"""Label-free checks on a decoded match. Aggregates only: counts, shares, quantiles.

None of these is optimised against; they are what the log reports so that a person (or the LLM
that wrote this, under protocol A7) can tell whether the decoder behaves sensibly on the real
data without anyone looking at a frame of it.
"""

import numpy as np

from . import decode
from .features import merged_runs
from .tags import SET_PIECES

FPS = 25


def composition(halves, states_by_half, static_speed):
    """What the ball is doing in decoded dead frames and in decoded live frames (shares)."""
    out = {}
    for name, pick in (("dead", lambda s: s == decode.D), ("live", lambda s: s != decode.D)):
        total = seen = fast = outside = still = 0
        for ctx, states in zip(halves, states_by_half):
            mask = pick(states)
            obs = ctx["obs"] & mask
            speed = np.nan_to_num(ctx["ball_speed_obs"])
            slow = np.nan_to_num(ctx["ball_speed_slow"], nan=99.0)
            total += int(mask.sum())
            seen += int(obs.sum())
            fast += int(np.sum(obs & (speed >= 6.0) & (ctx["inside_dist"] >= 1.0)))
            outside += int(np.sum(obs & (ctx["out_dist"] > 0.5)))
            still += int(np.sum(obs & (slow < static_speed)))
        total = max(total, 1)
        out[name] = {"frames": total, "seen": seen / float(total), "fast": fast / float(total),
                     "outside": outside / float(total), "still": still / float(total)}
    return out


def ignored_control(halves, states_by_half):
    """Runs of clear control by the side the decoder says does NOT have the ball, while live.

    Many long ones would mean real possessions are being missed; short ones are expected
    (duels, marking, tracking noise). Returned as counts per length bucket in frames.
    """
    buckets = {"10-24": 0, "25-49": 0, "50+": 0}
    for ctx, states in zip(halves, states_by_half):
        home_has_it = ctx["c_home"] > ctx["c_away"]
        live = states != decode.D
        against = ctx["confident"] & live & (home_has_it != (states == decode.H))
        starts, stops = merged_runs(against, 5)
        for start, stop in zip(starts, stops):
            length = int(against[start:stop].sum())
            if length >= 50:
                buckets["50+"] += 1
            elif length >= 25:
                buckets["25-49"] += 1
            elif length >= 10:
                buckets["10-24"] += 1
    return buckets


def setpiece_timing(tag_list, halves, states_by_half, slack=25):
    """Window lengths of the tagged set pieces and where the decoded restart falls in them.

    Returns (n_windows, length quantiles s, n_with_restart, offset-from-start quantiles s,
    offset-as-fraction quantiles, stoppage-start-minus-window-start quantiles s). A restart is a
    decoded D -> live change within the window +/- slack frames; the first one is used, and the
    stoppage is the decoded dead run that it ends.
    """
    lengths, offsets, fractions, dead_starts = [], [], [], []
    for ctx, states in zip(halves, states_by_half):
        restarts = np.flatnonzero((states[1:] != decode.D) & (states[:-1] == decode.D)) + 1
        entries = np.flatnonzero((states[1:] == decode.D) & (states[:-1] != decode.D)) + 1
        for tag in tag_list:
            if tag["code"] != SET_PIECES:
                continue
            start, end = tag["start"] - ctx["first"], tag["end"] - ctx["first"]
            if end < 0 or start >= ctx["n"]:
                continue
            lengths.append((end - start) / float(FPS))
            inside = restarts[(restarts >= start - slack) & (restarts <= end + slack)]
            if len(inside):
                offsets.append((inside[0] - start) / float(FPS))
                fractions.append((inside[0] - start) / float(max(end - start, 1)))
                before = entries[entries < inside[0]]
                if len(before):
                    dead_starts.append((before[-1] - start) / float(FPS))

    def q(values):
        return tuple(float(v) for v in np.percentile(values, [10, 50, 90])) if values else None

    return len(lengths), q(lengths), len(offsets), q(offsets), q(fractions), q(dead_starts)


def switch_cost_curve(scores_by_half, cfg, lams):
    """Possession and change counts if the match were decoded with other H<->A switch costs."""
    rows = []
    for lam in lams:
        states = [decode.viterbi(sh, sa, sd, lam, cfg["decode.lam_ad"], cfg["decode.lam_da"],
                                 cfg["decode.min_dead"]) for sh, sa, sd in scores_by_half]
        rows.append((lam, states))
    return rows
