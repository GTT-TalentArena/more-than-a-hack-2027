"""Per-frame evidence for the decoder, as log-likelihood ratios in nats.

Two quantities per frame:

  team  > 0 favours H, < 0 favours A, among live-ball states
  dead  > 0 favours D, < 0 favours a live ball

They are kept separate on purpose. Who is near the ball says which team has it if the ball is
live, and almost nothing about whether it is live -- the thrower holding the ball at the touchline
is as close to it as a dribbler -- so the decoder never lets team evidence argue against D.
"""

import numpy as np

from .atd import HOME, AWAY
from .config import FPS
from .features import (centred_sum, distance_outside, merged_runs, nan_moving_mean,
                       outward_speed, runs)
from .tags import KICKOFF_TYPES, SET_PIECES


# -- team: who controls the ball ----------------------------------------------------------------

def control_kernel(distance, d0, sigma):
    """1 inside d0 metres of a player, Gaussian decay beyond. inf -> 0."""
    return np.exp(-0.5 * (np.maximum(distance - d0, 0.0) / sigma) ** 2)


def speed_gate(relative_speed, v0, sigma):
    """1 when ball and player move together, -> 0 for a ball flying past."""
    return np.exp(-0.5 * (np.maximum(relative_speed - v0, 0.0) / sigma) ** 2)


def control_scores(ctx, cfg, scale):
    """(C_home, C_away): how strongly each team's nearest player controls the ball, 0..1."""
    d0, sigma = scale
    n = ctx["n"]
    rows = np.arange(n)
    ball_v = np.hypot(ctx["bvx"], ctx["bvy"])
    scores = {}
    for team in (HOME, AWAY):
        distance, slot = ctx["near"][team]
        kernel = control_kernel(distance, d0, sigma)
        has = slot >= 0
        safe = np.where(has, slot, 0)
        pvx = ctx["pvx"][rows, safe]
        pvy = ctx["pvy"][rows, safe]
        pspeed = ctx["pspeed"][rows, safe]
        relative = np.hypot(ctx["bvx"] - pvx, ctx["bvy"] - pvy)
        # No player velocity: the speed difference is a lower bound on the relative speed.
        bound = np.maximum(ball_v - np.where(np.isfinite(pspeed), pspeed, 0.0), 0.0)
        relative = np.where(np.isfinite(relative), relative, bound)
        gate = np.where(np.isfinite(ball_v), speed_gate(relative, cfg["team.v0"],
                                                        cfg["team.sigma_v"]),
                        cfg["team.unknown_gate"])
        scores[team] = np.where(has, kernel * gate, 0.0)
    return scores[HOME], scores[AWAY]


def reach_scores(ctx, cfg, scale):
    """(K_home, K_away): the distance kernel alone, without the speed gate, 0..1.

    For dating, not for evidence: with a smoothed ball the gate opens late at every reception
    (the smoothed ball slows down gradually), so "within reach" is the better clock for the
    moment a side gets to the ball.
    """
    d0, sigma = scale
    out = []
    for team in (HOME, AWAY):
        distance, slot = ctx["near"][team]
        out.append(np.where(slot >= 0, control_kernel(distance, d0, sigma), 0.0))
    return out[0], out[1]


def proximity_weight(ctx, cfg):
    """How much a frame's ball position is worth: 1 observed, less if isolated or interpolated."""
    weight = np.zeros(ctx["n"])
    weight[ctx["obs"]] = 1.0
    weight[ctx["obs"] & ctx["isolated"]] = cfg["ball.isolated_weight"]
    fill = ctx["interp"]
    weight[fill] = cfg["team.interp_weight"] * np.exp(-ctx["gap"][fill] / cfg["team.interp_tau"])
    return weight


def proximity_llr(ctx, cfg, c_home, c_away):
    llr = cfg["team.alpha"] * ctx["weight"] * (c_home - c_away)
    llr[np.abs(llr) < cfg["team.zero_below"]] = 0.0
    return llr


