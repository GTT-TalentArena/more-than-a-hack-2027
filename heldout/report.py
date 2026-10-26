"""Apply the decision rule of §3.6 to recorded runs, and print the tables for §4 of the report.

    python -m heldout report --a a --variant v [--matches J03WN1 J03WR9]

Criteria 1 (reproducibility on the provided game) and 4 (runtime on the provided game) are not
computable from DFL runs: they are listed as manual checks. Nothing here reads the challenge game.
"""

import argparse
import json
import os
import sys
from collections import defaultdict

import numpy as np

from evaluation import possession_metrics as pm
from . import degrade, score
from .run import HELDOUT, work_dir

DEGRADED = [p for p in degrade.PROFILES if p != "clean"]
MACRO_DROP = 0.02
SHORT_FACTOR, SHORT_SLACK = 1.2, 1.0


def load_results(models, matches):
    rows = defaultdict(dict)
    with open(os.path.join(work_dir(), "results.jsonl")) as handle:
        for r in map(json.loads, handle):
            if r["model"] in models and r["match"] in matches and r["valid"]:
                rows[(r["match"], r["profile"], r["seed"])][r["model"]] = r
    return rows


def mean(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def codes(path):
    return pm.label_codes(pm.read_label_csv(path))


def decide(a, v, matches):
    rows = load_results({a, v}, matches)
    complete = {key: pair for key, pair in rows.items() if a in pair and v in pair}
    out = {"matches": {}, "full_bootstrap": {}, "checks": {}}
    for m in matches:
        per_profile = {}
        for profile in degrade.PROFILES:
            keys = [k for k in complete if k[0] == m and k[1] == profile]
            if not keys:
                continue
            get = lambda name, metric: mean(complete[k][name]["metrics"][metric] for k in keys)
            per_profile[profile] = {name: {metric: get(name, metric) for metric in
                                           ("spell_f1", "macro_f1", "false_short_per_90")}
                                    for name in (a, v)} | {"seeds": len(keys)}
        degraded_keys = [k for k in complete if k[0] == m and k[1] in DEGRADED]
        avg = lambda name, metric: mean(complete[k][name]["metrics"][metric] for k in degraded_keys)
        summary = {name: {metric: avg(name, metric) for metric in
                          ("spell_f1", "macro_f1", "false_short_per_90")} for name in (a, v)}
        profiles_won = sum(1 for p in DEGRADED if p in per_profile
                           and per_profile[p][v]["spell_f1"] > per_profile[p][a]["spell_f1"])
        out["matches"][m] = {"profiles": per_profile, "degraded": summary,
                             "profiles_won": profiles_won,
                             "profiles_run": sum(1 for p in DEGRADED if p in per_profile)}
    for seed in degrade.SEEDS:
        triples = []
        for m in matches:
            pair = complete.get((m, "full", seed))
            if pair is None:
                break
            folder = os.path.join(work_dir(), "preds", m, "full-{}".format(seed))
            triples.append((codes(os.path.join(work_dir(), "gt", m + ".csv")),
                            codes(os.path.join(folder, a + ".csv")),
                            codes(os.path.join(folder, v + ".csv"))))
        if len(triples) == len(matches):
            out["full_bootstrap"][seed] = score.paired_bootstrap(triples)

    ms = out["matches"].values()
    ok = lambda xs: bool(xs) and all(xs)
    out["checks"] = {
        "2a_better_on_each_match": ok([d["degraded"][v]["spell_f1"] > d["degraded"][a]["spell_f1"] for d in ms]),
        "2b_at_least_3_of_4_profiles": ok([d["profiles_run"] == len(DEGRADED) and d["profiles_won"] >= 3 for d in ms]),
        "2c_full_interval_above_zero": len(out["full_bootstrap"]) == len(degrade.SEEDS)
                                       and all(b["low"] > 0 for b in out["full_bootstrap"].values()),
        "3a_macro_f1_drop_at_most_0.02": ok([d["degraded"][a]["macro_f1"] - d["degraded"][v]["macro_f1"] <= MACRO_DROP for d in ms]),
        "3b_false_short_within_limit": ok([d["degraded"][v]["false_short_per_90"] <= SHORT_FACTOR * d["degraded"][a]["false_short_per_90"] + SHORT_SLACK for d in ms]),
        "1_reproducible_on_provided_game": "manual (two clean regenerations, identical SHA-256)",
        "4_runtime_under_30_min": "manual (provided game, reference hardware)",
    }
    automatic = [value for key, value in out["checks"].items() if isinstance(value, bool)]
    out["recommendation"] = ("adopt the variant, if checks 1 and 4 also pass" if all(automatic)
                             else "keep A")
    return out


def markdown(result, a, v):
    lines = ["| match | profile | seeds | spellF1 {a} | spellF1 {v} | macroF1 {a} | macroF1 {v} | "
             "false short /90 {a} | false short /90 {v} |".format(a=a, v=v), "|---" * 9 + "|"]
    for m, d in result["matches"].items():
        for profile, p in d["profiles"].items():
            lines.append("| {} | {} | {} | {:.4f} | {:.4f} | {:.4f} | {:.4f} | {:.1f} | {:.1f} |".format(
                m, profile, p["seeds"], p[a]["spell_f1"], p[v]["spell_f1"], p[a]["macro_f1"],
                p[v]["macro_f1"], p[a]["false_short_per_90"], p[v]["false_short_per_90"]))
    lines += ["", "| `full` seed | 90% interval of mean paired spellF1 difference |", "|---|---|"]
    for seed, b in result["full_bootstrap"].items():
        lines.append("| {} | [{:+.4f}, {:+.4f}] |".format(seed, b["low"], b["high"]))
    lines += ["", "| check | result |", "|---|---|"]
    lines += ["| {} | {} |".format(k, v_) for k, v_ in result["checks"].items()]
    lines += ["", "**Recommendation from the rule:** " + result["recommendation"]]
    return "\n".join(lines)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--a", required=True, help="model name of A in results.jsonl")
    parser.add_argument("--variant", required=True)
    parser.add_argument("--matches", nargs="+", default=list(HELDOUT))
    args = parser.parse_args(argv)
    result = decide(args.a, args.variant, args.matches)
    with open(os.path.join(work_dir(), "decision.json"), "w") as handle:
        json.dump(result, handle, indent=2)
    print(markdown(result, args.a, args.variant))
    return 0


if __name__ == "__main__":
    sys.exit(main())
