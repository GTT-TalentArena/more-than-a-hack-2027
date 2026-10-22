"""P1: nearest-team observations plus bounded state retention, without ground truth."""
import argparse
import json
from pathlib import Path
import xml.etree.ElementTree as ET

import numpy as np

import games
from solution.contract import check_tracking_frames


def make_period_id(n_frames, blocks):
    """Map published inclusive video blocks to periods; 0 means outside play periods."""
    period_id = np.zeros(n_frames, dtype=np.int64)
    for period, first, last in blocks:
        if period <= 0 or not 0 <= first <= last < n_frames or np.any(period_id[first:last + 1]):
            raise ValueError("Invalid or overlapping period blocks")
        period_id[first:last + 1] = period
    return period_id


def apply_hold(observed_team, observation_valid, period_id, max_hold_frames=25):
    """Keep the last valid H/A/D for at most max_hold_frames; never infer D from absence.

    This is causal: a reappearance cannot rewrite a previous gap. X is explicit abstention,
    not a guarantee that the official temporal scorer stops carrying the last label.
    """
    observed_team = np.asarray(observed_team)
    observation_valid = np.asarray(observation_valid)
    period_id = np.asarray(period_id)
    if type(max_hold_frames) is not int or max_hold_frames < 0:
        raise ValueError("max_hold_frames must be an integer >= 0")
    if observed_team.ndim != 1 or observation_valid.shape != observed_team.shape or period_id.shape != observed_team.shape:
        raise ValueError("Inputs must be aligned one-dimensional arrays")
    if observation_valid.dtype != np.bool_ or not np.issubdtype(period_id.dtype, np.integer) or np.any(period_id < 0):
        raise ValueError("Expected a boolean validity mask and nonnegative integer periods")
    if not np.all(np.isin(observed_team[observation_valid], ["H", "A", "D"])):
        raise ValueError("Valid observations must be H/A/D")

    output_labels = np.full(len(observed_team), "X", dtype="<U1")
    last_valid_team = None
    missing_frames = 0
    current_period = 0
    for frame in range(len(observed_team)):
        period = period_id[frame]
        if period != current_period or period == 0:
            last_valid_team = None
            missing_frames = 0
            current_period = period
        if period == 0:
            continue
        if observation_valid[frame]:
            last_valid_team = observed_team[frame]
            missing_frames = 0
            output_labels[frame] = last_valid_team
        else:
            missing_frames += 1
            if last_valid_team is not None and missing_frames <= max_hold_frames:
                output_labels[frame] = last_valid_team
            else:
                last_valid_team = None
    return output_labels


def _finite_xy(group):
    try:
        fields = group.split(",")
        xy = np.array([float(fields[0]), float(fields[1])], dtype=np.float64)
    except (ValueError, IndexError):
        return None
    return xy if np.all(np.isfinite(xy)) else None


def load_observations(data_dir, game=games.GAME):
    """Stream tactical ATD: finite ball and at least one known-team player are required.

    Nearest player is only a baseline hypothesis, not confirmed football control. Unknown
    team slots are ignored; slot indices are not stable identities. No coordinates are imputed.
    """
    meta_path, raw_path = games.require(["atd_meta", "atd_raw"], game=game, data_dir=data_dir)
    n_frames = games.source_frames(game=game)
    check_tracking_frames(raw_path, n_frames)
    root = ET.parse(meta_path).getroot()
    teams = [team.get("id") for team in root.iter("Team")]
    if len(teams) != 2 or None in teams or teams[0] == teams[1]:
        raise ValueError("Expected two distinct teams in ATD metadata")
    team_labels = dict(zip(teams, ["H", "A"]))
    slot_team = [team_labels.get(player.get("teamId")) for player in root.iter("Player")]
    if not slot_team:
        raise ValueError("No player slots in ATD metadata")

    observed_team = np.full(n_frames, "X", dtype="<U1")
    ball_observed = np.zeros(n_frames, dtype=bool)
    observation_valid = np.zeros(n_frames, dtype=bool)
    pitch = np.asarray(games.GAMES[game]["pitch"], dtype=np.float64)
    with open(raw_path, encoding="utf-8-sig") as handle:
        for frame, line in enumerate(handle):
            _, players, ball_group = line.rstrip("\r\n").split(":")
            groups = players.split(";")
            if len(groups) != len(slot_team):
                raise ValueError("ATD player-slot count differs from metadata at frame {}".format(frame))
            ball_xy = _finite_xy(ball_group)
            if ball_xy is None:
                continue
            ball_observed[frame] = True
            best_distance = float("inf")
            for group, team in zip(groups, slot_team):
                player_xy = _finite_xy(group)
                if player_xy is None or team is None:
                    continue
                delta = (player_xy - ball_xy) * pitch
                distance = float(delta @ delta)
                if np.isfinite(distance) and distance < best_distance:
                    best_distance = distance
                    observed_team[frame] = team
            observation_valid[frame] = observed_team[frame] != "X"
    return observed_team, ball_observed, observation_valid


def _gap_stats(missing, fps):
    edges = np.diff(np.r_[False, missing, False].astype(np.int8))
    lengths = np.flatnonzero(edges == -1) - np.flatnonzero(edges == 1)
    return {
        "frames": int(len(missing)), "missing_frames": int(np.sum(missing)),
        "missing_percent": float(np.mean(missing) * 100) if len(missing) else 0.0,
        "gap_count": int(len(lengths)),
        "median_gap_s": float(np.median(lengths) / fps) if len(lengths) else 0.0,
        "p90_gap_s": float(np.percentile(lengths, 90) / fps) if len(lengths) else 0.0,
        "max_gap_s": float(np.max(lengths) / fps) if len(lengths) else 0.0,
        "gaps_up_to_1s": int(np.sum(lengths <= fps)),
        "gaps_over_1s_up_to_5s": int(np.sum((lengths > fps) & (lengths <= 5 * fps))),
        "gaps_over_5s": int(np.sum(lengths > 5 * fps)),
    }


def summarize_gaps(ball_observed, observation_valid, period_id, fps):
    """Aggregate only, per period; no coordinates, frame indices or real gap intervals."""
    return {
        "scope": "published_period_blocks; excludes halftime and outside-period frames",
        "periods": {
            str(int(period)): {
                "ball_absent": _gap_stats(~ball_observed[period_id == period], fps),
                "team_unavailable": _gap_stats(~observation_valid[period_id == period], fps),
            }
            for period in np.unique(period_id) if period > 0
        },
    }


def build(data_dir, max_hold_frames=25, game=games.GAME):
    observed_team, ball_observed, observation_valid = load_observations(data_dir, game)
    period_id = make_period_id(len(observed_team), games.half_video_blocks(game))
    labels = apply_hold(observed_team, observation_valid, period_id, max_hold_frames)
    summary = summarize_gaps(ball_observed, observation_valid, period_id, games.GAMES[game]["fps"])
    summary.update(
        max_hold_frames=max_hold_frames,
        retained_frames=int(np.sum((period_id > 0) & ~observation_valid & (labels != "X"))),
        abstention_percent_in_periods=float(np.mean(labels[period_id > 0] == "X") * 100)
        if np.any(period_id > 0) else 0.0,
        note="Nearest-player hypothesis, no P2 dead-ball evidence, no smoothing; not a quality claim",
    )
    return labels, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=games.DATA_DIR)
    parser.add_argument("--out", required=True, help="Aggregate JSON diagnostic, without evaluation")
    args = parser.parse_args()
    _, summary = build(args.data_dir)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, allow_nan=False)


if __name__ == "__main__":
    main()
