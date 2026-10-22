"""Exact MAP segmentation of one half into H / A / D with switch costs and a minimum stoppage.

    maximise  sum_t score(state_t, t)  -  sum of the cost of every change of state

States are H, A and D, with D lasting at least min_dead frames (a stoppage of a fraction of a
second is not a stoppage). The minimum duration is handled exactly with a running sum instead of
a chain of sub-states, so the recursion is O(1) per frame and a whole half takes well under a
second in plain Python.

Ties are broken on purpose, because flights and occlusions produce exact ties:
  * between H and A, and from D to a live state, the change is placed as LATE as the evidence
    allows -- "possession stays with the last team that had it" until the new team touches it,
    and a restart happens when the ball is played, not before;
  * from a live state to D, the stoppage starts as EARLY as the evidence allows -- once the ball
    has gone out, nothing that follows is play.
"""

import numpy as np

H, A, D = 0, 1, 2
NEG = -1e300

# Backpointer codes for the stoppage state.
FROM_H, FROM_A, CONTINUE, INITIAL = 0, 1, 2, 3


def viterbi(score_h, score_a, score_d, lam_ha, lam_ad, lam_da, min_dead):
    """States (int8 array of H/A/D) for one half."""
    n = len(score_h)
    if n == 0:
        return np.empty(0, dtype=np.int8)
    k = max(int(min_dead), 1)
    eh = np.asarray(score_h, dtype=np.float64).tolist()
    ea = np.asarray(score_a, dtype=np.float64).tolist()
    cumulative = np.concatenate(([0.0], np.cumsum(np.asarray(score_d, dtype=np.float64))))
    cs = cumulative.tolist()
    ed = np.asarray(score_d, dtype=np.float64).tolist()

    hist_h = [0.0] * n
    hist_a = [0.0] * n
    back_h = bytearray(n)
    back_a = bytearray(n)
    back_d = bytearray(n)

    prev_h, prev_a, prev_d = NEG, NEG, NEG
    for t in range(n):
        if t == 0:
            cur_h, bh = eh[0], H
            cur_a, ba = ea[0], A
        else:
            # Order matters: a later candidate wins a tie, so the switch is preferred.
            best, bh = prev_h, H
            cand = prev_a - lam_ha
            if cand >= best:
                best, bh = cand, A
            cand = prev_d - lam_da
            if cand >= best:
                best, bh = cand, D
            cur_h = best + eh[t]

            best, ba = prev_a, A
            cand = prev_h - lam_ha
            if cand >= best:
                best, ba = cand, H
            cand = prev_d - lam_da
            if cand >= best:
                best, ba = cand, D
            cur_a = best + ea[t]

        # A stoppage that has lasted k frames by t either started at t-k+1 (entered from the
        # best live state at t-k) or was already mature at t-1.
        j = t - k
        if j >= 0:
            if hist_h[j] >= hist_a[j]:
                entry, bd = hist_h[j] - lam_ad, FROM_H
            else:
                entry, bd = hist_a[j] - lam_ad, FROM_A
            entry += cs[t + 1] - cs[t + 1 - k]
        elif j == -1:
            entry, bd = cs[t + 1], INITIAL  # the half opens with a stoppage
        else:
            entry, bd = NEG, INITIAL
        cont = prev_d + ed[t] if prev_d > NEG else NEG
        if cont >= entry and cont > NEG:  # a tie keeps the earlier start
            cur_d, bd = cont, CONTINUE
        else:
            cur_d = entry

        hist_h[t], hist_a[t] = cur_h, cur_a
        back_h[t], back_a[t], back_d[t] = bh, ba, bd
        prev_h, prev_a, prev_d = cur_h, cur_a, cur_d

    states = np.empty(n, dtype=np.int8)
    final = max(((prev_h, H), (prev_a, A), (prev_d, D)), key=lambda item: item[0])
    state = final[1]
    t = n - 1
    while t >= 0:
        if state == H:
            states[t] = H
            state = back_h[t]
            t -= 1
        elif state == A:
            states[t] = A
            state = back_a[t]
            t -= 1
        else:
            code = back_d[t]
            if code == CONTINUE:
                states[t] = D
                t -= 1
            elif code == INITIAL:
                states[:t + 1] = D
                t = -1
            else:
                states[t - k + 1:t + 1] = D
                t -= k
                state = H if code == FROM_H else A
    return states


