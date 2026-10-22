"""Candidate A end to end: tracking + Smart Tagging -> per-frame evidence -> exact decoding -> CSV.

    python -m solution.a_opus --out evaluation/results/a_opus.csv

Three stages. (1) Per half: clean the ball track, compute velocities, who is near the ball, team
shape and collective speed. (2) Across the match, without labels: calibrate the control radius,
fit the dead-ball speed model, calibrate every Smart Tagging code against ball proximity and
cross-fit the ball-free team model. (3) Per half: add the evidence up and decode H / A / D
exactly with switch costs (decode.py). Frames outside the two graded halves are written as X.

The log reports only aggregate figures -- counts, percentages, durations, fitted constants --
never a row, a frame or an extract (data terms, FAQ.md; protocol A7).
"""

import argparse
import os
import sys
import time
import warnings

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import games  # noqa: E402

from . import atd, ballfree, config, decode, diagnostics, evidence, features  # noqa: E402
from . import tags as tagging  # noqa: E402
from .atd import HOME, AWAY  # noqa: E402

FPS = config.FPS
LABELS = np.array(["H", "A", "D"])


def build_half(data, first, last, cfg, pitch):
    """Stage 1 for one graded half [first, last] (video frames, inclusive)."""
    length = pitch[0]
    window = slice(first, last + 1)
    n = last + 1 - first
    slot_team = data["slot_team"]

    px = data["px"][window]
    py = data["py"][window]
    area = features.in_area(px, py, pitch, cfg["players.area_margin"])
    px = np.where(area, px, np.nan).astype(np.float32)
    py = np.where(area, py, np.nan).astype(np.float32)
    ps = None if data["ps"] is None else np.where(area, data["ps"][window], np.nan)
    valid = np.isfinite(px)
    pvx, pvy, pspeed = features.player_speed(px, py, ps, cfg["players.vel_half_window"],
                                             cfg["players.vel_min_points"], FPS)

    raw_x = data["bx"][window].astype(np.float64)
    raw_y = data["by"][window].astype(np.float64)
    seen = np.isfinite(raw_x)
    spike = features.despike(raw_x, raw_y, cfg["ball.spike_window"], cfg["ball.spike_dist"])
    obs = seen & ~spike
    bx = np.where(obs, raw_x, np.nan)
    by = np.where(obs, raw_y, np.nan)
    lonely = features.isolated(obs, cfg["ball.isolated_window"])
    vel_half, vel_min = cfg["ball.vel_half_window"], cfg["ball.vel_min_points"]
    bvx_obs = features.local_slope(bx, vel_half, vel_min) * FPS
    bvy_obs = features.local_slope(by, vel_half, vel_min) * FPS
    bvx_obs[~obs] = np.nan
    bvy_obs[~obs] = np.nan
    still_half, still_min = cfg["ball.still_half_window"], cfg["ball.still_min_points"]
    slow_speed = np.hypot(features.local_slope(bx, still_half, still_min),
                          features.local_slope(by, still_half, still_min)) * FPS
    slow_speed[~obs] = np.nan
    ix, iy, interp, gap, cvx, cvy = features.interpolate(bx, by, obs, cfg["ball.interp_max_gap"])

    ball_x = np.where(obs, bx, np.where(interp, ix, np.nan))
    ball_y = np.where(obs, by, np.where(interp, iy, np.nan))
    ctx = {
        "first": first, "last": last, "n": n,
        "obs": obs, "seen": seen, "spike": spike, "isolated": lonely,
        "interp": interp, "gap": gap,
        "bx": bx, "by": by,
        "bvx": np.where(obs, bvx_obs, np.where(interp, cvx * FPS, np.nan)),
        "bvy": np.where(obs, bvy_obs, np.where(interp, cvy * FPS, np.nan)),
        "ball_speed_obs": np.hypot(bvx_obs, bvy_obs),
        "ball_speed_slow": slow_speed,
        "second_diff": features.second_difference(bx, by, obs),
        "pvx": pvx, "pvy": pvy, "pspeed": pspeed,
    }
    ctx["near"] = features.nearest_by_team(ball_x, ball_y, px, py, slot_team, valid)
    ctx["dmin"] = np.minimum(ctx["near"][HOME][0], ctx["near"][AWAY][0])
    ctx["out_dist"], ctx["inside_dist"], ctx["out_speed"] = evidence.ball_geometry(ctx, pitch)
    ctx["out_dist_interp"] = np.where(
        interp, features.distance_outside(np.nan_to_num(ix), np.nan_to_num(iy), pitch)[0], 0.0)

    sign, margin = features.attack_sign(px, slot_team, valid, length)
    ctx["attack_sign"], ctx["attack_margin"] = sign, margin
    ctx["shape"] = features.team_shape(px, py, pvx, pvy, pspeed, slot_team, valid)
    ctx["n_players"] = ctx["shape"][HOME]["n"] + ctx["shape"][AWAY]["n"]
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        speed_raw = np.nanmean(np.where(valid, pspeed, np.nan), axis=1)
    ctx["speed_smooth"] = features.nan_moving_mean(speed_raw, cfg["dead.speed_smooth"])
    ctx["speed_raw_smooth"] = features.nan_moving_mean(speed_raw, cfg["dead.kickoff_smooth"])

    # Own half along each team's attacking direction, with a metre of slack on the halfway line.
    forward = (px - length / 2.0) * np.where(slot_team == HOME, sign, -sign)[None, :]
    own = valid & (forward <= 1.0)
    ctx["own_half_frac"] = own.sum(axis=1) / np.maximum(ctx["n_players"], 1)
    ctx["dead_hint"] = (ctx["out_dist"] > 0) | (
        np.nan_to_num(ctx["ball_speed_slow"], nan=99.0) < cfg["dead.static_speed"])
    return ctx