def confident_frames(ctx, c_home, c_away):
    """Frames where ball proximity alone names a side clearly: the self-supervision targets."""
    return (ctx["obs"] & ~ctx["isolated"] & (np.maximum(c_home, c_away) >= 0.6)
            & (np.abs(c_home - c_away) >= 0.5) & (ctx["out_dist"] <= 0.0))


def touch_threshold(halves, cfg):
    """Velocity change a touch must reach: the given quantile of a free ground ball.

    Self-calibrated. Free = observed and inside the pitch with nobody within 4 m at any frame of
    the window the change is measured over, so a nearby kick cannot leak into it. Ground = both
    chords slower than touch.ground_speed: a long ball in the air is projected onto the pitch
    along a curved path, which reads as a large velocity change with nobody touching it -- in the
    real match that inflated the reference to 12 m/s at the 1 s scale (v1.5). What a free ground
    ball shows is the tracker's own noise, which is what a touch has to stand out from.
    Returns (threshold m/s, free frames, quantiles).
    """
    pooled = []
    ground = cfg["touch.ground_speed"]
    for ctx in halves:
        nobody = features_window_min(ctx["dmin"], ctx["touch_scale"]) > 4.0
        free = (ctx["obs"] & ~ctx["isolated"] & nobody & (ctx["inside_dist"] > 1.0)
                & np.isfinite(ctx["ball_dv"])
                & (np.nan_to_num(ctx["ball_chord_before"], nan=99.0) < ground)
                & (np.nan_to_num(ctx["ball_chord_after"], nan=99.0) < ground))
        pooled.append(ctx["ball_dv"][free])
    pooled = np.concatenate(pooled) if pooled else np.empty(0)
    if len(pooled) < 500:
        return None, len(pooled), None
    quantiles = tuple(float(v) for v in np.quantile(pooled, [0.5, 0.9, 0.95]))
    return max(float(np.quantile(pooled, cfg["touch.quantile"])), cfg["touch.floor"]), \
        len(pooled), quantiles


def features_window_min(values, half):
    from .features import window_min
    return window_min(values, half)