def date_team_changes(states, c_home, c_away, window, min_control):
    """Date every H<->A change at the new side's first touch (study 3.2: "fechado en el primer
    toque, no en la confirmación").

    The decoder places a change where the new side's evidence has paid for it, which in a duel
    can be some frames after that side first reached the ball. Each change is moved back over
    the frames just before it in which the new side is within reach of the ball (control >=
    min_control) and at least as close to it as the old side, up to `window` frames and never
    past the start of the old possession. A flight stops it at once: nobody is within reach of a
    ball in the air, so a pass is still credited to the receiver, not the passer.

    Returns (states, list of how many frames each moved change moved).
    """
    out = np.array(states, copy=True)
    starts = np.concatenate(([0], np.flatnonzero(out[1:] != out[:-1]) + 1))
    moved = []
    for index in range(1, len(starts)):
        s = int(starts[index])
        new, old = out[s], out[s - 1]
        if new == D or old == D:
            continue
        c_new, c_old = (c_home, c_away) if new == H else (c_away, c_home)
        limit = max(s - window, int(starts[index - 1]) + 1)
        t = s
        while t - 1 >= limit and c_new[t - 1] >= min_control and c_new[t - 1] >= c_old[t - 1]:
            t -= 1
        if t < s:
            out[t:s] = new
            moved.append(s - t)
    return out, moved


def date_restarts(states, speed, window, min_rise, min_dead):
    """Date every D -> live change at the kick: where the ball's speed is halfway up its rise.

    A tracker that smooths the ball with a centred window turns a kick into a ramp of speed
    centred on the kick, so the frame at which the speed has made half of its rise is the kick
    -- whatever the smoothing width -- while a fixed speed threshold is crossed early for a soft
    kick and late for a hard one. For each restart, the rise is the climb from the slowest
    observed speed in the `window` frames before it to the fastest in the `window` frames after
    it; if it is at least min_rise m/s the restart moves to the half-way frame, keeping every
    stoppage at least min_dead frames and every live run at least one frame.

    Returns (states, list of signed moves in frames).
    """
    out = np.array(states, copy=True)
    n = len(out)
    moves = []
    starts = np.concatenate(([0], np.flatnonzero(out[1:] != out[:-1]) + 1, [n]))
    for index in range(1, len(starts) - 1):
        b = int(starts[index])
        if not (out[b - 1] == D and out[b] != D):
            continue
        dead_start, live_stop = int(starts[index - 1]), int(starts[index + 1])
        lo, hi = max(b - window, dead_start + min_dead), min(b + window, live_stop - 1)
        if hi <= lo:
            continue
        before = speed[max(b - window, 0):b + 1]
        after = speed[b:min(b + window, n)]
        if not (np.isfinite(before).any() and np.isfinite(after).any()):
            continue
        low, high = np.nanmin(before), np.nanmax(after)
        if high - low < min_rise:
            continue
        half = 0.5 * (low + high)
        segment = speed[lo:hi + 1]
        above = np.flatnonzero(np.nan_to_num(segment, nan=-1.0) >= half)
        if not len(above):
            continue
        kick = lo + int(above[0])
        if kick < b:
            out[kick:b] = out[b]
        elif kick > b:
            out[b:kick] = D
        if kick != b:
            moves.append(kick - b)
    return out, moves


def path_score(states, score_h, score_a, score_d, lam_ha, lam_ad, lam_da):
    """Objective of a given path, for tests: emissions minus switch costs."""
    scores = np.where(states == H, score_h, np.where(states == A, score_a, score_d)).sum()
    change = np.flatnonzero(states[1:] != states[:-1])
    for index in change:
        a, b = states[index], states[index + 1]
        if a == D:
            scores -= lam_da
        elif b == D:
            scores -= lam_ad
        else:
            scores -= lam_ha
    return float(scores)
