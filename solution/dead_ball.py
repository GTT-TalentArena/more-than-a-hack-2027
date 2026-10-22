"""P2 evidence from tactical geometry and automatic restart search windows. No GT."""
import argparse
import json
import math
from pathlib import Path

import numpy as np

import games
from solution.contract import check_tracking_frames
from solution.hold import apply_hold, load_observations, make_period_id
from starter.load_smart_tagging import load as load_events

DEFAULTS = dict(outside_margin_m=0.5, outside_frames=3, stationary_speed_m_s=0.5,
                stationary_frames=5, moving_speed_m_s=2.0, moving_frames=3,
                max_speed_m_s=45.0, max_dead_s=90.0, kickoff_radius_m=3.0,
                quiet_speed_m_s=1.5, min_players=6, dead_threshold=0.75)
TYPES = {"throw-in", "corner kick", "goal kick", "free kick",
         "kick off (after goal)", "kick off (start)"}


def validate_parameters(parameters):
    if set(parameters) != {"enabled", "max_hold_frames"} | set(DEFAULTS):
        raise ValueError("baseline_dead_ball requires enabled, max_hold_frames and all P2 thresholds")
    if type(parameters["enabled"]) is not bool:
        raise ValueError("enabled must be boolean")
    for key in ("max_hold_frames", "outside_frames", "stationary_frames", "moving_frames", "min_players"):
        if type(parameters[key]) is not int or parameters[key] < (0 if key == "max_hold_frames" else 1):
            raise ValueError(key + " must be a valid integer")
    for key in DEFAULTS:
        value = parameters[key]
        if isinstance(value, bool) or not isinstance(value, (int, float)) or not np.isfinite(value) or value <= 0:
            raise ValueError(key + " must be finite and positive")
    if not 0 < parameters["dead_threshold"] <= 1:
        raise ValueError("dead_threshold must be in (0, 1]")
    if not parameters["stationary_speed_m_s"] < parameters["moving_speed_m_s"] < parameters["max_speed_m_s"]:
        raise ValueError("Speed thresholds must be ordered")


def normalize(value):
    return " ".join(str(value or "").strip().casefold().split())


def normalize_events(events, n_frames):
    normalized = []
    counts = {}
    unknown_teams = 0
    for event in events:
        if normalize(event["code"]) != "set pieces":
            continue
        tags = {normalize(k): normalize(v) for k, v in event["tags"].items()}
        start, end = event["start_frame"], event["end_frame"]
        if type(start) is not int or type(end) is not int or not 0 <= start < end <= n_frames:
            raise ValueError("Set-piece interval outside tactical timeline")
        kind = tags.get("type", "")
        team = {"barcelona": "H", "atletic club": "A", "athletic club": "A"}.get(tags.get("team"))
        unknown_teams += team is None
        counts[kind or "unknown"] = counts.get(kind or "unknown", 0) + 1
        normalized.append(dict(start_frame=start, end_frame=end, kind=kind, team=team,
                               half=tags.get("half")))
    normalized.sort(key=lambda event: (event["start_frame"], event["end_frame"]))
    return normalized, dict(set_pieces=len(normalized), types=counts, unknown_teams=unknown_teams)


def load_geometry(data_dir, game=games.GAME):
    """Stream positions and provider speed aggregates; never print match rows."""
    raw = games.require(["atd_raw"], game=game, data_dir=data_dir)[0]
    n = games.source_frames(game=game)
    check_tracking_frames(raw, n)
    ball = np.full((n, 2), np.nan)
    median_speed = np.full(n, np.nan)
    player_count = np.zeros(n, dtype=np.int64)
    pitch = np.asarray(games.GAMES[game]["pitch"])
    with open(raw, encoding="utf-8-sig") as handle:
        for frame, line in enumerate(handle):
            _, players, ball_group = line.rstrip("\r\n").split(":")
            def fields(group):
                try:
                    values = [float(v) for v in group.split(",")[:3]]
                    return values if len(values) >= 2 and math.isfinite(values[0]) and math.isfinite(values[1]) else None
                except ValueError:
                    return None
            position = fields(ball_group)
            if position is not None:
                ball[frame] = np.asarray(position[:2]) * pitch
            speeds = []
            for group in players.split(";"):
                player = fields(group)
                if player is not None and len(player) == 3 and math.isfinite(player[2]) and player[2] >= 0:
                    speeds.append(player[2])
            player_count[frame] = len(speeds)
            if speeds:
                median_speed[frame] = np.median(speeds)
    return ball, np.all(np.isfinite(ball), axis=1), median_speed, player_count


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


