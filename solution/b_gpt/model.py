"""Control evidence + stoppage evidence + frame-resolution constrained Viterbi.

Scores are heuristic energies, not calibrated probabilities. No match labels are read.
"""

import unicodedata
import warnings
import numpy as np

from .config import CONFIG


def mean_window(values, before, after):
    """Finite-value mean on [t-before, t+after], with truncated edge windows."""
    values = np.asarray(values, dtype=np.float64)
    valid = np.isfinite(values)
    total = np.r_[0., np.cumsum(np.where(valid, values, 0.))]
    count = np.r_[0, np.cumsum(valid)]
    frames = np.arange(len(values))
    lo = np.maximum(0, frames - before)
    hi = np.minimum(len(values), frames + after + 1)
    return np.divide(total[hi] - total[lo], count[hi] - count[lo],
                     out=np.zeros(len(values)), where=(count[hi] != count[lo]))


def runs(mask):
    edges = np.diff(np.r_[False, mask, False].astype(np.int8))
    return zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1))


def persistent(mask, minimum):
    out = np.zeros(len(mask), dtype=bool)
    for a, b in runs(mask):
        if b - a >= minimum:
            out[a:b] = True
    return out


def clean_ball(raw, fps, pitch, cfg=CONFIG):
    ball = raw[:, :2].astype(np.float64).copy()
    valid = np.isfinite(ball).all(axis=1)
    valid &= ((ball >= -20) & (ball <= np.asarray(pitch) + 20)).all(axis=1)
    ids = np.flatnonzero(valid)
    # Reject isolated teleports, but do not extrapolate or smooth real touches.
    if len(ids) >= 3:
        a, b, c = ids[:-2], ids[1:-1], ids[2:]
        ab = np.linalg.norm(ball[b] - ball[a], axis=1) * fps / (b - a)
        bc = np.linalg.norm(ball[c] - ball[b], axis=1) * fps / (c - b)
        ac = np.linalg.norm(ball[c] - ball[a], axis=1) * fps / (c - a)
        bad = (ab > cfg.max_ball_mps) & (bc > cfg.max_ball_mps)
        bad &= (ac < cfg.max_ball_mps / 2) & ((c - a) <= fps)
        valid[b[bad]] = False
    ball[~valid] = np.nan
    reliability = valid.astype(float)
    ids = np.flatnonzero(valid)
    max_gap = round(cfg.interpolation_s * fps)
    for a, b in zip(ids[:-1], ids[1:]):
        if 1 < b - a <= max_gap + 1:
            speed = np.linalg.norm(ball[b] - ball[a]) * fps / (b - a)
            if speed <= 35:
                alpha = np.arange(1, b - a)[:, None] / (b - a)
                ball[a + 1:b] = ball[a] + alpha * (ball[b] - ball[a])
                reliability[a + 1:b] = 0.3
    # A 0.24 s chord suppresses coordinate jitter; exported speed is only fallback.
    lag = max(1, round(0.12 * fps))
    lo = np.maximum(0, np.arange(len(ball)) - lag)
    hi = np.minimum(len(ball) - 1, np.arange(len(ball)) + lag)
    speed = np.linalg.norm(ball[hi] - ball[lo], axis=1) * fps / np.maximum(hi - lo, 1)
    raw_speed = raw[:, 2].astype(float)
    raw_speed[(raw_speed < 0) | (raw_speed > cfg.max_ball_mps)] = np.nan
    speed = np.where(np.isfinite(speed), speed, raw_speed)
    speed[(reliability == 0) | (speed > cfg.max_ball_mps)] = np.nan
    return ball, reliability, speed


