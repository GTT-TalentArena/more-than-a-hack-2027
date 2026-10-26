"""Run models on DFL matches under the §1.2 profiles and record the §3.2 metrics.

    python -m heldout run --model a=configs/candidate_a.json [--model v=configs/<variant>.json]
                          [--matches ...] [--profiles ...] [--seeds ...] [--heldout]

Each model goes through P0 (python -m solution.predict) with the data folder pointed at a bundle
in the challenge's format, exactly as it runs on the challenge game. Development matches are the
default; the two reserved matches (§2) need --heldout and are only for the final comparison.

Results append to salidas/heldout/results.jsonl. A run is reused only if match, profile, seed,
model name, model identity and harness identity all match (heldout/identity.py): changing a
model's code or config, or the harness, recomputes it and records it separately.
"""

import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import time

import numpy as np

from evaluation import possession_metrics as pm
from . import bundle, convert, degrade, identity, score
from .fetch import MATCHES

HELDOUT = ("J03WN1", "J03WR9")
DEVELOPMENT = tuple(m for m in MATCHES if m not in HELDOUT)
ROOT = identity.ROOT


def work_dir():
    return os.path.dirname(convert.arrays_dir())


def results_path():
    return os.path.join(work_dir(), "results.jsonl")


def observation_hash(obs):
    digest = hashlib.sha256()
    for key in ("ball", "slots"):
        digest.update(np.ascontiguousarray(obs[key]).tobytes())
    return digest.hexdigest()


def runs_of(profiles, seeds):
    for profile in profiles:
        for seed in ([0] if profile == "clean" else seeds):
            yield profile, seed


def run_key(record):
    # Records written before identities existed have none: they never match a current run.
    return (record["match"], record["profile"], record["seed"], record["model"],
            record.get("model_identity"), record.get("harness_identity"))


def read_results(path=None):
    path = path or results_path()
    if not os.path.exists(path):
        return []
    with open(path) as handle:
        return [json.loads(line) for line in handle if line.strip()]


def prediction_path(match_id, profile, seed, model, model_id):
    return os.path.join(work_dir(), "preds", match_id, "{}-{}".format(profile, seed),
                        "{}-{}.csv".format(model, model_id[:12]))


def git_state():
    def git(*args):
        return subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True,
                              check=True).stdout.strip()
    try:
        return {"commit": git("rev-parse", "HEAD"), "dirty": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "dirty": None}


def predict(config, bundle_dir, out_csv):
    env = dict(os.environ, MTAH_DATA_DIR=bundle_dir)
    started = time.time()
    subprocess.run([sys.executable, "-m", "solution.predict", "--config", config, "--out", out_csv],
                   cwd=ROOT, env=env, check=True, stdout=subprocess.DEVNULL)
    return time.time() - started


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--model", action="append", required=True, metavar="NAME=CONFIG")
    parser.add_argument("--matches", nargs="+", default=list(DEVELOPMENT))
    parser.add_argument("--profiles", nargs="+", default=list(degrade.PROFILES), choices=list(degrade.PROFILES))
    parser.add_argument("--seeds", nargs="+", type=int, default=list(degrade.SEEDS))
    parser.add_argument("--heldout", action="store_true", help="allow the reserved matches (§2)")
    parser.add_argument("--keep-bundles", action="store_true", help="keep the written bundles (large)")
    args = parser.parse_args(argv)
    models = dict(item.split("=", 1) for item in args.model)
    reserved = sorted(set(args.matches) & set(HELDOUT))
    if reserved and not args.heldout:
        parser.error("{} are reserved for the final comparison (plan §2): pass --heldout".format(
            ", ".join(reserved)))
    if reserved:
        print("[heldout] using reserved matches {}: final comparison only".format(", ".join(reserved)))

    harness_id = identity.harness_identity()
    model_ids = {name: identity.model_identity(config) for name, config in models.items()}
    for name, model_id in sorted(model_ids.items()):
        print("[heldout] model {} = {} (identity {})".format(name, models[name], model_id[:12]))
    finished = {run_key(r) for r in read_results() if r["valid"]}
    state = git_state()

    for match_id in args.matches:
        match = convert.load(match_id)
        gt = bundle.ground_truth(match["label"], match["period"])
        gt_sha = hashlib.sha256(gt.tobytes()).hexdigest()
        gt_path = os.path.join(work_dir(), "gt", match_id + ".csv")
        if not os.path.exists(gt_path):
            bundle.write_ground_truth(gt_path, gt)
        for profile, seed in runs_of(args.profiles, args.seeds):
            todo = {name: cfg for name, cfg in models.items()
                    if (match_id, profile, seed, name, model_ids[name], harness_id) not in finished}
            if not todo:
                continue
            obs = degrade.observe(match, match_id, profile, seed)
            obs_sha = observation_hash(obs)
            bundle_dir = os.path.join(work_dir(), "bundles", match_id, "{}-{}".format(profile, seed))
            inputs = bundle.write(bundle_dir, obs, match["period"])
            for name, config in sorted(todo.items()):
                out_csv = prediction_path(match_id, profile, seed, name, model_ids[name])
                if os.path.exists(out_csv):
                    os.remove(out_csv)   # an interrupted run of this exact identity: P0 never overwrites
                seconds = predict(config, bundle_dir, out_csv)
                table = pm.read_label_csv(out_csv)
                problem = pm.validate_submission(table, len(gt))
                record = {"match": match_id, "profile": profile, "seed": seed, "model": name,
                          "config": config, "config_sha256": bundle.sha256(os.path.join(ROOT, config)),
                          "model_identity": model_ids[name], "harness_identity": harness_id,
                          "environment": identity.environment(), "git": state,
                          "observation_sha256": obs_sha, "gt_sha256": gt_sha, "inputs_sha256": inputs,
                          "prediction": os.path.relpath(out_csv, work_dir()),
                          "prediction_sha256": bundle.sha256(out_csv), "seconds": round(seconds, 1),
                          "valid": not problem,
                          "metrics": score.metrics(gt, pm.label_codes(table)) if not problem else None}
                with open(results_path(), "a") as handle:
                    handle.write(json.dumps(record) + "\n")
                print("[heldout] {} {}-{} {:<10} spellF1 {:.4f} macroF1 {:.4f} ({:.0f} s)".format(
                    match_id, profile, seed, name, record["metrics"]["spell_f1"],
                    record["metrics"]["macro_f1"], seconds) if record["valid"] else
                    "[heldout] {} {}-{} {} INVALID: {}".format(match_id, profile, seed, name, problem),
                    flush=True)
            if not args.keep_bundles:
                shutil.rmtree(bundle_dir)
    return 0


if __name__ == "__main__":
    sys.exit(main())