def estimate_ball_lag(data, blocks, pitch, cfg):
    """Relative lag of the ball track behind the players, from carried balls, label-free.

    Returns (delta, profile). delta > 0 means the ball track is late by delta frames (a smoother
    that is not centred would do that) and is corrected by advancing it; 0 when no shift fits the
    carried balls clearly better than none.
    """
    bx, by, px, py = data["bx"], data["by"], data["px"], data["py"]
    frames, slots = [], []
    for _, first, last in blocks:
        t = np.arange(first + 4, last - 4)
        ok = np.isfinite(bx[t]) & np.isfinite(bx[t + 4]) & np.isfinite(bx[t - 4])
        t = t[ok]
        speed = np.hypot(bx[t + 4] - bx[t - 4], by[t + 4] - by[t - 4]) / 8.0 * FPS
        t = t[(speed >= 1.5) & (speed <= 6.0)]
        with np.errstate(invalid="ignore"):
            d = np.hypot(px[t] - bx[t, None], py[t] - by[t, None])
        d = np.where(np.isfinite(d), d, np.inf)
        nearest = np.argmin(d, axis=1)
        near = d[np.arange(len(t)), nearest] <= 2.0
        frames.append(t[near])
        slots.append(nearest[near])
    frames = np.concatenate(frames) if frames else np.empty(0, dtype=np.int64)
    slots = np.concatenate(slots) if slots else np.empty(0, dtype=np.int64)
    if len(frames) < 1000:
        return 0, []
    profile = features.ball_lag_profile(bx, by, px, py, frames, slots, cfg["ball.lag_max"])
    scored = [(delta, d) for delta, d, _ in profile if d is not None]
    if not scored:
        return 0, profile
    zero = dict(scored).get(0)
    best, best_d = min(scored, key=lambda item: (item[1], abs(item[0])))
    if (not cfg["ball.lag_correction"] or zero is None or abs(best) < 2
            or best_d > (1.0 - cfg["ball.lag_min_gain"]) * zero):
        return 0, profile
    return best, profile


def calibrate_control_scale(halves, cfg):
    """(d0, sigma_d, median) from the nearest-player distance of slow balls in this match."""
    samples = []
    for ctx in halves:
        slow = (ctx["obs"] & ~ctx["isolated"]
                & (np.nan_to_num(ctx["ball_speed_obs"], nan=99.0) < 4.0)
                & (ctx["inside_dist"] > 0) & (ctx["dmin"] < 5.0))
        samples.append(ctx["dmin"][slow])
    samples = np.concatenate(samples) if samples else np.empty(0)
    if not cfg["team.calibrate"] or len(samples) < 500:
        return cfg["team.d0"], cfg["team.sigma_d"], None, len(samples)
    median = float(np.median(samples))
    d0 = float(np.clip(0.6 * median, *cfg["team.d0_range"]))
    sigma = float(np.clip(0.8 * median, *cfg["team.sigma_range"]))
    return d0, sigma, median, len(samples)


