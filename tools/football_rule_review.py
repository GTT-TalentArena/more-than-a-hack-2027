"""Observe unchanged A/P2 on invented development worlds for issue #47.

No real-data path, ground-truth path, model overrides or reserved set is accepted.
The observer returns A's evidence unchanged and verifies the resulting CSV hash.
"""
import argparse
from dataclasses import replace
import json
from pathlib import Path
import tempfile
from unittest.mock import patch
import warnings

import numpy as np

from evaluation import possession_metrics as pm
from heldout.bundle import sha256
from solution import dead_ball
from solution.a_opus import config, decode, evidence, pipeline
from tools import football_acceptance as fa


def kickoff_probes():
    """Four observation changes fixed in report section 3.9 before execution."""
    base = next(c for c in fa.scenarios() if c.id == "FA08" and c.condition == "tag-shift-+0")
    probes = []
    for name, window_end, gap in (("window-ends-at-motion", 200, None),
                                  ("only-two-moving-frames", 202, None),
                                  ("missing-five-frames", None, (199, 204)),
                                  ("missing-until-outside-centre-zone", None, (195, 240))):
        events = json.loads(json.dumps(base.events))
        ball = base.ball.copy()
        if window_end is not None:
            events[0]["end_frame"] = window_end
        if gap:
            ball[slice(*gap)] = np.nan
        probes.append(replace(base, condition=name, events=events, ball=ball))
    return probes


def signed_totals(values):
    values = np.asarray(values)
    return {"positive": float(values[values > 0].sum()),
            "negative": float(values[values < 0].sum())}


def neutral_dead_probe():
    """Replay the existing supplied-evidence case; no inference option changes."""
    cfg = config.build()
    team = np.r_[np.full(50, .4), np.full(30, -.4), np.full(50, .4)]
    truth = np.r_[np.full(50, decode.H), np.full(30, decode.A), np.full(50, decode.H)]
    costs = (cfg["decode.lam_ha"], cfg["decode.lam_ad"], cfg["decode.lam_da"])
    result = []
    for dead_value in (0., -.1):
        scores = (team / 2, -team / 2, np.full(len(team), dead_value) + abs(team) / 2)
        predicted = decode.viterbi(*scores, *costs, cfg["decode.min_dead"])
        result.append({"supplied_dead_evidence": dead_value,
                       "predicted_runs": fa.raw_runs(np.array(list("HAD"))[predicted]),
                       "decoded_score": float(decode.path_score(predicted, *scores, *costs)),
                       "reference_live_score": float(decode.path_score(truth, *scores, *costs))})
    return result


def p2_review(case):
    signals, candidates, _ = fa.p2_signals(case)
    starts = [c for c in candidates if c["evidence"] == "initial_kickoff_context"]
    expected = []
    for half in np.unique(case.period[case.period > 0]):
        indices = np.flatnonzero(case.period == half)
        runs = fa.raw_runs(case.expected[indices])
        expected.extend(int(indices[v[1]]) for u, v in zip(runs, runs[1:])
                        if u[0] == "D" and v[0] in "HA")
    found = sorted({int(c["restart_frame"]) for c in candidates if c["restart_frame"] is not None})
    errors = [min(found, key=lambda t: abs(t - ref)) - ref for ref in expected] if found else []
    return {"condition": case.condition, "observation_sha256": fa.observation_hash(case),
            "expected_physical_restarts": expected, "confirmed_restarts": found,
            "nearest_errors_frames": errors,
            "initial_contexts": [{key: c[key] for key in ("period", "start_frame", "end_frame", "restart_frame")}
                                 for c in starts],
            "high_dead_frames": int(np.sum(signals["dead_score"] >= dead_ball.DEFAULTS["dead_threshold"])),
            "unknown_dead_frames": int(np.sum((case.period > 0) & ~signals["dead_valid"]))}


