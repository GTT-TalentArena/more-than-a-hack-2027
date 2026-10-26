"""Apply the decision rule of §3.6 to recorded runs, and print the tables for §4 of the report.

    python -m heldout report --a a=configs/candidate_a.json --variant v=configs/<variant>.json
                             [--matches J03WN1 J03WR9]

Only runs of the models' and the harness's **current** identities count (heldout/identity.py).
Before deciding anything, the report checks that the evidence is complete and consistent: every
match x profile x seed of the protocol for both models, no ambiguous duplicates, the same
observation and ground truth for A and the variant, and prediction files that still match their
recorded hashes. If anything fails it says "incomplete evaluation: no recommendation" and exits
with code 3.

Criteria 1 (reproducibility on the provided game) and 4 (runtime on the provided game) are not
computable from DFL runs: they are listed as manual checks. Nothing here reads the challenge game.
"""

import argparse
import hashlib
import json
import os
import sys

import numpy as np

from evaluation import possession_metrics as pm
from . import bundle, degrade, identity, score
from .run import HELDOUT, read_results, runs_of, work_dir

DEGRADED = [p for p in degrade.PROFILES if p != "clean"]
METRICS = ("spell_f1", "macro_f1", "false_short_per_90")
MACRO_DROP = 0.02
SHORT_FACTOR, SHORT_SLACK = 1.2, 1.0
INCOMPLETE = "incomplete evaluation: no recommendation"


def codes(path):
    return pm.label_codes(pm.read_label_csv(path))


def collect(records, models, matches, harness_id):
    """{(match, profile, seed): {name: record}} for the full protocol matrix, plus problems."""
    problems = []
    current = [r for r in records if r.get("harness_identity") == harness_id
               and any(r["model"] == name and r.get("model_identity") == model_id
                       for name, (_, model_id) in models.items())]
    table = {}
    for m in matches:
        for profile, seed in runs_of(list(degrade.PROFILES), list(degrade.SEEDS)):
            key = (m, profile, seed)
            table[key] = {}
            for name in models:
                found = [r for r in current if (r["match"], r["profile"], r["seed"], r["model"]) == (*key, name)]
                if not found:
                    problems.append("missing: {} {}-{} {}".format(m, profile, seed, name))
                    continue
                if any(not r["valid"] for r in found):
                    problems.append("invalid prediction: {} {}-{} {}".format(m, profile, seed, name))
                    continue
                if len({r["prediction_sha256"] for r in found}) > 1:
                    problems.append("ambiguous duplicates (different predictions for one identity): "
                                    "{} {}-{} {}".format(m, profile, seed, name))
                    continue
                table[key][name] = found[-1]
            pair = table[key]
            if len(pair) == len(models):
                if len({r["observation_sha256"] for r in pair.values()}) > 1:
                    problems.append("different observations for the two models: {} {}-{}".format(m, profile, seed))
                if len({r["gt_sha256"] for r in pair.values()}) > 1:
                    problems.append("different ground truth for the two models: {} {}-{}".format(m, profile, seed))
    return table, problems


def check_files(table, matches):
    """Prediction and ground-truth files on disk must still be the ones that were scored."""
    problems = []
    gt_hash = {}
    for m in matches:
        path = os.path.join(work_dir(), "gt", m + ".csv")
        if os.path.exists(path):
            gt_hash[m] = hashlib.sha256(codes(path).astype(np.int8).tobytes()).hexdigest()
    for (m, profile, seed), pair in table.items():
        for name, r in pair.items():
            path = os.path.join(work_dir(), r["prediction"])
            if not os.path.exists(path) or bundle.sha256(path) != r["prediction_sha256"]:
                problems.append("prediction file missing or changed: {} {}-{} {}".format(m, profile, seed, name))
            if gt_hash.get(m) != r["gt_sha256"]:
                problems.append("ground truth on disk differs from the scored one: {}".format(m))
    return sorted(set(problems))


def mean(values):
    values = [v for v in values if v is not None]
    return float(np.mean(values)) if values else None


