"""A team-possession model that does not look at the ball, trained on this match without labels.

The ball is missing on 41% of graded frames (DATA.md), and a possession change inside a long gap
has to be placed somewhere. The literature infers team possession from player positions alone
(Kim et al. 2023, 2026; Wei et al. 2015): the side with the ball stretches out and pushes up, the
side without it compacts and drops. This module learns that relation for this match:

  targets   frames where ball proximity alone names the side clearly (self-supervision, no GT)
  features  team shape and movement, oriented by each team's attacking direction
  model     L2-regularised logistic regression (numpy IRLS)
  honesty   cross-fitted by half: each half is predicted by the model trained on the other one,
            and the held-out agreement decides how much the decoder trusts it (zero if useless)
"""

import warnings

import numpy as np

from .atd import HOME, AWAY
from .features import nan_moving_mean

FEATURE_NAMES = ("relative_position", "spread_x", "spread_y", "relative_velocity", "speed",
                 "block_position", "block_velocity")


LAGS = (-50, -25, 0, 25, 50)


def shifted(values, k):
    """values[t + k] at t, NaN where that falls outside the half."""
    out = np.full_like(values, np.nan)
    if k > 0:
        out[:-k] = values[k:]
    elif k < 0:
        out[-k:] = values[:k]
    else:
        out[:] = values
    return out


def features(ctx, pitch):
    """(X, valid): per-frame features, raw, smoothed over 1 s and 4 s, and 2 s means 1 s and 2 s
    ahead and 1 s behind.

    A team's shape answers a change of possession with a delay -- the side that wins the ball
    spreads out over the next seconds -- so the shape just after t says more about who had the
    ball at t than the shape at t does. Offline, the future is available: the shifted windows let
    the regression learn that delay instead of inheriting it.
    """
    length = pitch[0]
    shape = ctx["shape"]
    sign = ctx["attack_sign"]
    home, away = shape[HOME], shape[AWAY]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        total = home["n"] + away["n"]
        block_x = (home["mx"] * home["n"] + away["mx"] * away["n"]) / np.maximum(total, 1)
        block_vx = (home["vx"] * home["n"] + away["vx"] * away["n"]) / np.maximum(total, 1)
        # Everything is oriented along the home side's attacking direction, so one model serves
        # both halves although the teams swap ends at halftime.
        base = np.vstack([
            sign * (home["mx"] - away["mx"]) / 10.0,
            (home["sx"] - away["sx"]) / 10.0,
            (home["sy"] - away["sy"]) / 10.0,
            sign * (home["vx"] - away["vx"]) / 3.0,
            (home["speed"] - away["speed"]) / 3.0,
            sign * (block_x - length / 2) / (length / 2),
            sign * block_vx / 3.0,
        ]).T
    valid = (home["n"] >= 7) & (away["n"] >= 7) & np.all(np.isfinite(base), axis=1)
    base[~valid] = np.nan
    blocks = [base]
    for half in (12, 50):
        blocks.append(np.column_stack([nan_moving_mean(base[:, j], half)
                                       for j in range(base.shape[1])]))
    two_seconds = np.column_stack([nan_moving_mean(base[:, j], 25) for j in range(base.shape[1])])
    for lag in (25, 50, -25):
        blocks.append(shifted(two_seconds, lag))
    X = np.hstack(blocks)
    valid = valid & np.all(np.isfinite(X), axis=1)
    return X, valid


def fit_logistic(X, y, weight, l2, iterations=30):
    """Weighted L2 logistic regression by Newton steps. Returns (coef, intercept)."""
    n, d = X.shape
    design = np.hstack([X, np.ones((n, 1))])
    beta = np.zeros(d + 1)
    penalty = np.full(d + 1, l2)
    penalty[-1] = 0.0
    for _ in range(iterations):
        z = np.clip(design @ beta, -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        w = weight * p * (1.0 - p)
        gradient = design.T @ (weight * (y - p)) - penalty * beta
        hessian = design.T @ (design * w[:, None]) + np.diag(penalty + 1e-9)
        step = np.linalg.solve(hessian, gradient)
        beta += step
        if np.max(np.abs(step)) < 1e-7:
            break
    return beta[:-1], beta[-1]


def lag_profile(logits, halves, prepared):
    """Held-out agreement of the logit at t + lag with the side on the ball at t, per lag.

    Label-free: the targets are the proximity-confident frames. A peak away from lag 0 means the
    model's answer comes early or late; with the shifted features it should sit at 0.
    """
    profile = []
    for lag in LAGS:
        agree = total = 0
        for logit, (_, _, target, truth) in zip(logits, prepared):
            if not np.any(logit):
                continue
            moved = shifted(logit, lag)
            usable = target & np.isfinite(moved)
            agree += int(np.sum((moved[usable] > 0) == truth[usable]))
            total += int(usable.sum())
        profile.append((lag, agree / float(total) if total else None))
    return profile


def cross_fit(halves, cfg, pitch):
    """Out-of-fold logit per frame for each half, and the held-out agreement of each fold.

    Returns ([logit_per_half], [accuracy_per_half], [n_targets_per_half], lag profile). A half
    whose partner has too few targets gets zeros and accuracy None.
    """
    prepared = []
    for ctx in halves:
        X, valid = features(ctx, pitch)
        target = ctx["confident"] & valid & ~ctx["dead_hint"]
        prepared.append((X, valid, target, ctx["c_home"] > ctx["c_away"]))

    logits, accuracies, counts = [], [], []
    for index, ctx in enumerate(halves):
        X, valid, target, _ = prepared[index]
        counts.append(int(target.sum()))
        others = [prepared[j] for j in range(len(halves)) if j != index]
        train_X = np.vstack([o[0][o[2]][::cfg["ballfree.subsample"]] for o in others]) \
            if others else np.empty((0, X.shape[1]))
        train_y = np.concatenate([o[3][o[2]][::cfg["ballfree.subsample"]] for o in others]) \
            if others else np.empty(0)
        if len(train_y) < cfg["ballfree.min_train"] or train_y.all() or not train_y.any():
            logits.append(np.zeros(ctx["n"]))
            accuracies.append(None)
            continue
        mean = train_X.mean(axis=0)
        std = train_X.std(axis=0)
        std[std < 1e-9] = 1.0
        y = train_y.astype(np.float64)
        balance = np.where(train_y, 0.5 / y.mean(), 0.5 / (1.0 - y.mean()))
        coef, intercept = fit_logistic((train_X - mean) / std, y, balance, cfg["ballfree.l2"])

        logit = np.zeros(ctx["n"])
        logit[valid] = ((X[valid] - mean) / std) @ coef + intercept
        logits.append(logit)
        held = target
        if held.sum() >= 200:
            truth = prepared[index][3][held]
            accuracies.append(float(np.mean((logit[held] > 0) == truth)))
        else:
            accuracies.append(None)
    return logits, accuracies, counts, lag_profile(logits, halves, prepared)


def weight_from_accuracy(accuracy, cfg):
    """0 at or below acc_floor, 1 at or above acc_full, linear in between."""
    if accuracy is None:
        return 0.0
    span = cfg["ballfree.acc_full"] - cfg["ballfree.acc_floor"]
    return float(np.clip((accuracy - cfg["ballfree.acc_floor"]) / span, 0.0, 1.0))