def trace_a(case):
    """Capture term totals only; never feed the reference to a model component."""
    captured = []
    original = evidence.dead_components

    def observe(ctx, *args, **kwargs):
        parts = original(ctx, *args, **kwargs)
        captured.append((ctx["first"], ctx["last"], {k: v.copy() for k, v in parts.items()}))
        return parts  # No emissions are changed by the observer.

    messages = []
    with tempfile.TemporaryDirectory(prefix="issue47-rule-review-") as temp:
        root = Path(temp)
        with fa.synthetic_bundle(case, root / "inputs") as (n, target, original_indices):
            with patch.object(evidence, "dead_components", side_effect=observe), warnings.catch_warnings():
                warnings.simplefilter("ignore", RuntimeWarning)
                pipeline.run(str(root / "prediction.csv"), str(root / "inputs"),
                             log=messages.append, evidence_path=str(root / "evidence.npz"))
            table = pm.read_label_csv(str(root / "prediction.csv"))
            if pm.validate_submission(table, n) is not None:
                raise RuntimeError("The observed synthetic pipeline produced an invalid CSV")
            predicted = np.full(len(case.ball), "X", dtype="<U1")
            predicted[original_indices] = table["label"].to_numpy()[target]
            # Compare the exact file with a separate ordinary run, not with a
            # reconstruction of A assembled from only some of its components.
            normal, technical = fa.run_a(case)
            if sha256(str(root / "prediction.csv")) != technical["csv_sha256"]:
                raise RuntimeError("Observing the components changed A's CSV")
            np.testing.assert_array_equal(predicted, normal)
            part_arrays = {}
            for first, last, parts in captured:
                for name, values in parts.items():
                    part_arrays.setdefault(name, np.zeros(n))[first:last + 1] = values
            expected_live = np.isin(case.expected[original_indices], ["H", "A"])
            with np.load(root / "evidence.npz") as trace:
                control = np.fmax(trace["control_H_score"][target], trace["control_A_score"][target])
                team = trace["team_llr"][target]
                dead = trace["dead_llr"][target]
                observed_valid = trace["control_valid"][target]
            parts = {key: signed_totals(values[target][expected_live]) for key, values in part_arrays.items()}
            residual = dead - sum(values[target] for values in part_arrays.values())
            return {"scenario": case.id, "condition": case.condition,
                    "observation_sha256": fa.observation_hash(case),
                    "observer_preserved_csv": True, "csv_sha256": technical["csv_sha256"],
                    "live_reference_frames": int(expected_live.sum()),
                    "original_ball_frames": int(np.sum(np.isfinite(case.ball[original_indices]).all(axis=1))),
                    "available_control_frames": int(observed_valid.sum()),
                    "available_control_without_original_ball": int(np.sum(
                        observed_valid & ~np.isfinite(case.ball[original_indices]).all(axis=1))),
                    "strong_control_live_frames": int(np.sum(expected_live & observed_valid & (control >= .6))),
                    "nonzero_team_evidence_live_frames": int(np.sum(expected_live & (abs(team) >= .01))),
                    "positive_dead_evidence_live_frames": int(np.sum(expected_live & (dead > 0))),
                    "dead_terms_on_live_frames": parts,
                    "additional_dead_evidence_on_live_frames": signed_totals(residual[expected_live]),
                    "calibration_log": [line for line in messages if any(marker in line for marker in (
                        "control zone:", "speed model:", "touches:", "ball-free team model:"))],
                    "acceptance": fa.assess(case, predicted)}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("The report destination must be new")
    cases = fa.scenarios()
    review = {"scope": "synthetic development rule review; no model adoption",
              "baseline_identity": fa.source_identity(),
              "review_source_sha256": sha256(__file__),
              "p2_source_sha256": sha256(dead_ball.__file__),
              "supplied_evidence_probe": neutral_dead_probe(),
              "traces": [trace_a(case) for case in cases],
              "p2": [p2_review(case) for case in cases if case.id in ("FA07", "FA08", "FA10")],
              "additional_kickoff_probes": [p2_review(case) for case in kickoff_probes()]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(review, handle, indent=2, allow_nan=False)
    print("Reviewed 17 invented worlds and 4 declared kickoff probes; every observed A CSV matched an ordinary run.")
    print("Review report written; no model, configuration, real-match label or adoption decision changed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