def features(ball_raw, players, teams, fps, pitch, cfg=CONFIG):
    ball, quality, speed = clean_ball(ball_raw, fps, pitch, cfg)
    n = len(ball)
    nearest = np.full((n, 2), np.inf)
    activity = np.full(n, np.nan)
    count = np.zeros(n, dtype=int)
    for a in range(0, n, 4096):
        b = min(n, a + 4096)
        pos = players[a:b, :, :2]
        valid = np.isfinite(pos).all(axis=2)
        valid &= ((pos >= -5) & (pos <= np.asarray(pitch) + 5)).all(axis=2)
        dist = np.linalg.norm(pos - ball[a:b, None, :], axis=2)
        dist[~valid | ~np.isfinite(dist)] = np.inf
        for team in (0, 1):
            nearest[a:b, team] = np.min(dist[:, teams == team], axis=1)
        count[a:b] = valid.sum(axis=1)
        ps = players[a:b, :, 2].astype(float).copy()
        ps[(~valid) | (ps < 0) | (ps > 12)] = np.nan
        with warnings.catch_warnings():
            warnings.simplefilter("ignore", RuntimeWarning)
            activity[a:b] = np.nanmedian(ps, axis=1)
    activity[count < 8] = np.nan
    # Low-pass collective motion only; team/contact boundaries remain at 25 Hz.
    activity = np.where(np.isfinite(activity),
                        mean_window(activity, round(.5 * fps), round(.5 * fps)), np.nan)
    closest = np.min(nearest, axis=1)
    delta = np.zeros(n)
    both = np.isfinite(nearest).all(axis=1)
    delta[both] = nearest[both, 1] - nearest[both, 0]
    delta[np.isfinite(nearest[:, 0]) & ~np.isfinite(nearest[:, 1])] = 3
    delta[np.isfinite(nearest[:, 1]) & ~np.isfinite(nearest[:, 0])] = -3
    distance_quality = 1 / (1 + (closest / cfg.control_radius_m) ** 4)
    velocity_quality = .3 + .7 / (1 + (np.nan_to_num(speed, nan=12) / cfg.fast_ball_mps) ** 2)
    control = quality * distance_quality * np.tanh(delta / cfg.separation_m) * velocity_quality
    # Ball outside: no player can acquire live control there.
    outside = ((ball < -cfg.outside_margin_m) |
               (ball > np.asarray(pitch) + cfg.outside_margin_m)).any(axis=1)
    inside = ((ball >= 0) & (ball <= np.asarray(pitch))).all(axis=1)
    # Metres beyond the nearest line (0 inside); NaN where the ball is not located.
    beyond = np.max(np.concatenate([-ball, ball - np.asarray(pitch), np.zeros((n, 1))], axis=1), axis=1)
    # v3: signed distance to the nearest line (positive inside, negative outside).
    line_dist = np.min(np.concatenate([ball, np.asarray(pitch) - ball], axis=1), axis=1)
    control[outside] = 0
    return dict(ball=ball, quality=quality, speed=speed, activity=activity, count=count,
                nearest=nearest, control=control, outside=outside, inside=inside, beyond=beyond,
                line_dist=line_dist, pitch=np.asarray(pitch, dtype=np.float64))


def out_of_play_gaps(f, fps, cfg=CONFIG):
    """v1 (Claude): frames where the ball is lost right after clearly leaving the pitch.

    A ball that has left the field cannot re-enter play without a restart (Laws 9, 15-17),
    so the occlusion that follows a clear exit is a stoppage even if players keep moving,
    as they do at throw-ins and goal kicks. The gap ends when the ball is located again,
    and never lasts longer than the restart look-back used elsewhere.
    """
    observed = f["quality"] == 1
    exit_ = observed & f["outside"] & (
        persistent(f["outside"] & observed, max(2, round(.16 * fps)))
        | (np.nan_to_num(f["beyond"], nan=0.) > cfg.clear_out_m))
    gaps = np.zeros(len(observed), bool)
    cap = round(cfg.stop_lookback_s * fps)
    for a, b in runs(~observed):
        if a > 0 and exit_[a - 1]:
            gaps[a:min(b, a + cap)] = True
    return gaps


def normalise_name(name):
    return "".join(c for c in unicodedata.normalize("NFKD", name.casefold()) if c.isalnum())


def event_team(value, team_names):
    name = normalise_name(value)
    if name in ("", "na", "none", "unknown"):
        return None
    names = [normalise_name(t) for t in team_names]
    if name in names:
        return names.index(name)
    # These are public naming aliases, not tracking-slot identities.
    if "barcelona" in name:
        return 0
    if "athletic" in name or "atletic" in name:
        return 1
    return None


