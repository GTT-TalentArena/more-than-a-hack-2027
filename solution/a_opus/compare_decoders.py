"""Viterbi against hysteresis against vote on the same evidence (#16), on SYNTHETIC matches only.

    python -m solution.a_opus.compare_decoders <bundle> [<bundle> ...]

Each bundle is a folder written by `python -m solution.a_opus.synth` (it carries its own
synthetic_gt.csv). Everything but the decoder is identical across rows. Reports, besides spellF1
and macroF1, what a per-frame score hides: fragmentation, how many short true possessions survive,
how many short false ones appear, and transition timing.
"""

import os
import sys

import numpy as np

from . import pipeline

sys.path.insert(0, os.path.join(pipeline.ROOT, "evaluation"))
import possession_metrics as pm  # noqa: E402

METHODS = ("viterbi", "hysteresis", "vote")


def short_spell_stats(gt, pred, runs, limit_frames=125):
    """(true possessions under 5 s matched at IoU 0.5 / their number,
    predicted possessions under 2 s with no match at IoU 0.5)."""
    gs = pm.possession_spells(gt, runs)
    ps = pm.possession_spells(pred, runs)
    overlaps = pm.spell_overlaps(gs, ps)
    hit_gt = pm.matched_gt_flags(overlaps, len(gs), 0.5)
    used = set()
    taken = set()
    for iou, i, j in overlaps:
        if iou < 0.5:
            break
        if i in taken or j in used:
            continue
        taken.add(i)
        used.add(j)
    short = [k for k, (a, b, _) in enumerate(gs) if b - a < limit_frames]
    false_short = sum(1 for j, (a, b, _) in enumerate(ps) if b - a < 50 and j not in used)
    return int(sum(hit_gt[k] for k in short)), len(short), false_short


def main(argv=None):
    bundles = sys.argv[1:] if argv is None else argv
    if not bundles:
        print(__doc__)
        return 2
    rows = {m: [] for m in METHODS}
    for bundle in bundles:
        gt = pm.label_codes(pm.read_label_csv(os.path.join(bundle, "synthetic_gt.csv")))
        runs = pm.valid_runs(gt)
        for method in METHODS:
            out = os.path.join(bundle, "results", "compare_{}.csv".format(method))
            pipeline.run(out, bundle, ["decode.method=" + method], log=lambda *a: None)
            pred = pm.fill_abstentions(pm.label_codes(pm.read_label_csv(out)), runs)
            r = pm.evaluate(gt, pred)
            hit, n_short, false_short = short_spell_stats(gt, pred, runs)
            t = r["transitions"][25]
            rows[method].append((r["spell_f1_mean"], r["macro_f1"], r["n_pred_spells"],
                                 r["n_gt_spells"], r["fragmentation"], hit, n_short, false_short,
                                 t["precision"], t["recall"]))
            os.remove(out)
    print("{:<11} {:>8} {:>8} {:>11} {:>6} {:>13} {:>12} {:>8} {:>8}".format(
        "decoder", "spellF1", "macroF1", "poss/gt", "frag", "short kept", "false <2 s",
        "trans P", "trans R"))
    for method in METHODS:
        a = np.array(rows[method], dtype=np.float64)
        print("{:<11} {:>8.4f} {:>8.4f} {:>5.0f}/{:<5.0f} {:>6.2f} {:>6.0f}/{:<6.0f} {:>12.0f} {:>8.2f} {:>8.2f}"
              .format(method, a[:, 0].mean(), a[:, 1].mean(), a[:, 2].sum(), a[:, 3].sum(),
                      a[:, 4].mean(), a[:, 5].sum(), a[:, 6].sum(), a[:, 7].sum(), a[:, 8].mean(),
                      a[:, 9].mean()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
