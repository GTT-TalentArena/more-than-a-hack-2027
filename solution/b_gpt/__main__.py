"""User-local inference: deterministic CSV, aggregate-only stdout, no ground truth."""

import argparse
from dataclasses import asdict
import hashlib
import json
from pathlib import Path
import platform
import resource
import sys
import time
import traceback
import warnings

import numpy as np

from .aggregate import comparison
from .config import CONFIG
from .io import InputError, read_events, read_tracking, write_submission
from .model import predict
from .report_io import read_labels, write_summary


def synthetic_baseline(tracking):
    """The published baseline, but on generated tracking only."""
    from starter.baseline import smooth
    codes = np.full(len(tracking.ball), -1, dtype=np.int8)
    for a in range(0, len(codes), 4096):
        b = min(len(codes), a + 4096)
        distance = np.linalg.norm(tracking.players[a:b, :, :2] - tracking.ball[a:b, None, :2], axis=2)
        distance[~np.isfinite(distance)] = np.inf
        closest = np.argmin(distance, axis=1)
        valid = np.isfinite(distance[np.arange(b - a), closest])
        codes[a:b][valid] = tracking.teams[closest[valid]]
    return smooth(codes, 50)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", default="evaluation/results/b_gpt.csv")
    parser.add_argument("--data-dir", help="Optional data root; otherwise MTAH_DATA_DIR.")
    parser.add_argument("--baseline", default="evaluation/results/baseline_smooth50.csv")
    parser.add_argument("--synthetic", action="store_true",
                        help="Generate all inputs independently; never resolve real asset paths.")
    args = parser.parse_args(argv)
    started = time.perf_counter()
    from games import GAME, GAMES, half_video_blocks
    from evaluation import possession_metrics as pm
    game = GAMES[GAME]
    n, fps, pitch = game["n_video_frames"], game["fps"], game["pitch"]
    blocks = half_video_blocks(GAME)
    destination = Path(args.out)
    report_path = destination.with_suffix(".summary.json")
    if destination.resolve() == report_path.resolve():
        raise InputError("Output filename must differ from its .summary.json companion.")
    if args.synthetic:
        from .synthetic import make_match
        tracking, events, names, _ = make_match(n, blocks, fps)
        baseline = synthetic_baseline(tracking)
    else:
        from games import asset_paths
        paths = asset_paths(game=GAME, data_dir=args.data_dir, source="tactical")
        protected = {Path(p).resolve() for p in [*paths.values(), args.baseline]}
        if destination.resolve() in protected or report_path.resolve() in protected:
            raise InputError("Output cannot overwrite an input asset or baseline.")
        # Fail on an absent/malformed comparator before doing the expensive work.
        baseline = read_labels(args.baseline, n)
        tracking, names = read_tracking(paths["atd_meta"], paths["atd_raw"], n, pitch)
        events = read_events(paths["smart_tagging"], fps)
    labels, totals = predict(tracking, events, names, blocks, fps, pitch)
    diagnostics = comparison(labels, baseline, events, blocks, fps)
    write_submission(destination, labels, n)
    if pm.validate_submission(pm.read_label_csv(destination), n):
        raise InputError("Official submission validator rejected the generated file.")
    digest = hashlib.sha256()
    for source in sorted(Path(__file__).parent.glob("*.py")):
        digest.update(source.name.encode())
        digest.update(source.read_bytes())
    report = dict(candidate="b_gpt", synthetic=bool(args.synthetic), config=asdict(CONFIG),
                  python=platform.python_version(), numpy=np.__version__,
                  code_sha256=digest.hexdigest(), evidence_totals=totals,
                  elapsed_seconds=round(time.perf_counter() - started, 3),
                  peak_rss_mib=round(resource.getrusage(resource.RUSAGE_SELF).ru_maxrss /
                                     (1024 ** 2 if sys.platform == "darwin" else 1024), 2))
    write_summary(report_path, diagnostics, metadata=report)
    stats = diagnostics["b_gpt"]["full_match"]
    print(json.dumps(dict(n_possessions=stats["n_possessions"],
                          mean_duration_seconds=stats["mean_duration_seconds"],
                          median_duration_seconds=stats["duration_seconds"]["p50"],
                          percent_D=stats["percent_D"], percent_X=stats["percent_X"]),
                     sort_keys=True, allow_nan=False))
    return 0


def entrypoint():
    try:
        with warnings.catch_warnings():
            warnings.simplefilter("error")
            return main()
    except InputError as error:
        print("ERROR: " + str(error), file=sys.stderr)
    except Exception as error:
        print("ERROR: processing failed (" + type(error).__name__ +
              "). Input values suppressed.", file=sys.stderr)
        for frame in traceback.extract_tb(error.__traceback__):
            print(f"  {Path(frame.filename).name}:{frame.lineno} in {frame.name}", file=sys.stderr)
    return 2


if __name__ == "__main__":
    sys.exit(entrypoint())