def calibrate_tag_codes(tag_list, halves, cfg):
    """Polarity and reliability of every phase code, from agreement with ball proximity.

    No labels: a code whose tagged side agrees with whoever is clearly on the ball is used as
    tagged, one that disagrees is flipped, one at chance is ignored.
    """
    counts = {}
    for ctx in halves:
        confident = ctx["confident"]
        home_on_ball = ctx["c_home"] > ctx["c_away"]
        for tag in tag_list:
            prior = tagging.prior_polarity(tag["code"])
            if prior == 0 or tag["side"] is None:
                continue
            start = max(tag["start"] - ctx["first"], 0)
            stop = min(tag["end"] - ctx["first"], ctx["n"])
            if stop <= start:
                continue
            chosen = confident[start:stop]
            if not chosen.any():
                continue
            implied_home = (tag["side"] == HOME) == (prior == 1)
            agree = int(np.sum(home_on_ball[start:stop][chosen] == implied_home))
            total = int(chosen.sum())
            got = counts.setdefault(tag["code"], [0, 0])
            got[0] += agree
            got[1] += total

    calibration = {}
    codes = sorted({tag["code"] for tag in tag_list if tagging.prior_polarity(tag["code"])})
    span = 2.0 * cfg["tag.full_agreement"] - 1.0
    for code in codes:
        prior = tagging.prior_polarity(code)
        agree, total = counts.get(code, (0, 0))
        if total >= cfg["tag.min_calib_frames"]:
            rate = agree / float(total)
            polarity = prior if rate >= 0.5 else -prior
            reliability = float(np.clip(abs(2.0 * rate - 1.0) / span, 0.0, 1.0))
        else:
            rate, polarity, reliability = None, prior, cfg["tag.default_reliability"]
        calibration[code] = {"polarity": polarity, "reliability": reliability,
                             "agreement": rate, "frames": total, "flipped": polarity != prior}
    return calibration


def log_absence(log, model, first_pass, cfg):
    """The long-gap evidence the second pass uses, and what the first pass looked like."""
    per_frame, share, overall, gap_share = model
    log("[a_opus] ball-absence model: first pass {} possessions, {} stoppages, {:.1%} dead; gaps "
        ">= {:.0f} s cover {:.1%} of graded frames, {:.1%} of them decoded dead -> {:+.3f} nats "
        "per gap frame".format(
            first_pass["n_possessions"], first_pass["n_dead"], overall,
            cfg["absence.min_gap"] / float(FPS), gap_share, share, per_frame))


def log_checks(log, cfg, tag_list, halves, states_by_half, scores_by_half, static_speed):
    """The label-free checks of diagnostics.py, one line each. Reported, never optimised."""
    log("[a_opus] label-free checks:")
    n_windows, lengths, n_hit, offsets, fractions, dead_starts = diagnostics.setpiece_timing(
        tag_list, halves, states_by_half)
    if n_windows:
        log("[a_opus]   set-piece windows: {}, length p10/p50/p90 {} s; {} contain a decoded restart"
            "{}".format(n_windows, "/".join("{:.1f}".format(v) for v in lengths), n_hit,
                        "" if offsets is None else
                        ", at p10/p50/p90 {} s after the window opens (fraction {})".format(
                            "/".join("{:.1f}".format(v) for v in offsets),
                            "/".join("{:.2f}".format(v) for v in fractions))))
        if dead_starts is not None:
            log("[a_opus]   the stoppage before that restart starts p10/p50/p90 {} s after the "
                "window opens".format("/".join("{:+.1f}".format(v) for v in dead_starts)))
    parts = diagnostics.composition(halves, states_by_half, static_speed)
    for name in ("dead", "live"):
        p = parts[name]
        log("[a_opus]   decoded {} frames: ball seen {:.0%}, fast inside {:.1%}, outside {:.1%}, "
            "still {:.1%}".format(name, p["seen"], p["fast"], p["outside"], p["still"]))
    ignored = diagnostics.ignored_control(halves, states_by_half)
    log("[a_opus]   clear control by the side decoded as NOT on the ball (live), runs of "
        "{}".format(", ".join("{} f: {}".format(k, v) for k, v in ignored.items())))
    rows = diagnostics.switch_cost_curve(scores_by_half, cfg, (3.0, 4.0, 5.0, 6.0, 8.0))
    stats = [(lam, summarise(states)) for lam, states in rows]
    log("[a_opus]   switch cost lam_ha {} -> possessions {}, H<->A changes {}, stoppages {}"
        .format("/".join("{:g}".format(lam) for lam, _ in stats),
                "/".join(str(s["n_possessions"]) for _, s in stats),
                "/".join(str(s["changes"]["H->A"] + s["changes"]["A->H"]) for _, s in stats),
                "/".join(str(s["n_dead"]) for _, s in stats)))


