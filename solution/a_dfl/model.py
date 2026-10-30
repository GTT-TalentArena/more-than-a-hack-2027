"""The variant's ball-free model: candidate A's features, fitted on other games, applied unchanged.

Candidate A trains its ball-free team model on the match it labels (ballfree.cross_fit, with ball
proximity as the targets). This variant keeps every other part of A and replaces that one fit by
a fixed logistic regression trained on the DFL development matches with the DFL possession labels
(train.py): nothing is fitted on the match being labelled.

A's pipeline looks the fit up as `ballfree.cross_fit` when it runs, so `installed()` swaps that
function and the weight rule for the length of a run and puts A's back afterwards. Outside it, A
is exactly A.

The model is antisymmetric under swapping the teams. Each of A's features is "home minus away",
oriented by the home side's attacking direction; exchanging home and away flips the sign of five
of them (spreads, mean speed, block position and velocity) and leaves two unchanged: the oriented
differences relative_position and relative_velocity, because the attacking direction flips too.
A linear model whose logit changes sign under the swap can only use the five, with no intercept,
so the model has no preference for the home side of the matches it was trained on.
"""

import contextlib
import hashlib
import os

import numpy as np

from solution.a_opus import ballfree

HERE = os.path.dirname(os.path.abspath(__file__))
A_DIR = os.path.join(os.path.dirname(HERE), "a_opus")
# The files of candidate A that define the features the coefficients were fitted on. If one of
# them changes, the coefficients no longer describe what the pipeline computes: retrain.
FEATURE_SOURCES = ("atd.py", "config.py", "ballfree.py", "features.py", "pipeline.py")
SYMMETRIC = ("relative_position", "relative_velocity")
ODD = np.array([name not in SYMMETRIC for name in ballfree.FEATURE_NAMES])


def odd_columns(n_columns):
    """Columns of ballfree.features() that change sign under the swap: it stacks windows of the
    seven base features one after the other, and every window keeps its feature's parity."""
    base = len(ballfree.FEATURE_NAMES)
    if n_columns % base:
        raise ValueError("expected a multiple of {} feature columns, got {}".format(base, n_columns))
    return np.flatnonzero(np.tile(ODD, n_columns // base))


def sources_sha256():
    """SHA-256 of FEATURE_SOURCES, with line ends normalised so a Windows checkout agrees."""
    digest = hashlib.sha256()
    for name in FEATURE_SOURCES:
        with open(os.path.join(A_DIR, name), "rb") as handle:
            digest.update(name.encode() + b"\0" + handle.read().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def fit(X, y, l2, weight=None):
    """Antisymmetric L2 logistic regression on the odd columns of X (frames x features).

    Every frame is also given with the teams swapped (odd columns negated, label flipped), and
    fitted with A's own fit_logistic. On that symmetric data the intercept's gradient is zero at
    every step, so it stays at 0. Columns are scaled by their root mean square: their mean is zero
    once both versions of each frame are in. Returns the model as plain Python numbers.
    """
    columns = odd_columns(X.shape[1])
    Z = X[:, columns].astype(np.float64)
    scale = np.sqrt(np.mean(Z * Z, axis=0))
    scale[scale < 1e-9] = 1.0
    Z = Z / scale
    target = np.asarray(y, dtype=np.float64)
    coef, intercept = ballfree.fit_logistic(np.vstack([Z, -Z]), np.concatenate([target, 1.0 - target]),
                                            np.ones(2 * len(Z)), l2)
    if abs(intercept) > 1e-6:
        raise RuntimeError("the swapped fit should leave the intercept at 0, got {}".format(intercept))
    return {"n_columns": int(X.shape[1]), "columns": [int(c) for c in columns],
            "scale": [float(s) for s in scale], "coef": [float(c) for c in coef],
            "weight": 1.0 if weight is None else float(weight)}


def logit(X, valid, model):
    """Per-frame logit of 'home has the ball'; 0 where the features are not valid."""
    if X.shape[1] != model["n_columns"]:
        raise ValueError("the model expects {} feature columns, the pipeline gave {}".format(
            model["n_columns"], X.shape[1]))
    out = np.zeros(len(X))
    z = X[valid][:, model["columns"]] / np.asarray(model["scale"])
    out[valid] = z @ np.asarray(model["coef"])
    return out


def cross_fit(halves, cfg, pitch, model):
    """Drop-in for ballfree.cross_fit with the same return values; nothing is fitted here.

    The agreement it returns is the fixed model's agreement with the side on the ball where
    proximity alone names it, on the frames A would have trained on. A sets its weight from it;
    the variant only prints it (its weight is fixed).
    """
    prepared, logits, accuracies, counts = [], [], [], []
    for ctx in halves:
        X, valid = ballfree.features(ctx, pitch)
        target = ctx["confident"] & valid & ~ctx["dead_hint"]
        truth = ctx["c_home"] > ctx["c_away"]
        prepared.append((X, valid, target, truth))
        values = logit(X, valid, model)
        logits.append(values)
        counts.append(int(target.sum()))
        accuracies.append(float(np.mean((values[target] > 0) == truth[target]))
                          if target.sum() >= 200 else None)
    return logits, accuracies, counts, ballfree.lag_profile(logits, halves, prepared)


def check_sources(model):
    if model.get("a_opus_sources_sha256") != sources_sha256():
        raise RuntimeError(
            "candidate A's feature code ({}) changed since this ball-free model was trained: "
            "retrain it with python -m solution.a_dfl.train".format(", ".join(FEATURE_SOURCES)))


@contextlib.contextmanager
def installed(model=None):
    """Within this block, A's pipeline uses the fixed model (default: weights.MODEL)."""
    if model is None:
        from .weights import MODEL as model
    check_sources(model)
    original = ballfree.cross_fit, ballfree.weight_from_accuracy
    ballfree.cross_fit = lambda halves, cfg, pitch: cross_fit(halves, cfg, pitch, model)
    ballfree.weight_from_accuracy = lambda accuracy, cfg: model["weight"]
    try:
        yield model
    finally:
        ballfree.cross_fit, ballfree.weight_from_accuracy = original


@contextlib.contextmanager
def recording(store):
    """Within this block, every ball-free fit (A's, or the variant's if installed) also appends to
    `store`, per half, what the model saw and what the pipeline does with it: the features, the
    logit, and the frames where A applies it at full weight (no ball) or at a share (unclear).
    Training and development only; the run itself is unchanged.
    """
    inner = ballfree.cross_fit

    def recorded(halves, cfg, pitch):
        result = inner(halves, cfg, pitch)
        for ctx, values in zip(halves, result[0]):
            X, valid = ballfree.features(ctx, pitch)
            no_ball = ctx["weight"] < 0.2
            store.append({"first": ctx["first"], "last": ctx["last"], "X": X, "valid": valid,
                          "logit": np.asarray(values, dtype=np.float64), "no_ball": no_ball,
                          "unclear": ~no_ball & (np.abs(ctx["team_prox"])
                                                 < cfg["ballfree.unclear_below"])})
        return result

    ballfree.cross_fit = recorded
    try:
        yield store
    finally:
        ballfree.cross_fit = inner
