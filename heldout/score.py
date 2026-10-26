"""Metrics of §3.2 and the paired bootstrap of §3.3, on top of the official evaluation code.

Every number comes from evaluation/possession_metrics.py; nothing here reimplements spellF1 or
macroF1. The two additions are the false-short-possession rate and the paired, multi-match version
of the official bootstrap_spell_f1.
"""

import numpy as np

from evaluation import possession_metrics as pm

FPS = 25
SHORT_FRAMES = 25            # predicted possessions under 1 s ...
SHORT_MAX_IOU = 0.3          # ... whose best same-team IoU is below the lowest official threshold
BOOTSTRAP_DRAWS = 1000
BOOTSTRAP_SEED = 0
PERCENTILES = (5, 95)        # 90% interval, the official percentiles


def metrics(gt, pred):
    """The §3.2 metrics for one prediction against one ground truth (full-length code arrays)."""
    result = pm.evaluate(gt, pred)
    runs = pm.valid_runs(gt)
    filled = pm.fill_abstentions(pred, runs)
    out = {
        "spell_f1": result["spell_f1_mean"],
        "macro_f1": result["macro_f1"],
        "n_spells": result["n_pred_spells"],
        "n_gt_spells": result["n_gt_spells"],
        "median_spell_s": median_spell_seconds(filled, runs),
        "false_short_per_90": false_short_rate(gt, filled, runs),
    }
    for tol, scores in result["transitions"].items():
        out["transition_f1_{}".format(tol)] = scores["f1"]
        out["mean_abs_latency_{}".format(tol)] = scores["mean_abs_latency"]
    return out


def median_spell_seconds(codes, runs):
    spells = pm.possession_spells(codes, runs)
    return float(np.median([b - a for a, b, _ in spells]) / FPS) if spells else None


def false_short_rate(gt, filled, runs):
    """Predicted H/A spells under SHORT_FRAMES whose best same-team IoU with any ground-truth spell
    is below SHORT_MAX_IOU, per 90 minutes of scored time: defined even when there are none."""
    gt_spells = pm.possession_spells(gt, runs)
    pred_spells = pm.possession_spells(filled, runs)
    best = np.zeros(len(pred_spells))
    for iou, _, j in pm.spell_overlaps(gt_spells, pred_spells):
        best[j] = max(best[j], iou)
    false_short = sum(1 for j, (a, b, _) in enumerate(pred_spells)
                      if b - a < SHORT_FRAMES and best[j] < SHORT_MAX_IOU)
    scored_minutes = float(np.sum(gt != pm.X)) / FPS / 60.0
    return false_short * 90.0 / scored_minutes if scored_minutes else None


def spell_flags(gt, pred):
    """What the official bootstrap_spell_f1 precomputes: matched-or-not per ground-truth
    possession per IoU threshold, plus the predicted possession count."""
    runs = pm.valid_runs(gt)
    filled = pm.fill_abstentions(pred, runs)
    gt_spells = pm.possession_spells(gt, runs)
    pred_spells = pm.possession_spells(filled, runs)
    overlaps = pm.spell_overlaps(gt_spells, pred_spells)
    flags = np.vstack([pm.matched_gt_flags(overlaps, len(gt_spells), t) for t in pm.SPELL_IOUS])
    return flags, len(pred_spells)


def _draw_score(flags, n_pred, picks):
    """spellF1 of one resample, exactly as the official bootstrap_spell_f1 computes it."""
    n_gt = len(picks)
    f1s = []
    for row in flags:
        tp = int(row[picks].sum())
        fn = n_gt - tp
        fp = max(0, n_pred - tp)
        f1s.append(2.0 * tp / (2 * tp + fp + fn) if tp else 0.0)
    return float(np.mean(f1s))


def paired_bootstrap(matches, draws=BOOTSTRAP_DRAWS, seed=BOOTSTRAP_SEED):
    """90% interval of the mean (equal match weights) of spellF1(variant) - spellF1(A).

    `matches` is a list of (gt, pred_a, pred_variant). Each draw resamples the ground-truth
    possessions of every match independently and uses the same picks for both models.
    """
    prepared = []
    for gt, pred_a, pred_v in matches:
        flags_a, n_a = spell_flags(gt, pred_a)
        flags_v, n_v = spell_flags(gt, pred_v)
        prepared.append((flags_a, n_a, flags_v, n_v, flags_a.shape[1]))
    rng = np.random.RandomState(seed)
    stats = np.empty(draws)
    for d in range(draws):
        diffs = []
        for flags_a, n_a, flags_v, n_v, n_gt in prepared:
            picks = rng.randint(0, n_gt, n_gt)
            diffs.append(_draw_score(flags_v, n_v, picks) - _draw_score(flags_a, n_a, picks))
        stats[d] = np.mean(diffs)
    low, high = np.percentile(stats, PERCENTILES)
    return {"low": float(low), "high": float(high), "draws": draws, "seed": seed,
            "excludes_zero": bool(low > 0 or high < 0)}