def summarise(states_by_half):
    """Aggregate shape of the decoded labels: what validate_submission would also say."""
    lengths, dead_lengths = [], []
    graded = dead = home = alive = 0
    changes = {"H->A": 0, "A->H": 0, "live->D": 0, "D->live": 0}
    for states in states_by_half:
        graded += len(states)
        dead += int(np.sum(states == decode.D))
        home += int(np.sum(states == decode.H))
        alive += int(np.sum(states != decode.D))
        breaks = np.flatnonzero(states[1:] != states[:-1]) + 1
        bounds = np.concatenate(([0], breaks, [len(states)]))
        for a, b in zip(bounds[:-1], bounds[1:]):
            (dead_lengths if states[a] == decode.D else lengths).append(b - a)
        for index in breaks:
            before, after = states[index - 1], states[index]
            if after == decode.D:
                changes["live->D"] += 1
            elif before == decode.D:
                changes["D->live"] += 1
            elif before == decode.H:
                changes["H->A"] += 1
            else:
                changes["A->H"] += 1
    seconds = np.array(lengths, dtype=np.float64) / FPS
    dead_seconds = np.array(dead_lengths, dtype=np.float64) / FPS
    return {
        "n_possessions": len(lengths),
        "mean_s": float(seconds.mean()) if len(seconds) else 0.0,
        "median_s": float(np.median(seconds)) if len(seconds) else 0.0,
        "under_1s": float(np.mean(seconds < 1)) if len(seconds) else 0.0,
        "under_2s": float(np.mean(seconds < 2)) if len(seconds) else 0.0,
        "under_5s": float(np.mean(seconds < 5)) if len(seconds) else 0.0,
        "n_dead": len(dead_lengths),
        "dead_share": dead / float(max(graded, 1)),
        "dead_median_s": float(np.median(dead_seconds)) if len(dead_seconds) else 0.0,
        "home_share": home / float(max(alive, 1)),
        "changes": changes,
    }


def write_evidence(path, n_frames, halves, teams, deads, states_by_half):
    """Per-frame signals over the whole video, named as in docs/CONTRATO_DATOS.md section 6.

    control_H_score / control_A_score / control_valid are the contract's contact/control group
    (0..1 strength of evidence, not a probability); nearest_H_m / nearest_A_m / distance_valid
    its distance group. Extra, candidate-specific: touch_H / touch_A (touches found), team_llr
    and dead_llr (the evidence the decoder adds up, in nats) and state (decoded 0 H, 1 A, 2 D,
    -1 outside the graded halves). NaN and False outside the graded halves.
    """
    def blank(dtype, fill):
        return np.full(n_frames, fill, dtype=dtype)
    out = {"frame": np.arange(n_frames, dtype=np.int64),
           "control_H_score": blank(np.float64, np.nan), "control_A_score": blank(np.float64, np.nan),
           "control_valid": blank(bool, False), "nearest_H_m": blank(np.float64, np.nan),
           "nearest_A_m": blank(np.float64, np.nan), "distance_valid": blank(bool, False),
           "touch_H": blank(bool, False), "touch_A": blank(bool, False),
           "team_llr": blank(np.float64, np.nan), "dead_llr": blank(np.float64, np.nan),
           "state": blank(np.int8, -1)}
    for ctx, team, dead, states in zip(halves, teams, deads, states_by_half):
        window = slice(ctx["first"], ctx["last"] + 1)
        valid = ctx["weight"] > 0
        out["control_valid"][window] = valid
        out["control_H_score"][window] = np.where(valid, ctx["c_home"], np.nan)
        out["control_A_score"][window] = np.where(valid, ctx["c_away"], np.nan)
        d_home, d_away = ctx["near"][HOME][0], ctx["near"][AWAY][0]
        both = np.isfinite(d_home) & np.isfinite(d_away)
        out["distance_valid"][window] = both
        out["nearest_H_m"][window] = np.where(np.isfinite(d_home), d_home, np.nan)
        out["nearest_A_m"][window] = np.where(np.isfinite(d_away), d_away, np.nan)
        touches = ctx.get("touch_llr", np.zeros(ctx["n"]))
        out["touch_H"][window] = touches > 0
        out["touch_A"][window] = touches < 0
        out["team_llr"][window] = team
        out["dead_llr"][window] = dead
        out["state"][window] = states
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    np.savez_compressed(path, **out)


