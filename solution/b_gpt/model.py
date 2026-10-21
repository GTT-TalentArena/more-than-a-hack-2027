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
    control[outside] = 0
    return dict(ball=ball, quality=quality, speed=speed, activity=activity, count=count,
                nearest=nearest, control=control, outside=outside, inside=inside, beyond=beyond)


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
    moving = seen & f["inside"] & np.isfinite(speed) & (speed > 2.0)
    running = np.isfinite(activity) & (activity > 2.0)
    # The out-of-play gap carries the same weight as a ball seen outside, and running
    # players do not count against it: they move during throw-ins and goal kicks.
    margin = (3.8 * (outside | out_gap) + 1.6 * still + 1.0 * quiet_missing
              - 1.6 * moving - .65 * (running & ~out_gap) - .35 * seen - .35 * phase)
    seed = outside | still | quiet_missing | out_gap
    live = moving | (running & ~outside & ~out_gap) | ((phase > .65) & ~seed)
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


def predict(tracking, events, names, blocks, fps, pitch, cfg=CONFIG):
    labels = np.full(len(tracking.ball), "X", dtype="<U1")
    totals = dict(graded_frames=0, observed_ball_frames=0, control_frames=0,
                  dead_evidence_frames=0, supported_restarts=0, out_of_play_gap_frames=0)
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
    return labels, totals
