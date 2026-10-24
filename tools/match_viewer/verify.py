"""Opt-in local verification. Print aggregates only; never observations or labels."""

import argparse
import hashlib
import json
from pathlib import Path
import platform
import statistics
import time

import numpy as np

import games
from solution.a_opus.atd import read_raw
from .estimation import estimated_window
from .predictions import load_predictions
from .tracking import IndexedTracking, ViewerError


def verify(meta, raw, predictions=None, n_frames=None):
    source = IndexedTracking(meta, raw, n_frames=n_frames)
    labels = load_predictions(predictions, source.n_frames)
    # Independent existing reader (float32) checks the ball channel and time index.
    reference_players, reference_ball, _ = read_raw(raw, source.meta, source.n_frames)
    del reference_players
    roles = source.layout['ball_roles']
    reference_ball = reference_ball[:, [roles.index('x'), roles.index('y')]].astype(np.float64) * source.pitch
    checked = windows = observed_players = observed_balls = 0
    estimated_samples = estimated_frames = 0
    durations = []
    estimate_durations = []
    started = time.perf_counter()
    for start in range(0, source.n_frames, 125):
        tick = time.perf_counter()
        rows = source.window(start, min(125, source.n_frames - start))
        durations.append((time.perf_counter() - tick) * 1000)
        tick = time.perf_counter()
        display_rows = estimated_window(source, start, len(rows))
        estimate_durations.append((time.perf_counter() - tick) * 1000)
        for row, display in zip(rows, display_rows):
            if row != {key: display[key] for key in row}:
                raise ViewerError('Display estimation changed an original observation.')
            if any(point is not None and row['players'][slot] is not None
                   for slot, point in enumerate(display['player_estimates'])):
                raise ViewerError('A player estimate overlaps an original observation.')
            estimated_samples += sum(point is not None for point in display['player_estimates'])
            estimated_frames += any(point is not None for point in display['player_estimates'])
        if [row['frame'] for row in rows] != list(range(start, start + len(rows))):
            raise ViewerError('Tracking and video frame alignment failed.')
        if len(rows) != min(125, source.n_frames - start):
            raise ViewerError('A requested frame window is incomplete.')
        for row in rows:
            reference = reference_ball[row['frame']]
            if np.isfinite(reference).all():
                if row['ball'] is None or not np.allclose(row['ball'], reference, rtol=1e-6, atol=2e-5):
                    raise ViewerError('Ball position disagrees with the existing tracking reader.')
            elif row['ball'] is not None:
                raise ViewerError('Ball observation mask disagrees with the existing tracking reader.')
            if len(row['players']) != len(source.slot_ids):
                raise ViewerError('A frame has an inconsistent slot count.')
            for point in row['players'] + [row['ball']]:
                if point is not None and (len(point) != 2 or not np.isfinite(point).all()):
                    raise ViewerError('A decoded observation is invalid.')
            observed_players += sum(point is not None for point in row['players'])
            observed_balls += row['ball'] is not None
        checked += len(rows)
        windows += 1
    durations.sort()
    result = {'status':'passed', 'source':'authorised local tactical ATD',
              'python':platform.python_version(), 'platform':platform.system(),
              'frames_checked':checked, 'slots':len(source.slot_ids), 'windows_checked':windows,
              'all_frame_indices_aligned':checked == source.n_frames,
              'prediction_csv_validated':labels is not None,
              'observed_player_samples':observed_players, 'observed_ball_frames':observed_balls,
              'ball_matches_reference_reader':True, 'observations_unchanged_by_estimation':True,
              'estimated_player_samples':estimated_samples, 'frames_with_player_estimates':estimated_frames,
              'estimated_window_ms_p50':round(statistics.median(estimate_durations), 3),
              'estimated_window_ms_p95':round(sorted(estimate_durations)[max(0, int(len(estimate_durations) * .95) - 1)], 3),
              'index_seconds':round(source.load_seconds, 3),
              'scan_seconds':round(time.perf_counter() - started, 3),
              'index_bytes':len(source.offsets) * source.offsets.itemsize,
              'window_ms_p50':round(statistics.median(durations), 3),
              'window_ms_p95':round(durations[max(0, int(len(durations) * .95) - 1)], 3),
              'public_gt_evaluated':False}
    if predictions is not None:
        result['prediction_sha256'] = hashlib.sha256(Path(predictions).read_bytes()).hexdigest()
    return result


def main():
    parser = argparse.ArgumentParser(description='Verify local tracking and an optional CSV; aggregates only.')
    parser.add_argument('--data-dir', required=True)
    parser.add_argument('--predictions')
    parser.add_argument('--out', help='Optional new local aggregate report; never overwrites a report.')
    args = parser.parse_args()
    try:
        paths = games.asset_paths(data_dir=args.data_dir)
        result = verify(paths['atd_meta'], paths['atd_raw'], args.predictions)
        output = json.dumps(result, indent=2, allow_nan=False)
        if args.out:
            with Path(args.out).open('x', encoding='utf-8') as handle:
                handle.write(output + '\n')
        print(output)
    except ViewerError as error:
        parser.exit(2, str(error) + '\n')
    except Exception:
        parser.exit(2, 'Local verification failed; input details are suppressed. Check paths and output permissions.\n')


if __name__ == '__main__':
    main()
