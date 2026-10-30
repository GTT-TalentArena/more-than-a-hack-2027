"""Train the variant's ball-free model on the DFL development matches; the reserved ones are refused.

    python -m solution.a_dfl.train            # writes solution/a_dfl/weights.py

Needs the DFL arrays of the development matches (python -m heldout fetch <ids>, then convert). For
each development match it builds the observation of the `full` profile with seed 47 exactly as
heldout/ does (plan section 1.2), writes it as a challenge-format bundle and runs candidate A on
it, in-process, to collect the ball-free features A computes there. The targets are the DFL labels
of the live frames. Then:

  - per development match, a model trained on the other four, scored on the match left out
    against the DFL labels, next to A's self-trained model on the same frames (hypothesis H1);
  - the weight, by A's own rule on the mean of those accuracies;
  - the shipped model, trained on all five, written to weights.py with its provenance.

The leave-one-out models go to salidas/a_dfl/folds/ for develop.py. Everything printed is an
aggregate. Plan: docs/experimentos/A_DFL_BALLFREE.md.
"""

import argparse
import contextlib
import hashlib
import json
import os
import pprint
import shutil
import sys
import time

import numpy as np

import games
from heldout import bundle, convert, degrade
from heldout.run import DEVELOPMENT, HELDOUT, observation_hash
from solution.a_opus import ballfree, config, pipeline

from . import __version__
from . import model as dfl

PROFILE, SEED = "full", 47
SUBSAMPLE = config.DEFAULTS["ballfree.subsample"]
L2 = config.DEFAULTS["ballfree.l2"]
HOME_CODE, AWAY_CODE = 0, 1
SALIDAS = os.path.dirname(os.path.dirname(convert.arrays_dir()))
WORK = os.path.join(SALIDAS, "a_dfl")
WEIGHTS = os.path.join(dfl.HERE, "weights.py")


def guard_challenge_data():
    """In-process runs here always pass a bundle folder. If one ever did not, games would fall
    back to MTAH_DATA_DIR, the challenge match: point that fallback at an empty folder instead."""
    games.DATA_DIR = os.path.join(WORK, "no-challenge-data")


def check_development(match_ids):
    reserved = sorted(set(match_ids) & set(HELDOUT))
    if reserved:
        raise SystemExit("{} are reserved for the final comparison (plan section 2): never used "
                         "to train or develop the variant".format(", ".join(reserved)))
    unknown = sorted(set(match_ids) - set(DEVELOPMENT))
    if unknown:
        raise SystemExit("not development matches: " + ", ".join(unknown))


def observe(match_id, profile, seed):
    """(period, observation, ground-truth codes on the challenge timeline), as heldout/ builds them."""
    match = convert.load(match_id)
    return (match["period"], degrade.observe(match, match_id, profile, seed),
            bundle.ground_truth(match["label"], match["period"]))


def run_pipeline(bundle_dir, out_csv, overrides=(), model=None, store=None):
    """Candidate A on a bundle, in-process; the variant if `model` is given. `store` collects what
    the ball-free model saw (model.recording). Returns (log lines, seconds)."""
    lines = []
    started = time.time()
    with contextlib.ExitStack() as stack:
        if model is not None:
            stack.enter_context(dfl.installed(model))
        if store is not None:
            stack.enter_context(dfl.recording(store))
        pipeline.run(out_csv, bundle_dir, overrides, log=lines.append)
    return lines, time.time() - started


def stack_halves(store, gt):
    """One array per field over the graded halves, with the DFL label of each frame."""
    out = {key: np.concatenate([half[key] for half in store])
           for key in ("X", "valid", "logit", "no_ball", "unclear")}
    out["label"] = np.concatenate([gt[half["first"]:half["last"] + 1] for half in store])
    return out


def collect(match_id):
    """Features, masks, A's own ball-free logit and the DFL labels of one development match on
    the training observation. Cached under salidas/a_dfl/features/, keyed by the observation and
    by A's feature code."""
    period, obs, gt = observe(match_id, PROFILE, SEED)
    key = {"observation_sha256": observation_hash(obs), "sources_sha256": dfl.sources_sha256(),
           "gt_sha256": hashlib.sha256(gt.tobytes()).hexdigest()}
    path = os.path.join(WORK, "features", "{}-{}-{}.npz".format(match_id, PROFILE, SEED))
    if os.path.exists(path):
        with np.load(path) as cached:
            if all(str(cached[k]) == v for k, v in key.items()):
                return {k: cached[k] for k in cached.files}
    folder = os.path.join(WORK, "bundles", "{}-{}-{}".format(match_id, PROFILE, SEED))
    bundle.write(folder, obs, period)
    store = []
    try:
        run_pipeline(folder, os.path.join(folder, "a.csv"), store=store)
    finally:
        shutil.rmtree(folder)
    arrays = stack_halves(store, gt)
    arrays.update({k: np.array(v) for k, v in key.items()})
    os.makedirs(os.path.dirname(path), exist_ok=True)
    np.savez_compressed(path, **arrays)
    return arrays


def live(arrays):
    return np.isin(arrays["label"], (HOME_CODE, AWAY_CODE)) & arrays["valid"]


def training_rows(arrays):
    rows = live(arrays)
    return arrays["X"][rows][::SUBSAMPLE], (arrays["label"][rows] == HOME_CODE)[::SUBSAMPLE]


