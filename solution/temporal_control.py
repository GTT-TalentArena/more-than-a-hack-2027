"""Experimental control evidence and exact H/A/D decoding. Never consumes GT."""
import xml.etree.ElementTree as ET

import numpy as np

import games
from solution import dead_ball
from solution.contract import check_tracking_frames
from solution.hold import _finite_xy, make_period_id

DEFAULTS = dict(control_radius_m=2.0, distance_margin_m=0.75,
                max_control_speed_m_s=8.0, confirmation_frames=5,
                switch_cost=8.0, dead_weight=2.0, unknown_dead_cost=0.05)


def validate_parameters(parameters):
    if set(parameters) != set(DEFAULTS) | {"p2_enabled"}:
        raise ValueError("temporal_control requires all documented parameters")
    if type(parameters["p2_enabled"]) is not bool:
        raise ValueError("p2_enabled must be boolean")
    for name in DEFAULTS:
        value = parameters[name]
        if (isinstance(value, bool) or not isinstance(value, (int, float))
                or not np.isfinite(value) or value <= 0):
            raise ValueError(name + " must be finite and positive")
    if type(parameters["confirmation_frames"]) is not int:
        raise ValueError("confirmation_frames must be an integer")


def validate_periods(periods):
    periods = np.asarray(periods)
    if periods.ndim != 1 or not np.issubdtype(periods.dtype, np.integer) or np.any(periods < 0):
        raise ValueError("Expected nonnegative integer periods")
    for period in np.unique(periods[periods > 0]):
        indices = np.flatnonzero(periods == period)
        if indices[-1] - indices[0] + 1 != len(indices):
            raise ValueError("Each period must be contiguous")
    return periods


def ball_speed(ball, observed, periods, fps):
    ball, observed = np.asarray(ball, float), np.asarray(observed)
    n = len(periods)
    if (ball.shape != (n, 2) or observed.shape != (n,) or observed.dtype != np.bool_
            or not np.all(np.isfinite(ball[observed]))
            or not np.all(np.isnan(ball[~observed])) or not np.isfinite(fps) or fps <= 0):
        raise ValueError("Invalid ball geometry, observation mask or fps")
    speed = np.full(n, np.nan)
    pairs = observed[1:] & observed[:-1] & (periods[1:] == periods[:-1]) & (periods[1:] > 0)
    indices = np.flatnonzero(pairs) + 1
    speed[indices] = np.linalg.norm(ball[indices] - ball[indices - 1], axis=1) * fps
    return speed


def control_evidence(distances, speed, periods, parameters):
    """Confirm uninterrupted control and backdate evidence to its first observation."""
    validate_parameters(parameters)
    periods = validate_periods(periods)
    distances, speed = np.asarray(distances, float), np.asarray(speed, float)
    if distances.shape != (len(periods), 2) or speed.shape != periods.shape:
        raise ValueError("Control observations must align with frames")
    if np.any(distances[np.isfinite(distances)] < 0) or np.any(speed[np.isfinite(speed)] < 0):
        raise ValueError("Distances and speeds cannot be negative")
    valid = np.all(np.isfinite(distances), axis=1) & np.isfinite(speed) & (periods > 0)
    winner = np.argmin(np.where(np.isfinite(distances), distances, np.inf), axis=1)
    nearest = np.min(distances, axis=1)
    margin = np.abs(distances[:, 0] - distances[:, 1])
    valid &= ((nearest <= parameters["control_radius_m"])
              & (margin >= parameters["distance_margin_m"])
              & (speed <= parameters["max_control_speed_m_s"]))
    evidence = np.zeros((len(periods), 2))
    for period in np.unique(periods[periods > 0]):
        for team in (0, 1):
            for start, end in dead_ball.runs(valid & (winner == team) & (periods == period)):
                if end - start >= parameters["confirmation_frames"]:
                    evidence[start:end, team] = 1.0
    return evidence


def decode(emissions, switch_cost):
    """Exact penalized segmentation; team ties delay transitions through neutral gaps."""
    emissions = np.asarray(emissions, float)
    if (emissions.ndim != 2 or emissions.shape[1] != 3 or np.any(np.isnan(emissions))
            or np.any(np.isposinf(emissions)) or isinstance(switch_cost, bool)
            or not np.isfinite(switch_cost) or switch_cost < 0):
        raise ValueError("Expected three finite/forbidden emissions and a nonnegative cost")
    n = len(emissions)
    if not n:
        return np.empty(0, dtype=np.int8)
    pointers = np.zeros((n, 3), dtype=np.int8)
    score = emissions[0].copy()
    # Prefer a transition over staying on exact ties for H/A, so ownership in a
    # neutral gap remains with the last confirmed team. D ties start earlier.
    orders = np.array([[2, 1, 0], [2, 0, 1], [2, 0, 1]])
    penalties = switch_cost * (np.ones((3, 3)) - np.eye(3))
    for frame in range(1, n):
        choices = score[:, None] - penalties
        best = np.argmax(np.take_along_axis(choices.T, orders, axis=1), axis=1)
        predecessors = orders[np.arange(3), best]
        pointers[frame] = predecessors
        score = choices[predecessors, np.arange(3)] + emissions[frame]
    if not np.any(np.isfinite(score)):
        raise ValueError("No feasible state sequence")
    states = np.empty(n, dtype=np.int8)
    states[-1] = np.argmax(score)
    for frame in range(n - 1, 0, -1):
        states[frame - 1] = pointers[frame, states[frame]]
    return states


