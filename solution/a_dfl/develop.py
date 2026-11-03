"""Leave-one-match-out development runs: A, A without its ball-free model, and the variant.

    python -m solution.a_dfl.develop [--matches ...] [--profiles ...] [--seeds ...]
    python -m solution.a_dfl.develop --summary

Section 4 of docs/experimentos/A_DFL_BALLFREE.md. On each development match the variant uses the
model trained on the other four (salidas/a_dfl/folds/, written by train.py), so no score comes
from a match the model saw. Observations, ground truth and metrics are heldout/'s: degrade.observe,
bundle.ground_truth, and score.metrics on the official metric code. Results go to
salidas/a_dfl/develop-<match>.jsonl, one line per profile and seed; a line is reused only while
the code that produced it and the fold model are unchanged. The reserved matches are refused.
"""

import argparse
import glob
import hashlib
import json
import os
import shutil
import sys

import numpy as np

from evaluation import possession_metrics as pm
from heldout import bundle, degrade, score
from heldout.run import DEVELOPMENT, observation_hash, runs_of

from . import model as dfl
from . import train

# A v1.6, A with its ball-free model off (what A becomes without self-training), the variant.
MODELS = ("a", "a0", "v")
OVERRIDES = {"a": (), "a0": ("ballfree.enabled=0",), "v": ()}
CODE = ("solution/a_opus/*.py", "solution/a_dfl/model.py", "solution/a_dfl/train.py",
        "solution/a_dfl/develop.py", "heldout/convert.py", "heldout/degrade.py", "heldout/bundle.py",
        "heldout/score.py", "evaluation/possession_metrics.py", "games.py")
ROOT = os.path.dirname(os.path.dirname(dfl.HERE))


def code_identity():
    """Hash of the code a development run depends on (not weights.py: these runs use the folds)."""
    digest = hashlib.sha256()
    for pattern in CODE:
        for path in sorted(glob.glob(os.path.join(ROOT, pattern))):
            with open(path, "rb") as handle:
                digest.update(os.path.relpath(path, ROOT).replace("\\", "/").encode() + b"\0"
                              + handle.read().replace(b"\r\n", b"\n") + b"\0")
    return digest.hexdigest()


def load_fold(match_id):
    path = os.path.join(train.WORK, "folds", match_id + ".json")
    if not os.path.exists(path):
        raise SystemExit("no fold model for {}: run python -m solution.a_dfl.train first".format(match_id))
    with open(path) as handle:
        text = handle.read()
    return json.loads(text), hashlib.sha256(text.encode()).hexdigest()


def results_path(match_id):
    return os.path.join(train.WORK, "develop-{}.jsonl".format(match_id))


def read_records(match_id=None):
    paths = [results_path(match_id)] if match_id else sorted(
        glob.glob(os.path.join(train.WORK, "develop-*.jsonl")))
    records = []
    for path in paths:
        if os.path.exists(path):
            with open(path) as handle:
                records += [json.loads(line) for line in handle if line.strip()]
    return records


def evaluate(match_id, profile, seed, fold, fold_sha, identity):
    period, obs, gt = train.observe(match_id, profile, seed)
    folder = os.path.join(train.WORK, "bundles", "{}-{}-{}".format(match_id, profile, seed))
    inputs = bundle.write(folder, obs, period)
    record = {"match": match_id, "profile": profile, "seed": seed, "code_identity": identity,
              "fold_sha256": fold_sha, "observation_sha256": observation_hash(obs),
              "gt_sha256": hashlib.sha256(gt.tobytes()).hexdigest(), "inputs_sha256": inputs,
              "models": {}}
    store = []
    try:
        for name in MODELS:
            out = os.path.join(folder, name + ".csv")
            lines, seconds = train.run_pipeline(
                folder, out, OVERRIDES[name], model=fold if name == "v" else None,
                store=store if name == "a" else None)
            table = pm.read_label_csv(out)
            problem = pm.validate_submission(table, len(gt))
            if problem:
                raise RuntimeError("{} {}-{} {}: invalid output: {}".format(match_id, profile, seed, name, problem))
            with open(out, "rb") as handle:
                csv_sha = hashlib.sha256(handle.read()).hexdigest()
            record["models"][name] = {
                "metrics": score.metrics(gt, pm.label_codes(table)), "seconds": round(seconds, 1),
                "prediction_sha256": csv_sha,
                "ballfree_log": [line for line in lines if "ball-free" in line]}
    finally:
        shutil.rmtree(folder)
    arrays = train.stack_halves(store, gt)
    record["component"] = train.accuracies(arrays, dfl.logit(arrays["X"], arrays["valid"], fold))
    return record