def accuracies(arrays, logit):
    """Agreement with the DFL labels where A uses the ball-free model, and on every live frame.

    Frames where A's own model gave no answer (logit exactly 0: a half without a model) are left
    out for both models, so both are scored on the same frames."""
    every = live(arrays)
    base = every & (arrays["logit"] != 0)
    home = arrays["label"] == HOME_CODE

    def agreement(values, mask):
        return float(np.mean((values[mask] > 0) == home[mask])) if mask.any() else None

    out = {}
    for name, mask in (("no_ball", base & arrays["no_ball"]), ("unclear", base & arrays["unclear"]),
                       ("live", base)):
        out[name] = {"frames": int(mask.sum()), "a": agreement(arrays["logit"], mask),
                     "variant": agreement(logit, mask)}
    # What sets the weight (plan section 3): every live frame with valid features.
    out["all_live"] = {"frames": int(every.sum()), "variant": agreement(logit, every)}
    return out


def fit_on(collected, match_ids, weight=None):
    pairs = [training_rows(collected[m]) for m in match_ids]
    X = np.vstack([p[0] for p in pairs])
    y = np.concatenate([p[1] for p in pairs])
    trained = dfl.fit(X, y, L2, weight)
    trained["training"] = {"matches": sorted(match_ids), "profile": PROFILE, "seed": SEED,
                           "frames": int(len(y)), "subsample": SUBSAMPLE, "l2": L2,
                           "home_share": float(np.mean(y))}
    trained["a_opus_sources_sha256"] = dfl.sources_sha256()
    return trained


def dfl_files(match_ids):
    """MD5 of the DFL files each match was converted from (heldout fetch manifest)."""
    path = os.path.join(os.path.dirname(convert.arrays_dir()), "dfl", "manifest.json")
    with open(path) as handle:
        manifest = json.load(handle)
    return {f["name"]: f["md5"] for f in manifest["files"]
            if f["match"] in match_ids and f["kind"] in ("meta", "positions")}


def write_weights(trained, path=WEIGHTS):
    text = ('"""Generated by python -m solution.a_dfl.train: do not edit by hand.\n\n'
            "The variant's ball-free model (model.py): antisymmetric logistic regression on candidate\n"
            "A's ball-free features, trained on the DFL development matches with their possession\n"
            "labels. `lomo` holds the leave-one-match-out check and how the fixed weight was set.\n"
            '"""\n\nMODEL = ' + pprint.pformat(trained, width=100, sort_dicts=True) + "\n")
    with open(path, "w", encoding="utf-8", newline="\n") as handle:
        handle.write(text)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--matches", nargs="+", default=list(DEVELOPMENT))
    args = parser.parse_args(argv)
    check_development(args.matches)
    guard_challenge_data()
    cfg = config.build()

    collected = {}
    for match_id in args.matches:
        started = time.time()
        collected[match_id] = collect(match_id)
        rows = live(collected[match_id])
        print("[a_dfl] {}: {} live frames with valid features, home share {:.1%} ({:.0f} s)".format(
            match_id, int(rows.sum()), float(np.mean(collected[match_id]["label"][rows] == HOME_CODE)),
            time.time() - started), flush=True)

    folds, table = {}, {}
    for match_id in args.matches:
        others = [m for m in args.matches if m != match_id]
        folds[match_id] = fit_on(collected, others)
        X, valid = collected[match_id]["X"], collected[match_id]["valid"]
        table[match_id] = accuracies(collected[match_id], dfl.logit(X, valid, folds[match_id]))
    mean_live = float(np.mean([table[m]["all_live"]["variant"] for m in args.matches]))
    weight = ballfree.weight_from_accuracy(mean_live, cfg)

    print("[a_dfl] leave-one-match-out agreement with the DFL labels (A self-trained -> variant):")
    for match_id in args.matches:
        print("[a_dfl]   {}  ".format(match_id) + "   ".join(
            "{} {:.1%} -> {:.1%} on {}".format(name, row["a"], row["variant"], row["frames"])
            for name, row in table[match_id].items() if row.get("a") is not None))
    print("[a_dfl] mean agreement on every live frame {:.1%} -> weight {:.2f} (A's rule: 0 at or "
          "below {:.0%}, 1 from {:.0%})".format(mean_live, weight, cfg["ballfree.acc_floor"],
                                                cfg["ballfree.acc_full"]))

    os.makedirs(os.path.join(WORK, "folds"), exist_ok=True)
    for match_id, fold in folds.items():
        fold["weight"] = weight
        with open(os.path.join(WORK, "folds", match_id + ".json"), "w") as handle:
            json.dump(fold, handle, indent=1)

    final = fit_on(collected, args.matches, weight)
    final["lomo"] = {"accuracy": table, "mean_live_accuracy": mean_live,
                     "rule": "ballfree.weight_from_accuracy(mean_live_accuracy)"}
    final["data"] = {"source": "DFL/IDSSE open data, figshare 10.6084/m9.figshare.28196177 v1, CC BY 4.0",
                     "files_md5": dfl_files(args.matches),
                     "observation_sha256": {m: str(collected[m]["observation_sha256"]) for m in args.matches}}
    final["version"] = __version__
    write_weights(final)
    print("[a_dfl] wrote {} ({} training frames, {} columns, weight {:.2f})".format(
        os.path.relpath(WEIGHTS), final["training"]["frames"], len(final["coef"]), weight))
    return 0


if __name__ == "__main__":
    sys.exit(main())