def decide(models, matches, records=None):
    """`models` is {"a": (name, config), "v": (name, config)}."""
    (a, a_cfg), (v, v_cfg) = models["a"], models["v"]
    ids = {a: (a_cfg, identity.model_identity(a_cfg)), v: (v_cfg, identity.model_identity(v_cfg))}
    harness_id = identity.harness_identity()
    table, problems = collect(read_results() if records is None else records, ids, matches, harness_id)
    if not problems:
        problems = check_files(table, matches)
    out = {"identities": {name: model_id for name, (_, model_id) in ids.items()},
           "harness_identity": harness_id, "matches": {}, "full_bootstrap": {}, "checks": {}}
    if problems:
        out.update(status="incomplete", problems=problems, recommendation=INCOMPLETE)
        return out

    for m in matches:
        per_profile = {}
        for profile in degrade.PROFILES:
            keys = [k for k in table if k[0] == m and k[1] == profile]
            per_profile[profile] = {name: {metric: mean(table[k][name]["metrics"][metric] for k in keys)
                                           for metric in METRICS} for name in (a, v)}
            per_profile[profile]["seeds"] = len(keys)
        degraded = [k for k in table if k[0] == m and k[1] in DEGRADED]
        summary = {name: {metric: mean(table[k][name]["metrics"][metric] for k in degraded)
                          for metric in METRICS} for name in (a, v)}
        won = sum(1 for p in DEGRADED if per_profile[p][v]["spell_f1"] > per_profile[p][a]["spell_f1"])
        out["matches"][m] = {"profiles": per_profile, "degraded": summary, "profiles_won": won}
    for seed in degrade.SEEDS:
        triples = []
        for m in matches:
            pair = table[(m, "full", seed)]
            triples.append((codes(os.path.join(work_dir(), "gt", m + ".csv")),
                            codes(os.path.join(work_dir(), pair[a]["prediction"])),
                            codes(os.path.join(work_dir(), pair[v]["prediction"]))))
        out["full_bootstrap"][seed] = score.paired_bootstrap(triples)

    ms = list(out["matches"].values())
    out["checks"] = {
        "2a_better_on_each_match": all(d["degraded"][v]["spell_f1"] > d["degraded"][a]["spell_f1"] for d in ms),
        "2b_at_least_3_of_4_profiles": all(d["profiles_won"] >= 3 for d in ms),
        "2c_full_interval_above_zero": all(b["low"] > 0 for b in out["full_bootstrap"].values()),
        "3a_macro_f1_drop_at_most_0.02": all(d["degraded"][a]["macro_f1"] - d["degraded"][v]["macro_f1"] <= MACRO_DROP for d in ms),
        "3b_false_short_within_limit": all(d["degraded"][v]["false_short_per_90"]
                                           <= SHORT_FACTOR * d["degraded"][a]["false_short_per_90"] + SHORT_SLACK for d in ms),
        "1_reproducible_on_provided_game": "manual (two clean regenerations, identical SHA-256)",
        "4_runtime_under_30_min": "manual (provided game, reference hardware)",
    }
    automatic = [value for value in out["checks"].values() if isinstance(value, bool)]
    out["status"] = "complete"
    out["recommendation"] = ("adopt the variant, if checks 1 and 4 also pass" if all(automatic) else "keep A")
    return out


def markdown(result, a, v):
    lines = ["Identities: {} `{}`, {} `{}`, harness `{}`".format(
        a, result["identities"][a][:12], v, result["identities"][v][:12], result["harness_identity"][:12]), ""]
    if result["status"] != "complete":
        lines += ["**{}**".format(INCOMPLETE), ""] + ["- " + p for p in result["problems"]]
        return "\n".join(lines)
    lines += ["| match | profile | seeds | spellF1 {a} | spellF1 {v} | macroF1 {a} | macroF1 {v} | "
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
    parser.add_argument("--a", required=True, metavar="NAME=CONFIG", help="candidate A, as passed to run")
    parser.add_argument("--variant", required=True, metavar="NAME=CONFIG")
    parser.add_argument("--matches", nargs="+", default=list(HELDOUT))
    args = parser.parse_args(argv)
    models = {"a": tuple(args.a.split("=", 1)), "v": tuple(args.variant.split("=", 1))}
    result = decide(models, args.matches)
    with open(os.path.join(work_dir(), "decision.json"), "w") as handle:
        json.dump(result, handle, indent=2)
    print(markdown(result, models["a"][0], models["v"][0]))
    return 0 if result["status"] == "complete" else 3


if __name__ == "__main__":
    sys.exit(main())