def touch_llr(ctx, cfg, threshold):
    """Team evidence from touches (study 3.1, P3): a peak of the ball's velocity change with one
    side's player clearly the nearest around it. A touch alone does not change possession -- it
    is worth less than lam_ha -- but it dates the change exactly when control follows, and it is
    the only trace a one-touch interception leaves.

    The nearest distances are taken as the minimum over a few frames around the peak, because a
    smoothed track puts the peak where the ball has already left the foot. Returns (llr, counts)
    with counts = {"peaks", "near", HOME, AWAY, None (ambiguous)}.
    """
    llr = np.zeros(ctx["n"])
    counts = {"peaks": 0, "near": 0, HOME: 0, AWAY: 0, None: 0}
    if threshold is None:
        return llr, counts
    frames = features_touch(ctx, threshold, cfg)
    counts["peaks"] = len(frames)
    reach = max(cfg["touch.reach_window"], ctx["touch_scale"] // 2)
    d_home = features_window_min(ctx["near"][HOME][0], reach)
    d_away = features_window_min(ctx["near"][AWAY][0], reach)
    radius, margin = cfg["touch.radius"], cfg["touch.margin"]
    spread = cfg["touch.spread"]
    for t in frames:
        home, away = d_home[t], d_away[t]
        if min(home, away) > radius:
            continue
        counts["near"] += 1
        if home + margin <= away:
            side = HOME
        elif away + margin <= home:
            side = AWAY
        else:
            counts[None] += 1
            continue
        counts[side] += 1
        a, b = max(t - spread // 2, 0), min(t - spread // 2 + spread, ctx["n"])
        llr[a:b] += (1.0 if side == HOME else -1.0) * cfg["touch.beta"] / float(b - a)
    return llr, counts


def features_touch(ctx, threshold, cfg):
    from .features import touch_frames
    return touch_frames(ctx["ball_dv"], ctx["obs"] & ~ctx["isolated"], threshold,
                        ctx["touch_scale"])


def choose_touch_scale(halves, cfg, fps):
    """Pick the time scale at which touches stand out best, without labels.

    A tracker that smooths the ball spreads every velocity change over its smoothing window, so
    a velocity change measured over a shorter half-window sees only part of it and drowns in the
    free-flight spread. For each candidate half-window this counts the peaks above that scale's
    own free-flight threshold that have a player within reach; the scale that finds the most is
    the one that matches the track. A finer scale than needed splits nothing; a coarser one
    merges a pass and its reception into one peak -- both lose. Returns (scale, profile).
    """
    profile = []
    for half in cfg["touch.scales"]:
        set_touch_scale(halves, half, fps)
        threshold, n_free, _ = touch_threshold(halves, cfg)
        near = sum(touch_llr(ctx, cfg, threshold)[1]["near"] for ctx in halves)
        profile.append((half, threshold, near))
    best = max(profile, key=lambda row: (row[2], -row[0]))[0]
    set_touch_scale(halves, best, fps)
    return best, profile


def set_touch_scale(halves, half, fps):
    """Velocity change and chord speeds (m/s) at one half-window, for every half."""
    from .features import velocity_change_parts
    for ctx in halves:
        change, before, after = velocity_change_parts(ctx["bx"], ctx["by"], half)
        ctx["touch_scale"] = half
        ctx["ball_dv"] = change * fps
        ctx["ball_chord_before"] = before * fps
        ctx["ball_chord_after"] = after * fps


def restart_llr(ctx, cfg, threshold):
    """The restart after a stoppage (study 3.4): the first touch on a ball that reappears slow.

    After a long gap the ball typically comes back into sight held (a throw-in) or placed (a
    free kick, a corner, a goal kick) and is then struck. When it reappears slow and a touch
    follows within restart.search frames, the stoppage is extended over the hold and ended at the
    touch. A ball that reappears already travelling is a ball in flight, and gets nothing.
    Returns (dead llr, alive llr, n restarts found).
    """
    dead = np.zeros(ctx["n"])
    alive = np.zeros(ctx["n"])
    if threshold is None:
        return dead, alive, 0
    touches = features_touch(ctx, threshold, cfg)
    if len(touches) == 0:
        return dead, alive, 0
    found = 0
    starts, stops = runs(~ctx["obs"])
    slow = np.nan_to_num(ctx["ball_speed_obs"], nan=99.0)
    for start, stop in zip(starts, stops):
        if stop - start < cfg["absence.min_gap"] or stop >= ctx["n"]:
            continue
        later = touches[(touches >= stop) & (touches < stop + cfg["restart.search"])]
        if not len(later):
            continue
        kick = int(later[0])
        hold = slice(stop, kick)
        if kick > stop and np.median(slow[hold]) > cfg["restart.hold_speed"]:
            continue
        dead[hold] += cfg["restart.hold_beta"]
        alive[kick:kick + cfg["dead.kick_window"]] -= cfg["restart.beta"]
        found += 1
    return dead, alive, found


def tag_team_llr(ctx, tag_list, calibration, cfg):
    """Weak team prior from Smart Tagging phases, with each code's calibrated polarity.

    The tagger emits phases in pairs over the same interval -- BUILD UP for one side and
    DEFENDING IN ATTACKING THIRD for the other, and so on -- which say the same thing twice. An
    interval that names the same side in possession counts once, at its most reliable code.
    """
    llr = np.zeros(ctx["n"])
    best = {}
    for tag in tag_list:
        entry = calibration.get(tag["code"])
        if not entry or entry["polarity"] == 0 or tag["side"] is None:
            continue
        side = 1.0 if tag["side"] == HOME else -1.0
        key = (tag["start"], tag["end"], side * entry["polarity"] > 0)
        best[key] = max(best.get(key, 0.0), entry["reliability"])
    for (start, end, home), reliability in best.items():
        start = max(start - ctx["first"], 0)
        stop = min(end - ctx["first"], ctx["n"])
        if stop <= start:
            continue
        llr[start:stop] += cfg["tag.beta"] * reliability * (1.0 if home else -1.0)
    cap = cfg["tag.max_per_frame"]
    return np.clip(llr, -cap, cap)


# -- dead ball ----------------------------------------------------------------------------------

def out_of_bounds_llr(ctx, cfg):
    """Ball seen beyond a line: strong evidence of a stoppage.

    Every sighting outside counts, and so does the stretch of the straight line from the last
    sighting inside to the first one outside that lies beyond the line: it dates the crossing
    better than the first sighting outside, which is often a second late. An excursion followed
    within a second by the ball back well inside is most likely a ball in the air projected past
    the line by the camera, and counts less; and no single excursion can contribute more than
    out_run_cap, in case the tracker follows a second ball off the pitch.
    """
    llr = np.zeros(ctx["n"])
    out = ctx["obs"] & (ctx["out_dist"] > cfg["dead.out_margin"])
    crossing = ctx["interp"] & (ctx["out_dist_interp"] > 0.0)
    per_frame = cfg["dead.out_beta"] * out + cfg["dead.out_cross_beta"] * crossing
    starts, stops = merged_runs(out | crossing, cfg["dead.out_merge_gap"])
    observed = np.flatnonzero(ctx["obs"])
    for start, stop in zip(starts, stops):
        if not out[start:stop].any():
            continue
        run = per_frame[start:stop]
        factor = 1.0
        later = observed[(observed >= stop) & (observed < stop + cfg["dead.out_reentry_window"])]
        if len(later) and ctx["inside_dist"][later[0]] >= cfg["dead.out_reentry_inside"]:
            factor = cfg["dead.out_reentry_factor"]
        total = float(run.sum())
        if total * factor > cfg["dead.out_run_cap"]:
            factor = cfg["dead.out_run_cap"] / total
        llr[start:stop] += run * factor
    return llr


def exit_llr(ctx, cfg):
    """Ball last seen at a line heading out, then lost for a while: it probably went out."""
    llr = np.zeros(ctx["n"])
    starts, stops = runs(~ctx["obs"])
    for start, stop in zip(starts, stops):
        if stop - start < cfg["dead.exit_gap_min"] or start == 0:
            continue
        last = start - 1
        near_line = ctx["inside_dist"][last] <= cfg["dead.exit_line_dist"]
        heading_out = ctx["out_speed"][last] >= cfg["dead.exit_out_speed"]
        if near_line and (heading_out or ctx["out_dist"][last] > 0):
            span = min(cfg["dead.exit_frames"], stop - start)
            llr[start:start + span] += cfg["dead.exit_total"] / span
    return llr


def static_ball(ctx, cfg, pitch):
    """(dead llr, alive llr): a still ball (set piece being prepared) and the kick ending it.

    The still test uses a +/- 1 s fit, which starts to see the kick up to a second before it
    happens, so a still run ends early. The kick is therefore looked for from that much before
    the end of the run, with the short fit, and the run's dead evidence stops at the kick.
    """
    length, width = pitch
    dead = np.zeros(ctx["n"])
    alive = np.zeros(ctx["n"])
    speed = ctx["ball_speed_obs"]
    slow = ctx["ball_speed_slow"]
    still = ctx["obs"] & np.isfinite(slow) & (slow < ctx["static_speed"])
    starts, stops = merged_runs(still, cfg["dead.static_merge_gap"])
    corners = np.array([[0, 0], [length, 0], [0, width], [length, width]], dtype=np.float64)
    centre = np.array([length / 2.0, width / 2.0])
    penalty = np.array([[11.0, width / 2.0], [length - 11.0, width / 2.0]])
    for start, stop in zip(starts, stops):
        if stop - start < cfg["dead.static_min_frames"]:
            continue
        frames = np.flatnonzero(still[start:stop]) + start
        x = float(np.median(ctx["bx"][frames]))
        y = float(np.median(ctx["by"][frames]))
        point = np.array([x, y])
        multiplier = 1.0
        if (np.min(np.hypot(*(corners - point).T)) <= 2.5
                or np.hypot(*(centre - point)) <= 2.5):
            multiplier = cfg["dead.static_spot_mult"]
        elif ((min(x, length - x) <= 5.5 and abs(y - width / 2.0) <= 9.16)
              or np.min(np.hypot(*(penalty - point).T)) <= 1.5):
            multiplier = cfg["dead.static_box_mult"]
        attached = np.mean(ctx["dmin"][frames] < cfg["dead.static_attached_dist"])
        if attached >= cfg["dead.static_attached_frac"]:
            multiplier *= cfg["dead.static_attached_mult"]

        low = max(stop - cfg["ball.still_half_window"], start)
        high = min(stop + cfg["dead.kick_search_ahead"], ctx["n"])
        moving = ctx["obs"][low:high] & (np.nan_to_num(speed[low:high]) >= cfg["dead.kick_speed"])
        if moving.any():
            kick = low + int(np.argmax(moving))
            dead[start:kick] += cfg["dead.static_beta"] * multiplier
            alive[kick:kick + cfg["dead.kick_window"]] -= cfg["dead.kick_beta"]
        else:
            dead[start:stop] += cfg["dead.static_beta"] * multiplier
    return dead, alive


def fast_ball_llr(ctx, cfg):
    """A ball travelling fast inside the pitch is in play."""
    fast = (ctx["obs"] & ~ctx["isolated"]
            & (np.nan_to_num(ctx["ball_speed_obs"]) >= cfg["dead.fast_speed"])
            & (ctx["inside_dist"] >= cfg["dead.fast_inside"]))
    return -cfg["dead.fast_beta"] * fast


def fit_speed_model(values, cfg, iterations=60):
    """Two-component 1-D Gaussian mixture on the smoothed collective speed, or None.

    Self-calibrated on this match, without labels: stoppages are long stretches of walking, so
    the slow component is the dead-ball one. Returns (mu_slow, sd_slow, mu_fast, sd_fast, w_slow).
    """
    values = values[np.isfinite(values)]
    if len(values) < 1000:
        return None
    low, high = np.percentile(values, [20, 70])
    spread = max((high - low) / 2.0, 0.05)
    mu = np.array([low, high], dtype=np.float64)
    sd = np.array([spread, spread], dtype=np.float64)
    weight = np.array([0.3, 0.7])
    for _ in range(iterations):
        density = weight / sd * np.exp(-0.5 * ((values[:, None] - mu) / sd) ** 2)
        total = density.sum(axis=1, keepdims=True)
        total[total == 0] = 1e-300
        resp = density / total
        mass = resp.sum(axis=0)
        if np.any(mass < 10):
            return None
        weight = mass / len(values)
        mu = (resp * values[:, None]).sum(axis=0) / mass
        sd = np.sqrt((resp * (values[:, None] - mu) ** 2).sum(axis=0) / mass)
        sd = np.maximum(sd, 0.05)
    order = np.argsort(mu)
    mu, sd, weight = mu[order], sd[order], weight[order]
    if mu[1] - mu[0] < cfg["dead.speed_min_separation"]:
        return None
    return float(mu[0]), float(sd[0]), float(mu[1]), float(sd[1]), float(weight[0])


def ball_activity(ctx, cfg):
    """Fraction of the frames around t in which the ball is seen moving inside the pitch."""
    moving = (ctx["obs"] & (np.nan_to_num(ctx["ball_speed_obs"]) >= cfg["dead.speed_gate_speed"])
              & (ctx["inside_dist"] >= cfg["dead.fast_inside"]))
    half = cfg["dead.speed_gate_window"]
    return centred_sum(moving.astype(np.float64), half) / float(2 * half + 1)


def speed_llr(ctx, model, cfg):
    """Per-frame dead-vs-alive evidence from the collective speed, monotone and clipped.

    Slow players are evidence of a stoppage only while the ball does not say otherwise: a slow
    build-up still moves the ball around, a stoppage does not. Where the ball is seen moving
    inside the pitch in a good part of the surrounding 2 s, the speed term may argue for a live
    ball but not for a dead one.
    """
    llr = np.zeros(ctx["n"])
    if model is None:
        return llr
    mu_slow, sd_slow, mu_fast, sd_fast, _ = model
    v = np.clip(ctx["speed_smooth"], mu_slow, mu_fast)
    ratio = (np.log(sd_fast / sd_slow) - 0.5 * ((v - mu_slow) / sd_slow) ** 2
             + 0.5 * ((v - mu_fast) / sd_fast) ** 2)
    ratio = np.clip(ratio, -cfg["dead.speed_clip"], cfg["dead.speed_clip"])
    usable = np.isfinite(ratio) & (ctx["n_players"] >= cfg["dead.speed_min_players"])
    llr[usable] = ratio[usable] / cfg["dead.speed_tau"]
    if cfg["dead.speed_gate_frac"] > 0:
        in_play = ball_activity(ctx, cfg) >= cfg["dead.speed_gate_frac"]
        llr[in_play & (llr > 0)] = 0.0
    return llr


def kickoff_llr(ctx, cfg, pitch):
    """Both teams in their own half, slow, ball (if seen) on the centre spot: before a kick-off."""
    length, width = pitch
    own = ctx["own_half_frac"]
    slow = ctx["speed_raw_smooth"] <= cfg["dead.kickoff_max_speed"]
    ball_ok = ~ctx["obs"] | (np.hypot(ctx["bx"] - length / 2.0, ctx["by"] - width / 2.0)
                             <= cfg["dead.kickoff_ball_radius"])
    formation = ((ctx["n_players"] >= cfg["dead.kickoff_min_players"])
                 & (own >= cfg["dead.kickoff_own_half_frac"]) & slow & ball_ok)
    smooth = nan_moving_mean(formation.astype(np.float64), cfg["dead.kickoff_smooth"])
    return cfg["dead.kickoff_beta"] * (np.nan_to_num(smooth) >= 0.5)


def setpiece_llr(ctx, tag_list, cfg):
    """Smart Tagging set pieces: dead before the restart inside the window, alive after it.

    Where in the window the restart falls is only documented for kick-offs (~3.5 s after it
    opens), and the windows can be much longer than that, so the dead evidence inside a window
    stops at setpiece_max_dead frames after it opens whatever its length: a long window must
    not push a stoppage into the play that follows the restart.
    """
    llr = np.zeros(ctx["n"])
    beta = cfg["dead.setpiece_beta"]
    for tag in tag_list:
        if tag["code"] != SET_PIECES:
            continue
        start, end = tag["start"] - ctx["first"], tag["end"] - ctx["first"]
        pre = cfg["dead.setpiece_kickoff_pre"] if tag["type"] in KICKOFF_TYPES \
            else cfg["dead.setpiece_pre"]
        dead_stop = start + min(int(round(cfg["dead.setpiece_frac"] * (end - start))),
                                cfg["dead.setpiece_max_dead"])
        a, b = max(start - pre, 0), min(dead_stop, ctx["n"])
        if b > a:
            llr[a:b] += beta
        a, b = max(end, 0), min(end + cfg["dead.setpiece_post"], ctx["n"])
        if b > a:
            llr[a:b] -= beta
    return llr


def long_gaps(ctx, cfg):
    """Frames inside a gap of the ball track of at least absence.min_gap frames."""
    mask = np.zeros(ctx["n"], dtype=bool)
    starts, stops = runs(~ctx["obs"])
    for start, stop in zip(starts, stops):
        if stop - start >= cfg["absence.min_gap"]:
            mask[start:stop] = True
    return mask


def fit_absence_model(halves, states_by_half, cfg):
    """How strongly a long absence of the ball goes with a stoppage in this match.

    Study 3.3: a long gap is decided with stoppage evidence, and absence counts as such evidence
    only if it correlates with D in our data (L4). Measured here without labels, as one hard-EM
    step: the share of long-gap frames that a first decoding -- one that never looked at
    visibility -- put in D, against the share of all frames it put in D. The evidence is the log
    odds ratio of the two (not the odds of the first, which would smuggle in the prior). Short
    gaps carry nothing, whatever this says: a tracker that flickers is not a stoppage. Returns
    (per-frame llr, dead share of long-gap frames, dead share overall, long-gap share of graded
    frames) or None.
    """
    gap_frames = dead_in_gaps = graded = dead = 0
    for ctx, states in zip(halves, states_by_half):
        mask = long_gaps(ctx, cfg)
        gap_frames += int(mask.sum())
        dead_in_gaps += int(np.sum(mask & (states == 2)))
        graded += ctx["n"]
        dead += int(np.sum(states == 2))
    if gap_frames < 10 * cfg["absence.min_gap"] or graded == 0:
        return None
    share = (dead_in_gaps + 1.0) / (gap_frames + 2.0)
    overall = (dead + 1.0) / (graded + 2.0)
    ratio = np.log(share / (1.0 - share)) - np.log(overall / (1.0 - overall))
    ratio = float(np.clip(ratio, *cfg["absence.clip"]))
    return (cfg["absence.scale"] * ratio / cfg["absence.tau"], share, overall,
            gap_frames / float(graded))


def absence_llr(ctx, model, cfg):
    """Constant dead-vs-live evidence on every frame of a long gap, so that a stoppage tends to
    begin where the ball vanishes and to last while it stays out of sight."""
    llr = np.zeros(ctx["n"])
    if model is None:
        return llr
    llr[long_gaps(ctx, cfg)] = model[0]
    return llr


def dead_components(ctx, cfg, pitch, speed_model, tag_list):
    """Every dead-ball term separately, so the log can say what each one contributed."""
    static_dead, kick_alive = static_ball(ctx, cfg, pitch)
    restart = 0.0
    if cfg["restart.enabled"]:
        hold, kick, ctx["n_restarts"] = restart_llr(ctx, cfg, ctx.get("touch_threshold"))
        restart = hold + kick
    parts = {
        "restart": restart,
        "out": out_of_bounds_llr(ctx, cfg),
        "exit": exit_llr(ctx, cfg),
        "static": static_dead,
        "kick": kick_alive,
        "fast": fast_ball_llr(ctx, cfg),
        "speed": speed_llr(ctx, speed_model, cfg) if cfg["dead.speed_enabled"] else 0.0,
        "kickoff": kickoff_llr(ctx, cfg, pitch),
        "setpiece": setpiece_llr(ctx, tag_list, cfg) if cfg["dead.setpiece_enabled"] else 0.0,
    }
    return {k: (v if isinstance(v, np.ndarray) else np.zeros(ctx["n"])) for k, v in parts.items()}


def ball_geometry(ctx, pitch):
    """Distances to the lines and outward speed of the observed ball (NaN-safe)."""
    x = np.where(ctx["obs"], ctx["bx"], np.nan)
    y = np.where(ctx["obs"], ctx["by"], np.nan)
    outside, inside = distance_outside(np.nan_to_num(x, nan=-1e6), np.nan_to_num(y, nan=-1e6),
                                       pitch)
    outside = np.where(ctx["obs"], outside, 0.0)
    inside = np.where(ctx["obs"], inside, np.inf)
    out_speed = outward_speed(np.nan_to_num(x), np.nan_to_num(y), np.nan_to_num(ctx["bvx"]),
                              np.nan_to_num(ctx["bvy"]), pitch)
    out_speed = np.where(ctx["obs"] & np.isfinite(ctx["bvx"]), out_speed, 0.0)
    return outside, inside, out_speed