def tag_priors(events, n, names, fps):
    votes = np.zeros((n, 2))
    for event in events:
        code = event["code"]
        if code in ("set pieces", "goals"):
            continue
        team = event_team(event["tags"].get("team", ""), names)
        if team is None:
            continue
        if code.startswith("defend") or code == "defensive transition":
            team = 1 - team
        elif code not in {"build up", "progression", "attacking transition", "long ball",
                          "creating chances", "ball in final third", "ball in the box",
                          "players in the box"}:
            continue
        a, b = max(0, event["start"]), min(n, event["end"])
        if b <= a:
            continue
        # Correlated phases do not count as independent votes. Taper uncertain edges.
        ramp = min(fps, max(1, (b - a) // 3))
        envelope = np.minimum(1., np.minimum(np.arange(b - a) + 1,
                                            np.arange(b - a, 0, -1)) / ramp)
        if code == "players in the box":
            envelope *= .35
        votes[a:b, team] = np.maximum(votes[a:b, team], envelope)
    return votes[:, 0] - votes[:, 1], np.max(votes, axis=1)


def restart_like_gaps(f, fps, cfg=CONFIG):
    """v3 (Claude): ball-less stretches (>= medium_gap_s, players tracked) that look like a
    stoppage: the ball was lost at a line, or comes back placed still or at a line, or the
    gap is longer than any live sequence. A ball shielded by a player with his back to the
    camera, or lost in flight, comes back moving inside the pitch and is left as live play.
    """
    observed = f["quality"] == 1
    tracked = f["count"] >= 8
    n = len(observed)
    dead = np.zeros(n, bool)
    look = max(1, round(.5 * fps))
    for a, b in runs(~observed):
        if b - a < round(cfg.medium_gap_s * fps) or tracked[a:b].mean() <= .5:
            continue  # short occlusion, or ball and players missing together (data outage)
        lost_at_line = a > 0 and observed[a - 1] and f["line_dist"][a - 1] <= cfg.clear_out_m
        after = np.arange(b, min(n, b + look))
        after = after[observed[after]]
        back_at_line = len(after) > 0 and f["line_dist"][after[0]] <= cfg.clear_out_m
        speeds = f["speed"][after]
        speeds = speeds[np.isfinite(speeds)]
        back_still = len(speeds) > 0 and np.median(speeds) < .65
        very_long = b - a >= round(cfg.very_long_gap_s * fps)
        if lost_at_line or back_at_line or back_still or very_long:
            dead[a:b] = True
    return dead


def stoppage_evidence(f, phase, fps, cfg=CONFIG):
    quality, speed, activity = f["quality"], f["speed"], f["activity"]
    seen = quality > 0
    quiet_players = np.isfinite(activity) & (activity < 1.2)
    stationary = seen & np.isfinite(speed) & (speed < .65)
    outside = persistent(f["outside"] & (quality == 1), max(2, round(.16 * fps)))
    still = persistent(stationary & quiet_players, round(2.0 * fps))
    # Missingness alone has exactly zero dead-ball evidence.
    quiet_missing = persistent(~seen & quiet_players, round(3.0 * fps))
    # v1 (Claude): occlusion after the ball has left the pitch, whatever the players do.
    out_gap = out_of_play_gaps(f, fps, cfg)
    # v3 (Claude): replaces v2's "every long gap is a stoppage" (too many false D in the
    # public window): only gaps that start or end like a restart (see restart_like_gaps).
    restart_gap = restart_like_gaps(f, fps, cfg)
    moving = seen & f["inside"] & np.isfinite(speed) & (speed > 2.0)
    running = np.isfinite(activity) & (activity > 2.0)
    # The out-of-play gap carries the same weight as a ball seen outside, and running
    # players do not count against it: they move during throw-ins and goal kicks.
    gap = out_gap | restart_gap
    margin = (3.8 * (outside | gap) + 1.6 * still
              + 1.0 * (quiet_missing & ~gap)
              - 1.6 * moving - .65 * (running & ~gap) - .35 * seen - .35 * phase)
    seed = outside | still | quiet_missing | gap
    live = moving | (running & ~outside & ~gap) | ((phase > .65) & ~seed)
    return margin, seed, live, out_gap


def restart_candidates(events, f, margin, fps, cfg=CONFIG):
    """One estimated kick per automatic set-piece interval, with uncertainty retained."""
    n = len(margin)
    moving = ((f["speed"] > 1.5) & f["inside"] & (f["quality"] > 0)).astype(float)
    quiet = ((f["quality"] == 0) | (f["speed"] < .8) | f["outside"]).astype(float)
    before_quiet = mean_window(quiet, round(2 * fps), 0)
    after_moving = mean_window(moving, 0, round(.6 * fps))
    before_moving = mean_window(moving, round(.6 * fps), 0)
    activity = np.nan_to_num(f["activity"], nan=1.5)
    activity_gain = np.maximum(0, mean_window(activity, 0, fps) - mean_window(activity, fps, 0))
    result = []
    for event in events:
        if event["code"] != "set pieces" or event["end"] <= 0 or event["start"] >= n:
            continue
        a = max(0, event["start"] - round(cfg.restart_search_s * fps))
        b = min(n, event["end"] + round(cfg.restart_search_s * fps))
        ids = np.arange(a, b)
        if len(ids) == 0:
            continue
        midpoint = np.clip((event["start"] + event["end"]) // 2, a, b - 1)
        onset = before_quiet[ids] * after_moving[ids] - before_moving[ids] * .6
        score = onset + .15 * np.clip(activity_gain[ids], 0, 2)
        score -= .12 * np.abs(ids - midpoint) / max(fps, (b - a) / 2)
        kick = int(ids[np.argmax(score)])
        confidence = float(np.clip(np.max(score), 0, 1))
        if confidence < .25:
            # No convincing kinematic boundary: retain midpoint as weak tag information.
            kick = int(midpoint)
        else:
            # Locate the first sustained movement edge near the selected onset.
            lo, hi = max(a, kick - round(.5 * fps)), min(b, kick + round(.6 * fps))
            edges = np.flatnonzero((moving[lo:hi] > 0) &
                                   (np.r_[0., moving][lo:hi] == 0)) + lo
            if len(edges):
                kick = int(edges[np.argmin(np.abs(edges - kick))])
        if (event["tags"].get("type", "") == "kick off (start)"
                and event["start"] <= 0 < event["end"]
                and np.mean(moving[:min(n, max(1, fps // 2))]) > .5):
            # A half may start exactly at the kick, removing its stationary prehistory.
            # Do not fabricate a lead-in just because the tag midpoint is later.
            kick, confidence = 0, max(confidence, .6)
        result.append((kick, confidence, event))
    return sorted(result, key=lambda v: v[0])


def build_evidence(f, events, names, fps, cfg=CONFIG):
    n = len(f["control"])
    tag, phase = tag_priors(events, n, names, fps)
    margin, dead_seed, live, out_gap = stoppage_evidence(f, phase, fps, cfg)
    restarts = restart_candidates(events, f, margin, fps, cfg)
    restart_live = np.zeros(n, bool)
    kickoff_seen = False
    supported = 0
    for kick, confidence, event in restarts:
        kind = event["tags"].get("type", "")
        is_start = kind == "kick off (start)" and not kickoff_seen
        if is_start:
            kickoff_seen = True
        lo = max(0, kick - round(cfg.stop_lookback_s * fps))
        # Search for a suffix with stoppage evidence, anchored on a likely restart.
        # Negative evidence from live motion limits how far it can extend backwards.
        backward = np.cumsum((margin[lo:kick] + .10)[::-1])
        start = kick
        if len(backward):
            length = int(np.argmax(backward)) + 1
            if backward[length - 1] / fps > .8 and length >= round(.6 * fps):
                start = kick - length
        if is_start:
            # The first automatically tagged start kick defines the lead-in of this half.
            # No kickoff frame constant or manually labelled interval is used.
            start = 0
        if start < kick and (confidence >= .25 or is_start):
            margin[start:kick] = np.maximum(margin[start:kick], 2.0)
            dead_seed[start:kick] = True
            live[start:kick] = False
            supported += 1
        if confidence >= .25 or is_start:
            end = min(n, kick + round(.6 * fps))
            restart_live[kick:end] = True
            margin[kick:end] = np.minimum(margin[kick:end], -2.0)
            team = event_team(event["tags"].get("team", ""), names)
            if team is not None:
                # Weak seed only; a conflicting close control observation wins.
                tag[kick:end] = 1 if team == 0 else -1
    control = f["control"]
    signed = cfg.team_evidence * control + cfg.tag_evidence * tag
    # Relative team evidence must not become a spurious alive/dead prior.
    scores = np.zeros((n, 3))
    scores[:, 0] = np.minimum(signed, 0)
    scores[:, 1] = -np.maximum(signed, 0)
    scores[:, 2] = margin
    # Changes need an observation of the DESTINATION, not just a future Viterbi preference.
    # This keeps ownership with the last controller during flight/occlusion.
    acquire = np.zeros((n, 2), bool)
    acquire[:, 0] = (control > .12) | ((tag > .65) & (np.abs(control) < .12))
    acquire[:, 1] = (control < -.12) | ((tag < -.65) & (np.abs(control) < .12))
    live |= restart_live
    # Unknown restart team (throw-in N/A): use the next available control within 2 s.
    # This is a prior for D exit only; it never invents a team change during open play.
    restart_team = np.zeros((n, 2), bool)
    for kick, confidence, event in restarts:
        if confidence < .25 and event["tags"].get("type", "") != "kick off (start)":
            continue
        end = min(n, kick + 2 * fps)
        candidates = np.flatnonzero(np.abs(control[kick:end]) > .12)
        team = event_team(event["tags"].get("team", ""), names)
        if len(candidates):
            team = 0 if control[kick + candidates[0]] > 0 else 1
        if team is not None:
            restart_team[kick:min(n, kick + round(.6 * fps)), team] = True
    return scores / fps, acquire, dead_seed, live, restart_team, supported, int(out_gap.sum())


def decode(scores, acquire, dead_seed, live, restart_team, cfg=CONFIG):
    """Exact 3-state max-sum DP, O(frames). No downsampling or duration truncation."""
    n = len(scores)
    back = np.zeros((n, 3), dtype=np.int8)
    previous = scores[0].copy()
    # Marginal tie preference for live, with no special home-share prior.
    previous[2] -= 1e-9
    for t in range(1, n):
        h, a, d = previous
        new = np.empty(3)
        for team, own, other in ((0, h, a), (1, a, h)):
            values = [own, -np.inf, -np.inf]
            if acquire[t, team]:
                values[1] = other - cfg.team_switch_cost
            if live[t] and (acquire[t, team] or restart_team[t, team]):
                values[2] = d - cfg.dead_switch_cost
            best = int(np.argmax(values))  # ties prefer staying, not an early handover
            back[t, team] = (team, 1 - team, 2)[best]
            new[team] = values[best] + scores[t, team]
        values = [d, -np.inf, -np.inf]
        if dead_seed[t]:
            values[1:] = [h - cfg.dead_switch_cost, a - cfg.dead_switch_cost]
        best = int(np.argmax(values))
        back[t, 2] = (2, 0, 1)[best]
        new[2] = values[best] + scores[t, 2]
        previous = new - np.max(new)
    result = np.empty(n, dtype=np.int8)
    result[-1] = int(np.argmax(previous))
    for t in range(n - 1, 0, -1):
        result[t - 1] = back[t, result[t]]
    return result


def merge_flip_backs(states, fps, cfg=CONFIG):
    """v4 (Claude): a spell of one team shorter than min_change_s between two spells of the
    other team, with no stoppage in between, goes back to the team that had the ball: a touch,
    a deflection or a duel without control is not a change of possession (CHALLENGE.md). The
    shortest one is merged first, so a chain of flickers collapses into the surrounding team.
    Spells next to a stoppage are never touched: after a restart there is a clear possessor."""
    states = states.copy()
    limit = round(cfg.min_change_s * fps)
    merged = 0
    while True:
        starts = np.r_[0, np.flatnonzero(np.diff(states)) + 1]
        ends = np.r_[starts[1:], len(states)]
        values, lengths = states[starts], ends - starts
        inner = np.arange(1, len(values) - 1)
        candidate = ((values[inner] != 2) & (values[inner - 1] != 2)
                     & (values[inner - 1] == values[inner + 1]) & (lengths[inner] < limit))
        if not candidate.any():
            return states, merged
        i = inner[candidate][np.argmin(lengths[inner][candidate])]
        states[starts[i]:ends[i]] = values[i - 1]
        merged += 1


# v1 (Claude): GT-free diagnostics to locate under-detected stoppages. Aggregates only
# (counts and minutes); they never change a label.
GAP_BINS_S = (0, 1, 3, 5, 10, 30)
SLOW_PLAYERS_MPS = (1.0, 1.5, 2.0)


def dead_time_diagnostics(f, states, fps):
    live = states != 2
    seen = f["quality"] > 0
    out = {}
    lengths = [(a, b) for a, b in runs(~seen)]
    for i, lo in enumerate(GAP_BINS_S):
        hi = GAP_BINS_S[i + 1] if i + 1 < len(GAP_BINS_S) else None
        sel = [(a, b) for a, b in lengths if (b - a) >= lo * fps and (hi is None or (b - a) < hi * fps)]
        key = "ball_missing_{}s{}".format(lo, "_{}s".format(hi) if hi else "_plus")
        out[key] = dict(runs=len(sel),
                        minutes=round(sum(b - a for a, b in sel) / fps / 60, 2),
                        minutes_labelled_live=round(sum(int(live[a:b].sum()) for a, b in sel) / fps / 60, 2))
    ball_slow = ~seen | (np.isfinite(f["speed"]) & (f["speed"] < 2.0))
    for limit in SLOW_PLAYERS_MPS:
        slow = persistent(ball_slow & np.isfinite(f["activity"]) & (f["activity"] < limit), round(3 * fps))
        out["slow_phase_players_below_{}mps".format(limit)] = dict(
            minutes=round(slow.sum() / fps / 60, 2),
            minutes_labelled_live=round((slow & live).sum() / fps / 60, 2))
    return out


def merge_diagnostics(total, part):
    for key, values in part.items():
        bucket = total.setdefault(key, {})
        for name, value in values.items():
            bucket[name] = round(bucket.get(name, 0) + value, 2)


# v4 (Claude, effort max): GT-free diagnostics that size each proposal of
# prompts/confrontacion/b-gpt-claude/analisis-v4.md before it is implemented.
# Aggregates only (counts, minutes, seconds); they never change a label.
PENALTY_DEPTH_M, PENALTY_HALF_WIDTH_M = 16.5, 20.16
GOAL_AREA_DEPTH_M, GOAL_AREA_HALF_WIDTH_M = 5.5, 9.16
DUEL_RADIUS_M = 1.0  # Vidal-Codina et al. (2022): duel zone around the ball
ZONES = ("open", "near_line", "keeper_zone", "goal_area", "outside")
SIDES = ("goal_line_low_x", "goal_line_high_x", "touchline_low_y", "touchline_high_y")


def ball_zones(ball, pitch):
    """Pitch zone of each located ball; empty string where the ball is not located.
    keeper_zone = penalty area outside the goal area, where a goalkeeper may hold the ball."""
    length, width = pitch
    x, y = ball[:, 0], ball[:, 1]
    zone = np.full(len(ball), "", dtype="<U11")
    with np.errstate(invalid="ignore"):
        line = np.min(np.stack([x, length - x, y, width - y], axis=1), axis=1)
        from_goal = np.minimum(x, length - x)
        from_axis = np.abs(y - width / 2)
        located = np.isfinite(line)
        zone[located] = "open"
        zone[located & (line <= 2)] = "near_line"
        box = located & (from_goal <= PENALTY_DEPTH_M) & (from_axis <= PENALTY_HALF_WIDTH_M)
        zone[box] = "keeper_zone"
        zone[box & (from_goal <= GOAL_AREA_DEPTH_M) & (from_axis <= GOAL_AREA_HALF_WIDTH_M)] = "goal_area"
        zone[located & (line < 0)] = "outside"
    return zone


def next_true(mask):
    """Index of the next True at or after each frame (len(mask) if there is none)."""
    n = len(mask)
    return np.minimum.accumulate(np.where(mask, np.arange(n), n)[::-1])[::-1]


def inward_speed(ball, i, k, pitch, fps):
    """Ball speed towards the inside of the pitch, across the nearest line, from frame i-k to i."""
    length, width = pitch
    v = (ball[i] - ball[i - k]) * fps / k
    distances = [ball[i, 0], length - ball[i, 0], ball[i, 1], width - ball[i, 1]]
    normals = ((1., 0.), (-1., 0.), (0., 1.), (0., -1.))
    return float(np.dot(v, normals[int(np.argmin(distances))]))


def v4_candidate_diagnostics(parts, fps, cfg=CONFIG):
    minutes = lambda frames: round(float(frames) / fps / 60, 2)
    still_zone = {z: dict(runs=0, frames=0, live=0, runs_3s=0, frames_3s=0, live_3s=0) for z in ZONES}
    exits = dict(total=0, while_ball_still=0, frames=0)
    duels = dict(frames=0, team_switches=0, near=0)
    flips = dict(count=0, frames=0, short_spells=0)
    dead_lengths = []
    gap_keys = ("lost_at_line", "lost_at_line_inward_fast", "back_at_line", "back_at_line_fast",
                "back_still", "back_still_moves_within_1s", "very_long", "left_live")
    gaps = {key: [0, 0] for key in gap_keys}  # [number of gaps, frames]
    outs = {side: dict(episodes=0, bounce_backs=0) for side in SIDES}
    for f, states in parts:
        n = len(states)
        pitch = f["pitch"]
        observed = f["quality"] == 1
        speed = np.nan_to_num(f["speed"], nan=-1.)
        live = states != 2
        still = observed & (speed >= 0) & (speed < .65)
        moving = observed & (speed > 2.0)
        zone = ball_zones(f["ball"], pitch)

        # P2a: ball standing still for >= 1 s, by zone, and how much of it is labelled live
        for a, b in runs(still):
            z = zone[(a + b) // 2]
            if b - a < fps or z not in still_zone:
                continue
            bucket = still_zone[z]
            bucket["runs"] += 1
            bucket["frames"] += b - a
            bucket["live"] += int(live[a:b].sum())
            if b - a >= 3 * fps:
                bucket["runs_3s"] += 1
                bucket["frames_3s"] += b - a
                bucket["live_3s"] += int(live[a:b].sum())

        # P2b: exits from D while the ball is still, and time until it is really kicked
        upcoming = next_true(moving)
        for t in np.flatnonzero((states[:-1] == 2) & (states[1:] != 2)) + 1:
            exits["total"] += 1
            if still[t]:
                exits["while_ball_still"] += 1
                exits["frames"] += int(min(upcoming[t] - t, 30 * fps))

        # P1: duels (both teams within DUEL_RADIUS_M of the ball) and H<->A switches near them
        near = f["nearest"]
        duel = observed & (near[:, 0] <= DUEL_RADIUS_M) & (near[:, 1] <= DUEL_RADIUS_M)
        duels["frames"] += int(duel.sum())
        pad = round(.5 * fps)
        close_to_duel = mean_window(duel.astype(float), pad, pad) > 0
        switches = np.flatnonzero((states[:-1] != 2) & (states[1:] != 2) & (states[:-1] != states[1:])) + 1
        duels["team_switches"] += len(switches)
        duels["near"] += int(close_to_duel[switches].sum())

        # Structure: there-and-back team changes under 3 s, very short spells, dead runs
        starts = np.r_[0, np.flatnonzero(np.diff(states)) + 1]
        lengths = np.diff(np.r_[starts, n])
        values = states[starts]
        for i in range(1, len(values) - 1):
            if (values[i] != 2 and values[i - 1] != 2 and values[i - 1] == values[i + 1]
                    and values[i] != values[i - 1] and lengths[i] < 3 * fps):
                flips["count"] += 1
                flips["frames"] += int(lengths[i])
        flips["short_spells"] += int(np.sum((values != 2) & (lengths < 2 * fps)))
        dead_lengths += [int(length) for value, length in zip(values, lengths) if value == 2]

        # P3: the line rules of restart_like_gaps, split by the direction and speed of the ball
        tracked = f["count"] >= 8
        look, k = max(1, round(.5 * fps)), max(1, round(.2 * fps))
        for a, b in runs(~observed):
            if b - a < round(cfg.medium_gap_s * fps) or tracked[a:b].mean() <= .5:
                continue
            g = b - a
            lost_at_line = a > 0 and observed[a - 1] and f["line_dist"][a - 1] <= cfg.clear_out_m
            after = np.arange(b, min(n, b + look))
            after = after[observed[after]]
            back = speed[after][speed[after] >= 0]
            back_at_line = len(after) > 0 and f["line_dist"][after[0]] <= cfg.clear_out_m
            back_still = len(back) > 0 and np.median(back) < .65
            very_long = g >= round(cfg.very_long_gap_s * fps)
            hits = []
            if lost_at_line:
                hits.append("lost_at_line")
                if a - 1 - k >= 0 and observed[a - 1 - k] and inward_speed(f["ball"], a - 1, k, pitch, fps) > 2.0:
                    hits.append("lost_at_line_inward_fast")
            if back_at_line:
                hits.append("back_at_line")
                if len(back) > 0 and np.median(back) > 2.0:
                    hits.append("back_at_line_fast")
            if back_still:
                hits.append("back_still")
                if moving[b:min(n, b + fps)].any():
                    hits.append("back_still_moves_within_1s")
            if very_long:
                hits.append("very_long")
            if not (lost_at_line or back_at_line or back_still or very_long):
                hits.append("left_live")
            for key in hits:
                gaps[key][0] += 1
                gaps[key][1] += g

        # P6: exits per side, and "bounce-backs" (inside again and moving within 1 s, never lost)
        length, width = pitch
        for a, b in runs(persistent(observed & f["outside"], max(2, round(.16 * fps)))):
            x, y = f["ball"][b - 1]
            beyond_x, beyond_y = max(-x, x - length), max(-y, y - width)
            side = (("goal_line_low_x" if x < 0 else "goal_line_high_x") if beyond_x >= beyond_y
                    else ("touchline_low_y" if y < 0 else "touchline_high_y"))
            outs[side]["episodes"] += 1
            window = slice(b, min(n, b + fps))
            if b < n and observed[window].all() and f["inside"][window].all() and moving[window].any():
                outs[side]["bounce_backs"] += 1

    seconds = np.asarray(dead_lengths, dtype=float) / fps
    return dict(
        still_ball_1s_by_zone={z: dict(runs=v["runs"], minutes=minutes(v["frames"]),
                                       minutes_labelled_live=minutes(v["live"]), runs_3s=v["runs_3s"],
                                       minutes_3s=minutes(v["frames_3s"]),
                                       minutes_labelled_live_3s=minutes(v["live_3s"]))
                               for z, v in still_zone.items()},
        dead_exits=dict(total=exits["total"], while_ball_still=exits["while_ball_still"],
                        minutes_until_ball_moves=minutes(exits["frames"])),
        duels=dict(minutes=minutes(duels["frames"]), team_switches=duels["team_switches"],
                   switches_within_0_5s_of_duel=duels["near"]),
        structure=dict(flip_backs_under_3s=flips["count"], flip_back_minutes=minutes(flips["frames"]),
                       spells_under_2s=flips["short_spells"], dead_runs=len(dead_lengths),
                       dead_run_seconds_mean=round(float(seconds.mean()), 1) if len(seconds) else None,
                       dead_run_seconds_p50=round(float(np.percentile(seconds, 50)), 1) if len(seconds) else None,
                       dead_run_seconds_p90=round(float(np.percentile(seconds, 90)), 1) if len(seconds) else None),
        line_gaps={key: dict(gaps=v[0], minutes=minutes(v[1])) for key, v in gaps.items()},
        out_episodes=outs,
    )


def predict(tracking, events, names, blocks, fps, pitch, cfg=CONFIG):
    labels = np.full(len(tracking.ball), "X", dtype="<U1")
    totals = dict(graded_frames=0, observed_ball_frames=0, control_frames=0,
                  dead_evidence_frames=0, supported_restarts=0, out_of_play_gap_frames=0,
                  merged_flip_backs=0, dead_time_diagnostics={})
    parts = []
    for _, start, last in blocks:
        stop = last + 1
        if not (0 <= start < stop <= len(labels)):
            raise ValueError("Invalid published half boundaries.")
        f = features(tracking.ball[start:stop], tracking.players[start:stop],
                     tracking.teams, fps, pitch, cfg)
        local_events = [dict(e, start=e["start"] - start, end=e["end"] - start)
                        for e in events if e["end"] > start and e["start"] < stop]
        evidence = build_evidence(f, local_events, names, fps, cfg)
        states = decode(*evidence[:5], cfg=cfg)
        # v4 (Claude): there-and-back spells under min_change_s are touches, not changes.
        states, merged = merge_flip_backs(states, fps, cfg)
        totals["merged_flip_backs"] += merged
        labels[start:stop] = np.array(list("HAD"))[states]
        if not evidence[1].any() and not evidence[4].any():
            # An entirely unobserved half provides no basis for a home-team tie-break.
            labels[start:stop][states != 2] = "X"
        totals["graded_frames"] += stop - start
        totals["observed_ball_frames"] += int(np.sum(f["quality"] == 1))
        totals["control_frames"] += int(np.sum(np.abs(f["control"]) > .12))
        totals["dead_evidence_frames"] += int(np.sum(evidence[2]))
        totals["supported_restarts"] += evidence[5]
        totals["out_of_play_gap_frames"] += evidence[6]
        merge_diagnostics(totals["dead_time_diagnostics"], dead_time_diagnostics(f, states, fps))
        parts.append((f, states))
    totals["v4_diagnostics"] = v4_candidate_diagnostics(parts, fps, cfg)
    return labels, totals
