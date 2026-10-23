"""Compare immediate and bounded P2 search; only synthetic bundles may be scored."""
import argparse
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

import games
from evaluation import possession_metrics as pm
from solution import dead_ball, temporal_control
from solution.hold import make_period_id
from starter import baseline


def sha256(path):
    with Path(path).open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def counts(candidates):
    """Allowlisted counts only: never return real candidate frames or intervals."""
    return {kind: sum(c["evidence"] == kind for c in candidates) for kind in
            ("tagged_preparation", "initial_kickoff_context", "observed_exit")}


def check_consumers(data_dir, output_dir):
    output_dir.mkdir(exist_ok=False)
    result = {}
    for name in ("p1", "temporal"):
        result[name] = {}
        for wait in (0., 1.):
            with patch.dict(dead_ball.DEFAULTS, restart_search_s=wait):
                build = dead_ball.build if name == "p1" else temporal_control.build
                parameters = (dict(dead_ball.DEFAULTS, enabled=True, max_hold_frames=25)
                              if name == "p1" else dict(temporal_control.DEFAULTS, p2_enabled=True))
                labels, diagnostic = build(str(data_dir), parameters)
                repeated, _ = build(str(data_dir), parameters)
            if not np.array_equal(labels, repeated):
                raise ValueError("Consumer is not deterministic")
            paths = [output_dir / f"{name}-{wait:g}-{suffix}.csv" for suffix in ("first", "repeat")]
            for path, values in zip(paths, (labels, repeated)):
                baseline.write_submission(str(path), values)
                error = pm.validate_submission(pm.read_label_csv(path), games.source_frames())
                if error:
                    raise ValueError(error)
            hashes = [sha256(path) for path in paths]
            if hashes[0] != hashes[1]:
                raise ValueError("Repeated CSV bytes differ")
            result[name][str(wait)] = dict(valid=True, deterministic=True, sha256=hashes[0],
                dead_label_frames=diagnostic["dead_label_frames"],
                abstention_frames=diagnostic["abstention_frames"])
    return result


def analyze(data_dir, synthetic=False, candidate_a=False):
    ball, observed, collective, player_count = dead_ball.load_geometry(str(data_dir))
    periods = make_period_id(len(ball), games.half_video_blocks(games.GAME))
    events = dead_ball.load_events(games.GAME, str(data_dir))
    result = dict(detector={})
    for wait in (0., 1.):
        _, candidates, summary = dead_ball.detect(ball, observed, periods, events,
            games.GAMES[games.GAME]["fps"], games.GAMES[games.GAME]["pitch"], collective, player_count,
            parameters={"restart_search_s": wait})
        result["detector"][str(wait)] = dict(candidate_counts=counts(candidates),
            delayed_preparations=summary["delayed_preparation_candidates"],
            set_pieces=summary["set_pieces"], dead_evidence_frames=summary["dead_evidence_frames"],
            confirmed_initial_kickoffs=sum(c["evidence"] == "initial_kickoff_context"
                                           and c["restart_frame"] is not None for c in candidates))
    assets = games.asset_paths(data_dir=str(data_dir))
    result["input_hashes"] = {name: sha256(assets[name]) for name in ("atd_raw", "smart_tagging")}
    if candidate_a:
        if not synthetic:
            raise ValueError("Candidate scoring is restricted to explicitly synthetic bundles")
        from solution.a_opus import pipeline
        from solution.a_opus.compare_p2 import restart_errors
        from solution.a_opus.compare_decoders import short_spell_stats
        gt = pm.label_codes(pm.read_label_csv(data_dir / "synthetic_gt.csv"))
        runs = pm.valid_runs(gt)
        result["candidate_a"] = {}
        for name, enabled, wait in (("off", False, 1.), ("immediate", True, 0.), ("bounded", True, 1.)):
            with tempfile.TemporaryDirectory(prefix="p2-synthetic-") as temp, \
                    patch.dict(dead_ball.DEFAULTS, restart_search_s=wait):
                path = Path(temp) / "candidate.csv"
                pipeline.run(str(path), str(data_dir), [f"p2.enabled={int(enabled)}"], log=lambda *a: None)
                pred = pm.label_codes(pm.read_label_csv(path))
                report = pm.evaluate(gt, pred)
                filled = pm.fill_abstentions(pred, runs)
                errors, missed = restart_errors(gt, filled, runs)
                _, _, false_short = short_spell_stats(gt, filled, runs)
                result["candidate_a"][name] = dict(spellF1=report["spell_f1_mean"], macroF1=report["macro_f1"],
                    false_possessions_under_2s=false_short, restart_errors_frames=errors,
                    missed_restarts=missed)
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundles", nargs="+", type=Path)
    parser.add_argument("--synthetic", action="store_true")
    parser.add_argument("--candidate-a", action="store_true")
    parser.add_argument("--check-consumers", action="store_true")
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    if args.candidate_a and not args.synthetic:
        parser.error("--candidate-a requires --synthetic; real match scoring is prohibited here")
    if args.out.exists():
        raise FileExistsError("Refusing to overwrite an existing comparison")
    args.out.parent.mkdir(parents=True, exist_ok=True)
    result = dict(scope="synthetic" if args.synthetic else "local-match-diagnostics-without-GT",
                  source_sha256=sha256(ROOT / "solution/dead_ball.py"), bundles=[])
    for index, bundle in enumerate(args.bundles):
        report = analyze(bundle, args.synthetic, args.candidate_a)
        if args.check_consumers:
            report["consumer_checks"] = check_consumers(bundle, args.out.parent / f"predictions-{index}")
        result["bundles"].append(report)
        print(f"Completed bundle {index + 1}/{len(args.bundles)}: " + json.dumps(report["detector"]))
    if args.candidate_a:
        result["candidate_a_aggregate"] = {}
        for name in ("off", "immediate", "bounded"):
            rows = [bundle["candidate_a"][name] for bundle in result["bundles"]]
            errors = [error for row in rows for error in row.pop("restart_errors_frames")]
            result["candidate_a_aggregate"][name] = dict(
                spellF1=float(np.mean([row["spellF1"] for row in rows])),
                macroF1=float(np.mean([row["macroF1"] for row in rows])),
                false_possessions_under_2s=sum(row["false_possessions_under_2s"] for row in rows),
                missed_restarts=sum(row["missed_restarts"] for row in rows),
                restart_error_p50_frames=float(np.median(errors)) if errors else None,
                restart_error_p90_frames=float(np.percentile(errors, 90)) if errors else None)
        print(json.dumps(result["candidate_a_aggregate"], indent=2, allow_nan=False))
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)


if __name__ == "__main__":
    main()