def run(match_ids, profiles, seeds):
    identity = code_identity()
    for match_id in match_ids:
        fold, fold_sha = load_fold(match_id)
        if match_id in fold["training"]["matches"]:
            raise SystemExit("the fold model for {} was trained on it".format(match_id))
        done = {(r["profile"], r["seed"]) for r in read_records(match_id)
                if r["code_identity"] == identity and r["fold_sha256"] == fold_sha}
        for profile, seed in runs_of(profiles, seeds):
            if (profile, seed) in done:
                continue
            record = evaluate(match_id, profile, seed, fold, fold_sha, identity)
            with open(results_path(match_id), "a") as handle:
                handle.write(json.dumps(record) + "\n")
            m = {name: record["models"][name]["metrics"] for name in MODELS}
            print("[a_dfl] {} {}-{}  spellF1 a {:.4f}  a0 {:.4f}  v {:.4f}   macroF1 a {:.4f}  v {:.4f}"
                  .format(match_id, profile, seed, m["a"]["spell_f1"], m["a0"]["spell_f1"],
                          m["v"]["spell_f1"], m["a"]["macro_f1"], m["v"]["macro_f1"]), flush=True)


def summary(match_ids):
    """The gate of plan section 4, and the tables behind it, from the current records."""
    identity = code_identity()
    records = [r for r in read_records() if r["code_identity"] == identity and r["match"] in match_ids]
    degraded = [p for p in degrade.PROFILES if p != "clean"]
    names = list(MODELS)

    def mean(rows, name, metric):
        values = [r["models"][name]["metrics"][metric] for r in rows]
        return float(np.mean(values)) if values else None

    per_match = {}
    for match_id in match_ids:
        rows = [r for r in records if r["match"] == match_id and r["profile"] in degraded]
        per_match[match_id] = {"runs": len(rows), **{
            "{}_{}".format(metric, name): mean(rows, name, metric)
            for metric in ("spell_f1", "macro_f1", "false_short_per_90") for name in names}}
    per_profile = {}
    for profile in degrade.PROFILES:
        rows = [r for r in records if r["profile"] == profile]
        per_profile[profile] = {"runs": len(rows), **{
            "spell_f1_" + name: mean(rows, name, "spell_f1") for name in names}}
    complete = [m for m in match_ids if per_match[m]["runs"]]
    wins = [m for m in complete if per_match[m]["spell_f1_v"] > per_match[m]["spell_f1_a"]]
    macro_drop = float(np.mean([per_match[m]["macro_f1_a"] - per_match[m]["macro_f1_v"] for m in complete])) \
        if complete else None
    component = {}
    for field in ("no_ball", "unclear", "live"):
        rows = [r["component"][field] for r in records if r["component"][field]["a"] is not None]
        component[field] = {"a": float(np.mean([c["a"] for c in rows])) if rows else None,
                            "variant": float(np.mean([c["variant"] for c in rows])) if rows else None,
                            "runs": len(rows)}
    gate = {"matches_with_runs": len(complete), "variant_above_a": len(wins),
            "mean_macro_f1_drop": macro_drop,
            "passed": len(complete) == len(match_ids) and len(wins) >= 3
            and macro_drop is not None and macro_drop <= 0.02}
    out = {"code_identity": identity, "per_match": per_match, "per_profile": per_profile,
           "component": component, "gate": gate}

    print("[a_dfl] development, degraded profiles x seeds per match (spellF1 a / a0 / v, macroF1 a / v):")
    for match_id in complete:
        row = per_match[match_id]
        print("[a_dfl]   {} ({} runs)  {:.4f} / {:.4f} / {:.4f}   {:.4f} / {:.4f}   false short/90 a {:.1f} v {:.1f}"
              .format(match_id, row["runs"], row["spell_f1_a"], row["spell_f1_a0"], row["spell_f1_v"],
                      row["macro_f1_a"], row["macro_f1_v"], row["false_short_per_90_a"],
                      row["false_short_per_90_v"]))
    print("[a_dfl] per profile, mean over matches and seeds (spellF1 a / a0 / v):")
    for profile, row in per_profile.items():
        if row["runs"]:
            print("[a_dfl]   {:<13} ({} runs)  {:.4f} / {:.4f} / {:.4f}".format(
                profile, row["runs"], row["spell_f1_a"], row["spell_f1_a0"], row["spell_f1_v"]))
    print("[a_dfl] ball-free component, agreement with the DFL labels (A -> variant): " + ", ".join(
        "{} {:.1%} -> {:.1%}".format(k, v["a"], v["variant"]) for k, v in component.items() if v["runs"]))
    print("[a_dfl] gate: variant above A on {} of {} matches, mean macroF1 drop {}: {}".format(
        len(wins), len(complete), "--" if macro_drop is None else "{:+.4f}".format(macro_drop),
        "PASSED" if gate["passed"] else "not passed"))
    with open(os.path.join(train.WORK, "develop_summary.json"), "w") as handle:
        json.dump(out, handle, indent=1)
    return out


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--matches", nargs="+", default=list(DEVELOPMENT))
    parser.add_argument("--profiles", nargs="+", default=list(degrade.PROFILES), choices=list(degrade.PROFILES))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(degrade.SEEDS))
    parser.add_argument("--summary", action="store_true", help="only summarise the current records")
    args = parser.parse_args(argv)
    train.check_development(args.matches)
    train.guard_challenge_data()
    if not args.summary:
        run(args.matches, args.profiles, args.seeds)
    summary(args.matches)
    return 0


if __name__ == "__main__":
    sys.exit(main())