def write_csv(path, labels):
    """frame,label with '\\n' line ends, so the bytes do not depend on the OS."""
    folder = os.path.dirname(os.path.abspath(path))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(path, "w", newline="\n") as handle:
        handle.write("frame,label\n")
        handle.write("".join("{},{}\n".format(i, label) for i, label in enumerate(labels)))


def run(out_path, data_dir=None, overrides=(), log=print, evidence_path=None):
    """Build the submission. Returns the aggregate report that was logged."""
    clock = time.time()
    cfg = config.build(overrides)
    game = games.GAME
    pitch = tuple(games.GAMES[game]["pitch"])
    n_frames = games.source_frames("tactical", game)
    meta_path, raw_path = games.require(["atd_meta", "atd_raw"], game, data_dir)

    data = atd.load(meta_path, raw_path, n_frames, pitch)
    s = data["summary"]
    log("[a_opus] ATD: {} records (contiguous {}), {} slots ({} H / {} A), layout from {}".format(
        s["n_records"], s["contiguous"], s["n_slots"], s["slots_home"], s["slots_away"],
        s["layout_source"]))
    log("[a_opus]   player channels {}, ball channels {}; home side by {} (first Team is home: "
        "{}); slot order = Player order: {}".format(
            ",".join(s["player_channels"]), ",".join(s["ball_channels"]), s["home_rule"],
            s["first_team_is_home"], s["slot_order_matches_players"]))
    if s["slow_lines"] or s["bad_lines"] or s["out_of_range"] or s["unknown_slots"]:
        log("[a_opus]   parse notes: {} lines parsed slowly, {} unreadable, {} out of range, "
            "{} slots without a team".format(s["slow_lines"], s["bad_lines"], s["out_of_range"],
                                             s["unknown_slots"]))
    log("[a_opus]   ball present on {:.1f}% of frames  ({:.0f} s)".format(
        s["ball_seen_pct"], time.time() - clock))

    tag_list, tag_note = tagging.load(game, data_dir, data["team_names"])
    if tag_note:
        log("[a_opus] " + tag_note)
    else:
        sides = [t["side"] for t in tag_list]
        log("[a_opus] Smart Tagging: {} instances, side H {} / A {} / none {}".format(
            len(tag_list), sides.count(HOME), sides.count(AWAY), sides.count(None)))

    blocks = games.half_video_blocks(game)
    lag, profile = estimate_ball_lag(data, blocks, pitch, cfg)
    if profile:
        shown = [(d, m) for d, m, _ in profile if d in (-12, -8, -4, -2, 0, 2, 4, 8, 12)]
        log("[a_opus] ball-track lag behind players (median |v ball(t+delta) - v carrier(t)| of "
            "carried balls): {}; correction applied: {:+d} frames".format(
                ", ".join("{:+d} f {}".format(d, "--" if m is None else "{:.2f}".format(m))
                          for d, m in shown), lag))
    if lag:
        data["bx"] = features.shift_track(data["bx"], lag)
        data["by"] = features.shift_track(data["by"], lag)
    halves = [build_half(data, first, last, cfg, pitch) for _, first, last in blocks]
    evidence.set_touch_scale(halves, cfg["touch.scales"][0], FPS)
    del data
    graded = sum(ctx["n"] for ctx in halves)
    seen = sum(int(ctx["seen"].sum()) for ctx in halves)
    obs = sum(int(ctx["obs"].sum()) for ctx in halves)
    interp = sum(int(ctx["interp"].sum()) for ctx in halves)
    log("[a_opus] graded frames {}: ball seen {:.1f}%, kept after despiking {:.1f}%, bridged by "
        "interpolation (<= {:.1f} s) +{:.1f}%".format(
            graded, 100.0 * seen / graded, 100.0 * obs / graded,
            cfg["ball.interp_max_gap"] / float(FPS), 100.0 * interp / graded))
    log("[a_opus] attack direction margins: {} m".format(
        " / ".join("{:.1f}".format(ctx["attack_margin"]) for ctx in halves)))

    # Position noise of the ball track, from second differences of consecutive detections. It
    # sets how slow a fitted speed must be before the ball counts as still.
    second = np.concatenate([ctx["second_diff"] for ctx in halves])
    noise = float(np.median(second) * 1.4826 / np.sqrt(6.0)) if len(second) > 100 else None
    half_window = cfg["ball.still_half_window"]
    slope_sd = (np.sqrt(3.0 / (half_window * (half_window + 1) * (2 * half_window + 1))) * FPS
                * (noise or 0.0))
    static_speed = max(cfg["dead.static_speed"], 2.5 * slope_sd)
    for ctx in halves:
        ctx["static_speed"] = static_speed
    log("[a_opus] ball position noise ~{} m -> still-ball threshold {:.2f} m/s".format(
        "--" if noise is None else "{:.2f}".format(noise), static_speed))

    d0, sigma, median, n_samples = calibrate_control_scale(halves, cfg)
    log("[a_opus] control zone: d0 {:.2f} m, sigma {:.2f} m ({})".format(
        d0, sigma, "median slow-ball distance {:.2f} m over {} frames".format(median, n_samples)
        if median is not None else "defaults"))
    for ctx in halves:
        ctx["c_home"], ctx["c_away"] = evidence.control_scores(ctx, cfg, (d0, sigma))
        ctx["weight"] = evidence.proximity_weight(ctx, cfg)
        ctx["team_prox"] = evidence.proximity_llr(ctx, cfg, ctx["c_home"], ctx["c_away"])
        ctx["confident"] = evidence.confident_frames(ctx, ctx["c_home"], ctx["c_away"])
    confident = sum(int(ctx["confident"].sum()) for ctx in halves)
    log("[a_opus] frames with a clear side on the ball: {:.1f}% of graded".format(
        100.0 * confident / graded))

    if cfg["touch.enabled"] or cfg["restart.enabled"]:
        scale, profile = evidence.choose_touch_scale(halves, cfg, FPS)
        log("[a_opus] touch scale (peaks with a player within reach, per half-window): {} -> "
            "+/- {} frames".format(", ".join(
                "{} f {}".format(h, n) for h, _, n in profile), scale))
        threshold, n_free, quantiles = evidence.touch_threshold(halves, cfg)
        totals = {"peaks": 0, "near": 0, HOME: 0, AWAY: 0, None: 0}
        for ctx in halves:
            ctx["touch_threshold"] = threshold
            values, counts = evidence.touch_llr(ctx, cfg, threshold)
            if cfg["touch.enabled"]:
                ctx["team_prox"] = ctx["team_prox"] + values
                ctx["touch_llr"] = values
            for key in totals:
                totals[key] += counts[key]
        log("[a_opus] touches: free-flight velocity change p50/p90/p95 {} m/s over {} frames -> "
            "threshold {} m/s; {} peaks, {} with a player within {:.1f} m, assigned H {} / A {}, "
            "ambiguous {}".format(
                "--" if quantiles is None else "/".join("{:.2f}".format(q) for q in quantiles),
                n_free, "--" if threshold is None else "{:.2f}".format(threshold),
                totals["peaks"], totals["near"], cfg["touch.radius"], totals[HOME], totals[AWAY],
                totals[None]))

    speed_model = None
    if cfg["dead.speed_enabled"]:
        pooled = np.concatenate([
            ctx["speed_smooth"][ctx["n_players"] >= cfg["dead.speed_min_players"]][::5]
            for ctx in halves])
        speed_model = evidence.fit_speed_model(pooled, cfg)
        if speed_model is None:
            log("[a_opus] speed model: no usable two-component fit, speed evidence off")
        else:
            log("[a_opus] speed model: slow {:.2f} +/- {:.2f} m/s ({:.0%}), fast {:.2f} +/- {:.2f}"
                " m/s".format(speed_model[0], speed_model[1], speed_model[4], speed_model[2],
                              speed_model[3]))

    calibration = calibrate_tag_codes(tag_list, halves, cfg) if cfg["tag.enabled"] else {}
    for code, entry in sorted(calibration.items()):
        log("[a_opus]   tag {:<30} agreement {:>6} on {:>6} frames -> polarity {:+d}{}, "
            "reliability {:.2f}".format(
                code, "--" if entry["agreement"] is None else "{:.1%}".format(entry["agreement"]),
                entry["frames"], entry["polarity"], " (flipped)" if entry["flipped"] else "",
                entry["reliability"]))

    logits = [np.zeros(ctx["n"]) for ctx in halves]
    weights = [0.0 for _ in halves]
    if cfg["ballfree.enabled"]:
        logits, accuracies, counts, lags = ballfree.cross_fit(halves, cfg, pitch)
        weights = [ballfree.weight_from_accuracy(acc, cfg) for acc in accuracies]
        log("[a_opus] ball-free team model: held-out agreement {} on {} targets -> weight {}"
            .format(" / ".join("--" if a is None else "{:.1%}".format(a) for a in accuracies),
                    " / ".join(str(c) for c in counts),
                    " / ".join("{:.2f}".format(w) for w in weights)))
        log("[a_opus]   held-out agreement of the logit at t+lag with the side on the ball at t: "
            + ", ".join("{:+d} f {}".format(lag, "--" if a is None else "{:.1%}".format(a))
                        for lag, a in lags))

    teams, deads = [], []
    contributions = {}
    for index, ctx in enumerate(halves):
        team = ctx["team_prox"].copy()
        if cfg["tag.enabled"]:
            team += evidence.tag_team_llr(ctx, tag_list, calibration, cfg)
        if weights[index] > 0:
            clipped = np.clip(logits[index], -cfg["ballfree.clip"], cfg["ballfree.clip"])
            ballfree_llr = np.round(weights[index] * clipped / cfg["ballfree.tau"], 6)
            # Full weight where there is no ball to look at; a share of it where the ball is in
            # sight but nobody clearly controls it (flights, duels). Never where proximity
            # already speaks, which is what the model was trained on.
            no_ball = ctx["weight"] < 0.2
            unclear = ~no_ball & (np.abs(ctx["team_prox"]) < cfg["ballfree.unclear_below"])
            team += np.where(no_ball, ballfree_llr,
                             np.where(unclear, cfg["ballfree.unclear_share"] * ballfree_llr, 0.0))
        parts = evidence.dead_components(ctx, cfg, pitch, speed_model, tag_list)
        dead = np.zeros(ctx["n"])
        for name, values in parts.items():
            dead += values
            got = contributions.setdefault(name, [0.0, 0.0])
            got[0] += float(values[values > 0].sum())
            got[1] += float(values[values < 0].sum())
        teams.append(team)
        deads.append(dead)

    def decode_all():
        scores = [(0.5 * team, -0.5 * team, dead + 0.5 * np.abs(team))
                  for team, dead in zip(teams, deads)]
        method = cfg["decode.method"]
        costs = (cfg["decode.lam_ha"], cfg["decode.lam_ad"], cfg["decode.lam_da"])
        if method == "viterbi":
            states = [decode.viterbi(*s, *costs, cfg["decode.min_dead"]) for s in scores]
        elif method == "hysteresis":
            states = [decode.hysteresis(*s, *costs, cfg["decode.min_dead"]) for s in scores]
        elif method == "vote":
            states = [decode.vote(*s, cfg["decode.vote_half"]) for s in scores]
        else:
            raise ValueError("decode.method must be viterbi, hysteresis or vote")
        return states, scores

    states_by_half, scores_by_half = decode_all()
    if cfg["absence.enabled"]:
        # Second pass: gap rates measured on the first decoding, which never looked at them.
        model = evidence.fit_absence_model(halves, states_by_half, cfg)
        if model is not None:
            first_pass = summarise(states_by_half)
            for index, ctx in enumerate(halves):
                values = evidence.absence_llr(ctx, model, cfg)
                deads[index] = deads[index] + values
                got = contributions.setdefault("absence", [0.0, 0.0])
                got[0] += float(values[values > 0].sum())
                got[1] += float(values[values < 0].sum())
            log_absence(log, model, first_pass, cfg)
            states_by_half, scores_by_half = decode_all()

    if cfg["refine.restarts"]:
        moved = []
        for index, ctx in enumerate(halves):
            states_by_half[index], shifts = decode.date_restarts(
                states_by_half[index], ctx["ball_speed_obs"], cfg["refine.restart_window"],
                cfg["refine.restart_min_rise"], cfg["decode.min_dead"])
            moved += shifts
        restarts = summarise(states_by_half)["changes"]["D->live"]
        log("[a_opus] restart dating (half-rise of the ball speed): {} of {} restarts moved, "
            "median {:+.0f} frames, p10/p90 {}".format(
                len(moved), restarts, float(np.median(moved)) if moved else 0.0,
                "/".join("{:+.0f}".format(v) for v in np.percentile(moved, [10, 90]))
                if moved else "--"))

    if cfg["refine.enabled"]:
        moved = []
        for index, ctx in enumerate(halves):
            k_home, k_away = evidence.reach_scores(ctx, cfg, (d0, sigma)) \
                if cfg["refine.gate_free"] else (ctx["c_home"], ctx["c_away"])
            states_by_half[index], shifts = decode.date_team_changes(
                states_by_half[index], k_home, k_away, cfg["refine.window"],
                cfg["refine.min_control"])
            moved += shifts
        changes = summarise(states_by_half)["changes"]
        log("[a_opus] first-touch dating: {} of {} H<->A changes moved back, median {} frames, "
            "max {}".format(len(moved), changes["H->A"] + changes["A->H"],
                            int(np.median(moved)) if moved else 0, max(moved) if moved else 0))

    labels = np.full(n_frames, "X", dtype="<U1")
    for ctx, states in zip(halves, states_by_half):
        labels[ctx["first"]:ctx["last"] + 1] = LABELS[states]

    log("[a_opus] dead-ball evidence totals (nats, +dead / -alive): " + ", ".join(
        "{} {:+.0f}/{:+.0f}".format(name, pos, neg)
        for name, (pos, neg) in sorted(contributions.items())))
    if cfg["restart.enabled"]:
        log("[a_opus] restarts found after a long gap (ball back in sight slow, then touched): "
            "{}".format(sum(ctx.get("n_restarts", 0) for ctx in halves)))
    log_checks(log, cfg, tag_list, halves, states_by_half, scores_by_half, static_speed)
    report = summarise(states_by_half)
    log("[a_opus] decoded: {} possessions, mean {:.1f} s, median {:.1f} s, under 1 s {:.0%}, "
        "under 2 s {:.0%}, under 5 s {:.0%}; home share of live frames {:.1%}".format(
            report["n_possessions"], report["mean_s"], report["median_s"], report["under_1s"],
            report["under_2s"], report["under_5s"], report["home_share"]))
    log("[a_opus]          {} stoppages, {:.1%} of graded frames, median {:.1f} s; changes {}"
        .format(report["n_dead"], report["dead_share"], report["dead_median_s"],
                ", ".join("{} {}".format(k, v) for k, v in report["changes"].items())))

    write_csv(out_path, labels)
    if evidence_path:
        write_evidence(evidence_path, n_frames, halves, teams, deads, states_by_half)
        log("[a_opus] wrote per-frame evidence (local only, never commit) to {}".format(
            evidence_path))
    log("[a_opus] wrote {} ({} rows) in {:.0f} s".format(out_path, len(labels),
                                                        time.time() - clock))
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(
        prog="python -m solution.a_opus",
        description="Candidate A: frame-level possession (H/A/D/X) for the tactical video.")
    parser.add_argument("--out", required=True, help="where to write the frame,label CSV")
    parser.add_argument("--data-dir", default=None,
                        help="match data folder (default: MTAH_DATA_DIR or ./data, see games.py)")
    parser.add_argument("--set", action="append", default=[], metavar="KEY=VALUE",
                        help="override a parameter of solution/a_opus/config.py (repeatable)")
    parser.add_argument("--evidence", default=None, metavar="PATH",
                        help="also write per-frame evidence (P0 contract names) to this .npz; "
                             "frame-level match data: keep it local, e.g. under salidas/")
    parser.add_argument("--log", default=None, metavar="PATH",
                        help="also write the log (aggregates only) to this UTF-8 text file")
    args = parser.parse_args(argv)
    try:
        games.require(["atd_meta", "atd_raw"], games.GAME, args.data_dir)
    except IOError as error:
        # The normal first-run state (DATA.md): say where it looked and how to point it elsewhere.
        print(error, file=sys.stderr)
        return 2
    if not args.log:
        run(args.out, args.data_dir, args.set, evidence_path=args.evidence)
        return 0
    folder = os.path.dirname(os.path.abspath(args.log))
    if not os.path.isdir(folder):
        os.makedirs(folder)
    with open(args.log, "w", encoding="utf-8", newline="\n") as handle:
        def log(line):
            print(line)
            handle.write(line + "\n")
            handle.flush()
        from . import __version__
        log("[a_opus] version {}; overrides: {}".format(__version__, " ".join(args.set) or "none"))
        run(args.out, args.data_dir, args.set, log=log, evidence_path=args.evidence)
    return 0