def detect(ball_xy_m, ball_observed, period_id, events, fps, pitch,
           collective_speed=None, player_count=None, parameters=None):
    """Return aligned evidence and local-only candidates with half-open boundaries."""
    p = dict(DEFAULTS)
    if parameters:
        if set(parameters) - set(DEFAULTS):
            raise ValueError("Unknown P2 thresholds")
        p.update(parameters)
    validate_parameters(dict(p, enabled=True, max_hold_frames=25))
    ball = np.asarray(ball_xy_m, dtype=float)
    observed = np.asarray(ball_observed)
    periods = np.asarray(period_id)
    n = len(periods)
    if (ball.shape != (n, 2) or observed.shape != (n,) or observed.dtype != np.bool_
            or periods.ndim != 1 or not np.issubdtype(periods.dtype, np.integer) or np.any(periods < 0)
            or not np.all(np.isfinite(ball[observed])) or not np.all(np.isnan(ball[~observed]))):
        raise ValueError("Invalid geometry, masks or periods")
    if not np.isfinite(fps) or fps <= 0 or np.shape(pitch) != (2,) or not np.all(np.isfinite(pitch)) or np.any(np.asarray(pitch) <= 0):
        raise ValueError("Invalid fps or pitch")
    for optional in (collective_speed, player_count):
        if optional is not None and np.shape(optional) != (n,):
            raise ValueError("Collective evidence must align with frames")
    normalized, inventory = normalize_events(events, n)
    speed = np.full(n, np.nan)
    pairs = observed[1:] & observed[:-1] & (periods[1:] == periods[:-1]) & (periods[1:] > 0)
    indices = np.flatnonzero(pairs) + 1
    speed[indices] = np.linalg.norm(ball[indices] - ball[indices - 1], axis=1) * fps
    speed[speed > p["max_speed_m_s"]] = np.nan
    inside = observed & np.all((ball >= 0) & (ball <= np.asarray(pitch)), axis=1)
    outside = observed & np.any((ball < -p["outside_margin_m"]) | (ball > np.asarray(pitch) + p["outside_margin_m"]), axis=1)
    still = np.isfinite(speed) & (speed <= p["stationary_speed_m_s"])
    moving = inside & np.isfinite(speed) & (speed >= p["moving_speed_m_s"])
    dead = np.full(n, np.nan)
    restart = np.full(n, np.nan)
    # Valid negative evidence requires a measured movement, not mere missing data.
    dead[moving] = 0.0
    restart[np.isfinite(speed) & (periods > 0)] = 0.0
    candidates = []
    coverage = np.zeros(n, dtype=np.int64)
    for event in normalized:
        coverage[event["start_frame"]:event["end_frame"]] += 1
    for period in np.unique(periods[periods > 0]):
        frames = np.flatnonzero(periods == period)
        first, end = int(frames[0]), int(frames[-1]) + 1
        if not np.all(periods[first:end] == period):
            raise ValueError("A period must be contiguous")
        starts = []
        restarts = []
        initial_kickoff_seen = False
        for a, b in runs(outside[first:end]):
            if b - a >= p["outside_frames"]:
                starts.append((first + int(a), 0.85, "observed_exit", None))
        for a, b in runs(moving[first:end]):
            if b - a >= p["moving_frames"]:
                restarts.append((first + int(a), 0.8, "infield_motion"))
        for event in normalized:
            a, b = max(first, event["start_frame"]), min(end, event["end_frame"])
            if a >= b or event["kind"] not in TYPES:
                continue
            kind = event["kind"]
            zone = np.ones(n, dtype=bool)
            if kind.startswith("kick off"):
                zone = np.linalg.norm(ball - np.asarray(pitch) / 2, axis=1) <= p["kickoff_radius_m"]
            elif kind == "corner kick":
                zone = (np.minimum(abs(ball[:, 0]), abs(ball[:, 0] - pitch[0])) <= 5) & (np.minimum(abs(ball[:, 1]), abs(ball[:, 1] - pitch[1])) <= 5)
            elif kind == "throw-in":
                zone = np.minimum(abs(ball[:, 1]), abs(ball[:, 1] - pitch[1])) <= 3
            elif kind == "goal kick":
                zone = np.minimum(abs(ball[:, 0]), abs(ball[:, 0] - pitch[0])) <= 18
            if kind == "kick off (start)":
                if initial_kickoff_seen:
                    continue
                initial_kickoff_seen = True
                refined = None
                for s, t in runs(moving[a:b]):
                    r = a + int(s)
                    if t - s >= p["moving_frames"] and (zone[r] or (r > first and zone[r - 1])):
                        refined = r
                        break
                if refined is not None:
                    starts.append((first, 0.9, "tagged_preparation", refined))
                    restarts.append((refined, 0.9, "tagged_restart"))
                    stop = refined
                else:
                    stop = a
                    dead[first:stop] = np.fmax(dead[first:stop], 0.8)
                if stop > first or refined is not None:
                    candidates.append(dict(start_frame=first, end_frame=stop, restart_frame=refined,
                                           evidence="initial_kickoff_context", confidence=0.9 if refined is not None else 0.8,
                                           kind=kind, team=event["team"], period=int(period)))
                continue
            for s, t in runs((still & zone)[a:b]):
                s, t = a + int(s), a + int(t)
                if t - s < p["stationary_frames"]:
                    continue
                # Consecutive motion immediately after preparation; no derivative across a gap.
                r = t
                if r + p["moving_frames"] > b or not np.all(moving[r:r + p["moving_frames"]]):
                    continue
                begin = first if kind == "kick off (start)" else s
                quiet = (collective_speed is not None and player_count is not None
                         and player_count[t - 1] >= p["min_players"]
                         and np.isfinite(collective_speed[t - 1])
                         and collective_speed[t - 1] <= p["quiet_speed_m_s"])
                score = 0.9 if kind.startswith("kick off") else (0.8 if quiet else 0.6)
                starts.append((begin, score, "tagged_preparation", r))
                restarts.append((r, 0.9, "tagged_restart"))
                candidates.append(dict(start_frame=begin, end_frame=r, restart_frame=r,
                                       evidence="tagged_preparation", confidence=score,
                                       kind=kind, team=event["team"], period=int(period)))
                break
        for start, score, reason, tagged_restart in starts:
            # A movement before this start cannot release a later interruption.
            following = [(r, weight, why) for r, weight, why in restarts
                         if r > start and (tagged_restart is None or r == tagged_restart)]
            limit = (min(end, start + int(round(p["max_dead_s"] * fps)))
                     if tagged_restart is None else min(end, tagged_restart))
            if following:
                r, weight, why = min(following, key=lambda item: (item[0], -item[1]))
                stop = min(limit, r)
                if r <= limit:
                    restart[r] = max(float(np.nan_to_num(restart[r])), weight)
            else:
                stop = limit
            dead[start:stop] = np.fmax(dead[start:stop], score)
            if reason == "observed_exit":
                candidates.append(dict(start_frame=int(start), end_frame=int(stop),
                                       restart_frame=int(r) if following and r <= limit else None,
                                       evidence=reason, confidence=score, period=int(period)))
    dead[periods == 0] = np.nan
    restart[periods == 0] = np.nan
    signals = dict(dead_score=dead, restart_score=restart,
                   dead_valid=np.isfinite(dead), restart_valid=np.isfinite(restart))
    summary = dict(inventory, overlap_frames=int(np.sum(coverage > 1)),
                   dead_evidence_frames=int(np.sum(dead >= p["dead_threshold"])),
                   dead_valid_frames=int(np.sum(signals["dead_valid"])),
                   restart_candidates=int(np.sum(restart >= p["dead_threshold"])),
                   interruption_candidates=len(candidates),
                   conflicts=int(np.sum((dead >= p["dead_threshold"]) & (restart >= p["dead_threshold"]))),
                   note="Evidence only; no GT, whistle detection, stable player identity or quality guarantee")
    return signals, candidates, summary


