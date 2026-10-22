"""Candidate A with and without the P2 detector (#14, P3), on SYNTHETIC matches only.

    python -m solution.a_opus.compare_p2 <bundle> [<bundle> ...]

Same bundles and columns as compare_decoders; everything but p2.enabled is identical across rows.
Adds what P2 is meant to move: how far each decoded restart (D -> live) lies from the true one.
"""

import os
import sys

import numpy as np

from . import pipeline
from .compare_decoders import pm, short_spell_stats

VARIANTS = (("A (P2 off)", []), ("A + P2", ["p2.enabled=1"]))


def restart_errors(gt, pred, runs, reach=250):
    """|decoded - true| in frames for each true D -> live change with a decoded one within reach,
    and how many true ones had none."""
    errors, missed = [], 0
    for a, b in runs:
        g, p = gt[a:b], pred[a:b]
        true = np.flatnonzero((g[:-1] == 2) & (g[1:] != 2)) + 1
        found = np.flatnonzero((p[:-1] == 2) & (p[1:] != 2)) + 1
        for t in true:
            if found.size and np.min(np.abs(found - t)) <= reach:
                errors.append(int(np.min(np.abs(found - t))))
            else:
                missed += 1
    return errors, missed


def main(argv=None):
    bundles = sys.argv[1:] if argv is None else argv
    if not bundles:
        print(__doc__)
        return 2
    rows = {name: [] for name, _ in VARIANTS}
    errors = {name: [] for name, _ in VARIANTS}
    for bundle in bundles:
        gt = pm.label_codes(pm.read_label_csv(os.path.join(bundle, "synthetic_gt.csv")))
        runs = pm.valid_runs(gt)
        for name, overrides in VARIANTS:
            out = os.path.join(bundle, "results", "compare_p2.csv")
            pipeline.run(out, bundle, overrides, log=lambda *a: None)
            pred = pm.fill_abstentions(pm.label_codes(pm.read_label_csv(out)), runs)
            r = pm.evaluate(gt, pred)
            hit, n_short, false_short = short_spell_stats(gt, pred, runs)
            t = r["transitions"][25]
            found, missed = restart_errors(gt, pred, runs)
            errors[name] += found
            rows[name].append((r["spell_f1_mean"], r["macro_f1"], r["n_pred_spells"],
                               r["n_gt_spells"], r["fragmentation"], hit, n_short, false_short,
                               t["precision"], t["recall"], missed))
            os.remove(out)
    print("{:<11} {:>8} {:>8} {:>11} {:>6} {:>13} {:>12} {:>8} {:>8} {:>16} {:>7}".format(
        "variant", "spellF1", "macroF1", "poss/gt", "frag", "short kept", "false <2 s",
        "trans P", "trans R", "restart |err| p50/p90", "missed"))
    for name, _ in VARIANTS:
        a = np.array(rows[name], dtype=np.float64)
        e = np.array(errors[name]) if errors[name] else np.zeros(1)
        print("{:<11} {:>8.4f} {:>8.4f} {:>5.0f}/{:<5.0f} {:>6.2f} {:>6.0f}/{:<6.0f} {:>12.0f} "
              "{:>8.2f} {:>8.2f} {:>10.0f}/{:<10.0f} {:>7.0f}".format(
                  name, a[:, 0].mean(), a[:, 1].mean(), a[:, 2].sum(), a[:, 3].sum(),
                  a[:, 4].mean(), a[:, 5].sum(), a[:, 6].sum(), a[:, 7].sum(), a[:, 8].mean(),
                  a[:, 9].mean(), np.percentile(e, 50), np.percentile(e, 90), a[:, 10].sum()))
    return 0


if __name__ == "__main__":
    sys.exit(main())