def predict(distances, ball, observed, periods, fps, signals, parameters):
    validate_parameters(parameters)
    periods = validate_periods(periods)
    speed = ball_speed(ball, observed, periods, fps)
    control = control_evidence(distances, speed, periods, parameters)
    emissions = np.column_stack((control, np.full(len(periods), -parameters["unknown_dead_cost"])))
    if parameters["p2_enabled"]:
        for key in ("dead_score", "dead_valid", "restart_score", "restart_valid"):
            if key not in signals or np.shape(signals[key]) != periods.shape:
                raise ValueError("P2 signals must align with frames")
        for name in ("dead", "restart"):
            scores, valid = np.asarray(signals[name + "_score"]), np.asarray(signals[name + "_valid"])
            if (valid.dtype != np.bool_ or not np.all(np.isnan(scores[~valid]))
                    or not np.all(np.isfinite(scores[valid]))
                    or np.any((scores[valid] < 0) | (scores[valid] > 1))):
                raise ValueError("Invalid P2 scores or masks")
        dead = signals["dead_valid"] & (signals["dead_score"] >= dead_ball.DEFAULTS["dead_threshold"])
        live = signals["dead_valid"] & (signals["dead_score"] == 0)
        emissions[dead, 2] = parameters["dead_weight"]
        emissions[live, 2] = -parameters["dead_weight"]
        restart = signals["restart_valid"] & (signals["restart_score"] >= dead_ball.DEFAULTS["dead_threshold"])
        emissions[restart, 2] = -np.inf
    labels = np.full(len(periods), "X", dtype="<U1")
    for period in np.unique(periods[periods > 0]):
        indices = np.flatnonzero(periods == period)
        states = decode(emissions[indices], parameters["switch_cost"])
        decoded = np.array(list("HAD"))[states]
        seen_control = np.cumsum(np.any(control[indices] > 0, axis=1)) > 0
        decoded[~seen_control & (decoded != "D")] = "X"
        labels[indices] = decoded
    summary = dict(control_evidence_frames=int(np.sum(np.any(control > 0, axis=1))),
                   control_coverage_in_periods=float(np.sum(np.any(control > 0, axis=1)) / max(1, np.sum(periods > 0))),
                   state_changes=int(np.sum((labels[1:] != labels[:-1]) & (periods[1:] == periods[:-1]) & (periods[1:] > 0))),
                   dead_label_frames=int(np.sum(labels == "D")),
                   abstention_frames=int(np.sum((labels == "X") & (periods > 0))),
                   parameters=parameters, note="Experimental physical control rules and exact temporal decoding; no GT or calibrated probabilities")
    return labels, summary


def load_features(data_dir, game=games.GAME):
    """Streaming team distances and P2 geometry, without retaining player identities."""
    meta, raw = games.require(["atd_meta", "atd_raw"], game=game, data_dir=data_dir)
    n = games.source_frames(game=game)
    check_tracking_frames(raw, n)
    root = ET.parse(meta).getroot()
    teams = [team.get("id") for team in root.iter("Team")]
    if len(teams) != 2 or None in teams or teams[0] == teams[1]:
        raise ValueError("Expected two distinct teams")
    slots = [teams.index(p.get("teamId")) if p.get("teamId") in teams else -1 for p in root.iter("Player")]
    if not slots:
        raise ValueError("No player slots")
    distances, ball = np.full((n, 2), np.nan), np.full((n, 2), np.nan)
    collective, counts = np.full(n, np.nan), np.zeros(n, dtype=np.int64)
    pitch = np.asarray(games.GAMES[game]["pitch"])
    with open(raw, encoding="utf-8-sig") as handle:
        for frame, line in enumerate(handle):
            _, players, ball_group = line.rstrip("\r\n").split(":")
            groups = players.split(";")
            if len(groups) != len(slots):
                raise ValueError("Player-slot count differs from metadata")
            position = _finite_xy(ball_group)
            if position is not None:
                ball[frame] = position * pitch
            nearest, speeds = [np.inf, np.inf], []
            for group, team in zip(groups, slots):
                xy = _finite_xy(group)
                if xy is None:
                    continue
                fields = group.split(",")
                if len(fields) >= 3:
                    try:
                        speed = float(fields[2])
                        if np.isfinite(speed) and speed >= 0:
                            speeds.append(speed)
                    except ValueError:
                        pass
                if position is not None and team >= 0:
                    nearest[team] = min(nearest[team], float(np.linalg.norm((xy - position) * pitch)))
            for team in (0, 1):
                if np.isfinite(nearest[team]):
                    distances[frame, team] = nearest[team]
            counts[frame] = len(speeds)
            if speeds:
                collective[frame] = np.median(speeds)
    return distances, ball, np.all(np.isfinite(ball), axis=1), collective, counts


def build(data_dir, parameters, game=games.GAME):
    validate_parameters(parameters)
    distances, ball, observed, collective, counts = load_features(data_dir, game)
    periods = make_period_id(len(ball), games.half_video_blocks(game))
    signals, p2_summary = {}, {}
    if parameters["p2_enabled"]:
        signals, _, p2_summary = dead_ball.detect(ball, observed, periods,
            dead_ball.load_events(game, data_dir), games.GAMES[game]["fps"],
            games.GAMES[game]["pitch"], collective, counts)
    labels, summary = predict(distances, ball, observed, periods,
                              games.GAMES[game]["fps"], signals, parameters)
    summary["p2"] = p2_summary
    return labels, summary