def build(data_dir, parameters, game=games.GAME):
    validate_parameters(parameters)
    teams, observed, valid = load_observations(data_dir, game)
    periods = make_period_id(len(teams), games.half_video_blocks(game))
    if parameters["enabled"]:
        geometry, mask, collective, counts = load_geometry(data_dir, game)
        signals, candidates, summary = detect(geometry, mask, periods, load_events(game, data_dir),
                                     games.GAMES[game]["fps"], games.GAMES[game]["pitch"],
                                     collective, counts, {k: parameters[k] for k in DEFAULTS})
        summary["initial_kickoffs_refined"] = sum(c.get("kind") == "kick off (start)"
                                                  and c["restart_frame"] is not None for c in candidates)
        dead = signals["dead_valid"] & (signals["dead_score"] >= parameters["dead_threshold"])
        restart = signals["restart_valid"] & (signals["restart_score"] >= parameters["dead_threshold"])
        # Explicit restart wins in conflicts. Clear retained D even if H/A is unavailable.
        teams[dead & ~restart] = "D"
        valid[dead & ~restart] = True
        segments = periods.copy()
        offset = 0
        for frame in range(len(segments)):
            if restart[frame]:
                offset += int(np.max(periods)) + 1
            if segments[frame] > 0:
                segments[frame] += offset
        labels = apply_hold(teams, valid, segments, parameters["max_hold_frames"])
    else:
        labels = apply_hold(teams, valid, periods, parameters["max_hold_frames"])
        summary = dict(note="P2 disabled; exact P1 consumer", interruption_candidates=0)
    summary.update(enabled=parameters["enabled"], parameters=parameters,
                   dead_label_frames=int(np.sum(labels == "D")),
                   abstention_frames=int(np.sum((periods > 0) & (labels == "X"))))
    if game == "BAR-ATH" and len(labels) == games.GAMES[game]["n_video_frames"]:
        # Published FAQ anchor is diagnostic only; it never generates or changes labels.
        from starter.load_smart_tagging import KICKOFF_VIDEO_FRAMES
        start = games.half_video_blocks(game)[1][1]
        end = KICKOFF_VIDEO_FRAMES["2nd Half"]
        summary["second_half_pre_kickoff_dead_fraction"] = float(np.mean(labels[start:end] == "D"))
    return labels, summary


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", default=games.DATA_DIR)
    parser.add_argument("--out", required=True, help="Aggregate diagnostic JSON, without evaluation")
    args = parser.parse_args()
    ball, observed, collective, counts = load_geometry(args.data_dir)
    periods = make_period_id(len(ball), games.half_video_blocks(games.GAME))
    _, _, summary = detect(ball, observed, periods, load_events(data_dir=args.data_dir),
                           games.GAMES[games.GAME]["fps"], games.GAMES[games.GAME]["pitch"], collective, counts)
    path = Path(args.out)
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("x", encoding="utf-8") as handle:
        json.dump(summary, handle, indent=2, allow_nan=False)
    print("Aggregate P2 diagnostic written; no match rows or intervals printed.")


if __name__ == "__main__":
    main()
