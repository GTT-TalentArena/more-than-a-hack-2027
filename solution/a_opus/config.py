"""Every tunable number of candidate A, in one table, in physical units.

None of these values was fitted to the public ground truth. Each one was set a priori from what is
documented about the data (DATA.md, EVALUATION.md) and from football and tracking knowledge, and
the comment next to it says why. Several are not used as given but re-estimated from the match
itself without labels (marked "self-calibrated"): the control radius, the dead-ball speed model,
the polarity and reliability of each Smart Tagging code and the weight of the ball-free team model.

Units: metres, seconds converted to frames at 25 fps, and "nats" for evidence. A nat is one unit of
log-likelihood; the decoder adds evidence across frames and pays a fixed number of nats for every
change of state, so the ratio between the two is what decides how much evidence a change needs.

Override any value from the command line without editing this file:

    python -m solution.a_opus --out x.csv --set decode.lam_ha=8 --set ballfree.enabled=0
"""

FPS = 25

DEFAULTS = {
    # -- ball track cleaning -------------------------------------------------------------------
    # A detection further than this from the median of its neighbours (+/- spike_window frames,
    # with neighbours on both sides) is a jump, not a ball: 3 m in 3 frames is 25 m/s off-track.
    "ball.spike_window": 3,
    "ball.spike_dist": 3.0,
    # A detection with no other one within +/- isolated_window frames is trusted less.
    "ball.isolated_window": 5,
    "ball.isolated_weight": 0.3,
    # Local linear fit for velocity: +/- 4 frames (0.36 s), at least 5 points. Shorter is too
    # noisy at a few tens of centimetres of position noise, longer smears kicks.
    "ball.vel_half_window": 4,
    "ball.vel_min_points": 5,
    # A second, slow fit (+/- 1 s) only to tell a still ball from a slow one: with ~0.25 m of
    # position noise the short fit reads ~1 m/s for a ball that is not moving at all.
    "ball.still_half_window": 12,
    "ball.still_min_points": 10,
    # Gaps up to 2 s are bridged by straight-line interpolation (used with a decaying weight).
    "ball.interp_max_gap": 50,
    # Relative lag of the ball track behind the players, measured on carried balls (the delta
    # that brings the ball closest to the nearest player's feet). self-calibrated: applied only
    # if it is at least 2 frames and fits >= 5% better than no shift.
    "ball.lag_correction": 1,
    "ball.lag_max": 12,
    "ball.lag_min_gain": 0.05,

    # Players further than this outside the pitch lines are bench, warm-up or tracking noise.
    "players.area_margin": 3.0,
    "players.vel_half_window": 3,
    "players.vel_min_points": 4,

    # -- team evidence: who controls the ball ----------------------------------------------------
    # Nats per frame for a ball inside one team's control zone and outside the other's. Frames
    # are strongly correlated, so this is deliberately well below a calibrated per-frame LLR.
    "team.alpha": 0.4,
    # Control kernel K(d) = exp(-0.5 * (max(d - d0, 0) / sigma_d)^2). self-calibrated: d0 and
    # sigma_d are scaled from the median nearest-player distance of slow balls in this match,
    # clamped to the ranges below; the defaults apply when that statistic cannot be computed.
    "team.calibrate": 1,
    "team.d0": 0.75,
    "team.sigma_d": 1.0,
    "team.d0_range": (0.4, 1.5),
    "team.sigma_range": (0.6, 2.0),
    # A ball moving much faster than the nearest player is passing by, not controlled.
    "team.v0": 1.5,
    "team.sigma_v": 3.0,
    "team.unknown_gate": 0.6,  # gate used when the ball velocity cannot be estimated
    # Interpolated frames count at weight interp_weight * exp(-gap / interp_tau).
    "team.interp_weight": 0.5,
    "team.interp_tau": 25.0,
    # Proximity evidence below this is set to exactly 0, so the decoder sees exact ties in
    # flights and can apply "possession stays with the last team until the new one touches it".
    "team.zero_below": 0.01,

    # -- touches (study 3.1, P3): the ball changes velocity next to one side's player ------------
    # v1.4: the net velocity change |v(t..t+6) - v(t-6..t)| replaces v1.3's point acceleration,
    # which found only 70 touches in the real match (the ATD smooths the ball, flattening the
    # peaks). A touch is a peak above the touch.quantile of free-flight changes (self-calibrated,
    # never below touch.floor m/s), with the nearest player -- closest distance within
    # +/- touch.reach_window frames -- within touch.radius and touch.margin closer than any
    # opponent. 1.5 nats: less than lam_ha, so a touch alone (a deflection, a block) changes
    # nothing.
    # v1.5: the half-window is chosen per match among touch.scales (self-calibrated): the real
    # ATD smooths the ball over ~1 s, and at +/- 6 frames v1.4 found only 422 peaks.
    "touch.enabled": 1,
    "touch.scales": (6, 12, 25),
    # v1.6: the reference for the threshold is a free GROUND ball (both chords under this speed);
    # long aerial balls, projected along curved paths, inflated it to 12 m/s in v1.5.
    "touch.ground_speed": 12.0,
    "touch.quantile": 0.95,
    "touch.floor": 3.0,
    "touch.radius": 2.0,
    "touch.margin": 0.75,
    "touch.reach_window": 3,
    "touch.beta": 1.5,
    "touch.spread": 5,
    # Restart after a long gap: the ball reappears slow (held or placed, median speed <= 2 m/s)
    # and the first touch within 5 s is the restart (study 3.4).
    "restart.enabled": 1,
    "restart.search": 125,
    "restart.hold_speed": 2.0,
    "restart.hold_beta": 0.05,
    "restart.beta": 0.5,

    # -- Smart Tagging phases as a weak team prior -----------------------------------------------
    "tag.enabled": 1,
    "tag.beta": 0.03,              # nats per frame for a fully reliable code
    "tag.max_per_frame": 0.06,     # cap when instances overlap
    "tag.min_calib_frames": 100,   # below this many confident frames a code keeps its prior
    "tag.default_reliability": 0.3,
    "tag.full_agreement": 0.8,     # agreement with ball proximity that counts as fully reliable

    # -- ball-free team model (self-trained on this match, cross-fitted by half) -----------------
    "ballfree.enabled": 1,
    "ballfree.tau": 40.0,          # frames of correlation: per-frame evidence = logit / tau
    "ballfree.clip": 3.0,
    "ballfree.acc_floor": 0.55,    # held-out agreement at or below this -> weight 0
    "ballfree.acc_full": 0.75,     # at or above this -> full weight
    "ballfree.l2": 1.0,
    "ballfree.subsample": 3,
    "ballfree.min_train": 2000,
    # v1.5: where the ball is in sight but nobody clearly controls it (|proximity llr| below
    # unclear_below: flights, duels, a smoothed ball between players) the ball-free evidence
    # counts at unclear_share of its weight. Half, not all: the real model agrees 86% held-out
    # against 97% on the synthetic matches where full weight was best, and at half weight it
    # takes over 6 s of confidently wrong frames in a row to invent a blip.
    "ballfree.unclear_below": 0.02,
    "ballfree.unclear_share": 0.5,

    # -- dead-ball evidence ----------------------------------------------------------------------
    # Ball observed beyond a line by more than out_margin metres; the interpolated path between
    # the last sighting inside and the first outside dates the crossing.
    "dead.out_margin": 0.5,
    "dead.out_beta": 1.0,           # nats per sighting outside
    "dead.out_cross_beta": 0.5,     # nats per interpolated frame beyond the line
    "dead.out_run_cap": 30.0,       # nats per excursion
    "dead.out_merge_gap": 10,       # frames: out observations this close form one run
    "dead.out_reentry_window": 25,  # back inside within 1 s, moving -> probably a ball in the air
    "dead.out_reentry_inside": 2.0,
    "dead.out_reentry_factor": 0.3,
    # Last sighting near a line, heading out, then a long gap: probably went out.
    "dead.exit_gap_min": 38,
    "dead.exit_line_dist": 2.0,
    "dead.exit_out_speed": 2.0,
    "dead.exit_total": 3.0,
    "dead.exit_frames": 12,
    # Ball standing still: a set piece being prepared, more so on a restart spot. The threshold
    # is raised to 2.5x the noise of the slow fit if the measured position noise demands it
    # (self-calibrated).
    "dead.static_speed": 0.6,
    "dead.static_merge_gap": 5,
    "dead.static_min_frames": 25,
    "dead.static_beta": 0.06,
    "dead.static_spot_mult": 3.0,     # corner arc, centre spot
    "dead.static_box_mult": 2.0,      # goal area, penalty spot
    "dead.static_attached_dist": 1.0, # ball glued to a player (e.g. a keeper holding it): weaker
    "dead.static_attached_frac": 0.6,
    "dead.static_attached_mult": 0.3,
    # The kick that ends a static ball: alive evidence on the frames right after it (5 nats in
    # all -- enough to end a stoppage, not enough to end one on its own if the ball is merely
    # re-placed while the other evidence still says dead).
    "dead.kick_speed": 5.0,
    "dead.kick_search_ahead": 25,
    "dead.kick_window": 10,
    "dead.kick_beta": 0.5,
    # A fast ball inside the pitch is a ball in play.
    "dead.fast_speed": 6.0,
    "dead.fast_inside": 1.0,
    "dead.fast_beta": 0.08,
    # Collective speed. self-calibrated: a two-component Gaussian mixture on the smoothed mean
    # player speed of this match; evidence = clipped LLR / speed_tau per frame.
    "dead.speed_enabled": 1,
    # Light smoothing only: the mean over ~20 players is already smooth, and a wide centred
    # window leaks the next restart's acceleration backwards into the stoppage.
    "dead.speed_smooth": 6,
    "dead.speed_tau": 25.0,
    "dead.speed_clip": 3.0,
    "dead.speed_min_players": 10,
    "dead.speed_min_separation": 0.25,
    # The speed term may not argue for a stoppage where the ball is seen moving (>= 2.5 m/s,
    # inside the pitch) on at least 20% of the surrounding +/- 1 s.
    "dead.speed_gate_speed": 2.5,
    "dead.speed_gate_window": 25,
    "dead.speed_gate_frac": 0.2,
    # Kick-off formation: everybody in their own half, slow, ball on the centre spot.
    "dead.kickoff_beta": 0.15,
    "dead.kickoff_own_half_frac": 0.9,
    "dead.kickoff_min_players": 14,
    "dead.kickoff_max_speed": 2.0,
    "dead.kickoff_ball_radius": 3.0,
    "dead.kickoff_smooth": 12,
    # Smart Tagging set pieces: the restart is inside the window, ~3.5 s after it opens (DATA.md,
    # starter/01). Dead before the restart, alive after the window closes.
    "dead.setpiece_enabled": 1,
    "dead.setpiece_beta": 0.06,
    "dead.setpiece_pre": 50,
    "dead.setpiece_frac": 0.5,
    "dead.setpiece_max_dead": 75,   # frames after the window opens (3 s, before the ~3.5 s kick)
    "dead.setpiece_post": 25,
    "dead.setpiece_kickoff_pre": 250,

    # -- P3: the P2 detector (#14) as one more dead-ball term (p2.py) -----------------------------
    # Off in candidate A as delivered (v1.6, frozen). On: D over each confirmed preparation and
    # before each first kick-off, at the same per-frame scale as the set-piece and still-ball
    # terms times P2's confidence, and alive just after the restart P2 confirmed. P2's own exits
    # weigh 0: out_of_bounds_llr and exit_llr already count them.
    "p2.enabled": 0,
    "p2.dead_beta": 0.06,
    "p2.restart_beta": 0.2,
    "p2.restart_post": 25,
    "p2.exit_beta": 0.0,

    # -- absence of the ball (study 3.3, L4) ------------------------------------------------------
    # The first real run answered L4 without labels: the ball is seen on 91% of the frames
    # decoded live and on 24% of those decoded dead, so a long absence is evidence of a stoppage.
    # Every frame of a gap of at least 2 s carries scale * (logit(share in gaps) - logit(share
    # overall)) / tau nats, the shares being the fractions of long-gap frames and of all frames
    # that a first decoding which ignores visibility put in D (one hard-EM step, self-calibrated).
    # scale 0.5 because that first decoding sees more "live" evidence where the ball is visible,
    # which inflates the association somewhat. Shorter gaps carry nothing: flicker is not a
    # stoppage.
    "absence.enabled": 1,
    "absence.min_gap": 50,
    "absence.tau": 25.0,
    "absence.scale": 0.5,
    "absence.clip": (-3.0, 3.0),

    # -- boundary dating (study 3.2, 4.6, P5) ------------------------------------------------------
    # A change of team is dated at the new side's first touch: the switch moves back over the
    # frames just before it in which the new side is at least as close to the ball as the old one
    # and within reach (control >= refine.min_control), up to refine.window frames.
    "refine.enabled": 1,
    "refine.window": 25,
    "refine.min_control": 0.3,
    # Tried in v1.5 and left off (no gain on the heavily smoothed synthetic match, -0.003): the
    # "within reach" clock without the speed gate, and restarts dated at the half-rise of the
    # ball's speed. Both are kept behind these switches for the record.
    "refine.gate_free": 0,
    "refine.restarts": 0,
    "refine.restart_window": 25,
    "refine.restart_min_rise": 3.0,

    # -- decoder ---------------------------------------------------------------------------------
    # Cost of a change of state, in nats. A possession change needs ~lam_ha nats of evidence for
    # the new team; a blip inside a possession needs twice that. With team.alpha = 0.4 that is
    # ~10 frames of clear control to change and ~20 to blip, so deflections and one-touch
    # contacts do not change possession, as CHALLENGE.md asks. v1.0 used 5; v1.1 used 4 because
    # the first real run decoded only 48 direct H<->A changes in the whole match (football has
    # a turnover in open play every ~30 s of live ball, so that is too few). v1.3 uses 3: the
    # touch evidence makes a change's evidence sharper and better placed, every synthetic sweep
    # prefers 3, and the real match is still under-segmented (185 possessions, 71 direct
    # changes). A blip inside a possession still needs 6 nats: four opponent touches, or a
    # touch and ~11 frames of clear control.
    "decode.lam_ha": 3.0,
    # viterbi (the candidate), or the alternatives compared in #16: hysteresis (CUSUM with
    # retro-dating, same costs) and vote (windowed majority of the same evidence, +/- vote_half).
    "decode.method": "viterbi",
    "decode.vote_half": 25,
    "decode.lam_ad": 4.0,          # alive -> dead
    "decode.lam_da": 4.0,          # dead -> alive
    "decode.min_dead": 50,         # frames: a stoppage lasts at least 2 s
}


def parse_value(text):
    """'8' -> 8, '0.5' -> 0.5, '1,2' -> (1.0, 2.0), anything else stays a string."""
    if "," in text:
        return tuple(float(part) for part in text.split(","))
    for cast in (int, float):
        try:
            return cast(text)
        except ValueError:
            pass
    return text


def build(overrides=()):
    """DEFAULTS with KEY=VALUE overrides applied. Unknown keys are an error, not a no-op."""
    cfg = dict(DEFAULTS)
    for item in overrides:
        if "=" not in item:
            raise ValueError("--set expects KEY=VALUE, got {!r}".format(item))
        key, value = item.split("=", 1)
        key = key.strip()
        if key not in cfg:
            raise KeyError("unknown parameter {!r}; see solution/a_opus/config.py".format(key))
        cfg[key] = parse_value(value.strip())
    # A list parameter given as one number on the command line ("--set touch.scales=6").
    scales = cfg["touch.scales"]
    cfg["touch.scales"] = tuple(int(s) for s in
                                (scales if isinstance(scales, (tuple, list)) else (scales,)))
    return cfg
