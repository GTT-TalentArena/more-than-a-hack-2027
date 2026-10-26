"""Degradation profiles of §1.2 of the plan: what a held-out match looks like through a noisier tracker.

Input is a clean match (heldout.convert): per-player tracks with identities and a ball that is
almost always located. Output is an observation in the challenge's shape: 23 anonymous slots per
team and a ball missing on 41% of each half's frames. Labels are never an input here: a profile
only ever sees positions, so the same observation is fed to every model (§1.3).
"""

import zlib

import numpy as np

FPS = 25
SLOTS_PER_TEAM = 23
MISSING_SHARE = 0.41          # DATA.md: no ball on 41% of graded frames
MAX_GAP_S = 30.0
CROWD_RADIUS_M = 5.0
FRAGMENT_MEAN_S = 60.0
NOISE_PLAYER_M = 0.10
NOISE_BALL_M = 0.20
SEEDS = (47, 48, 49)

# name: (mean gap length in s or None for no added gaps, crowd-weighted gap starts, fragment+noise)
PROFILES = {
    "clean": (None, False, False),
    "gaps-short": (0.5, False, False),
    "gaps-long": (4.0, False, False),
    "gaps-crowded": (2.0, True, False),
    "full": (2.0, True, True),
}


def rng_for(match_id, profile, seed):
    """Deterministic per (match, profile, seed); independent of call order."""
    return np.random.default_rng([seed, list(PROFILES).index(profile), zlib.crc32(match_id.encode())])


def crowd_weights(ball, players):
    """Players within CROWD_RADIUS_M of the (clean) ball, per frame; 0 where the ball is unknown."""
    with np.errstate(invalid="ignore"):
        d = np.linalg.norm(players[:, :, :2] - ball[:, None, :2], axis=2)
        return np.nansum(d < CROWD_RADIUS_M, axis=1).astype(np.float64)


def ball_gaps(missing, period, mean_s, weights, rng):
    """Extend `missing` with gaps until each half has exactly MISSING_SHARE of its frames missing.

    Gaps never cross a half, are truncated at its end and at MAX_GAP_S, and the last one is cut
    short so the half lands on the target exactly. Frames already missing count towards it.
    """
    missing = missing.copy()
    cap = int(round(MAX_GAP_S * FPS))
    for p in np.unique(period):
        idx = np.flatnonzero(period == p)
        first, last = idx[0], idx[-1]
        target = int(round(MISSING_SHARE * len(idx)))
        count = int(missing[first:last + 1].sum())
        while count < target:
            free = np.flatnonzero(~missing[first:last + 1]) + first
            if weights is not None and weights[free].sum() > 0:
                prob = weights[free] / weights[free].sum()
                start = int(rng.choice(free, p=prob))
            else:
                start = int(rng.choice(free))
            length = max(1, min(cap, int(round(rng.exponential(mean_s * FPS)))))
            for t in range(start, min(last + 1, start + length)):
                if not missing[t]:
                    missing[t] = True
                    count += 1
                    if count == target:
                        break
    return missing


def assign_slots(players, team, fragment, rng):
    """(n, 2*SLOTS_PER_TEAM, 3) slot array; team t uses slots t*23 .. t*23+22.

    Without fragmentation every player keeps one slot. With it, each continuous presence of a
    player is cut into segments of exponential length and each segment takes a free slot of the
    same team: identity switches without changing who is where.
    """
    n = len(players)
    slots = np.full((n, 2 * SLOTS_PER_TEAM, 3), np.nan, dtype=np.float32)
    busy_until = np.full(2 * SLOTS_PER_TEAM, -1)
    pieces = []
    for k in range(players.shape[1]):
        present = np.isfinite(players[:, k, 0])
        edges = np.diff(np.r_[0, present.astype(np.int8), 0])
        for a, b in zip(np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)):
            if not fragment:
                pieces.append((a, b, k))
                continue
            t = a
            while t < b:
                length = max(FPS, int(round(rng.exponential(FRAGMENT_MEAN_S * FPS))))
                pieces.append((t, min(b, t + length), k))
                t += length
    pieces.sort()
    for a, b, k in pieces:
        pool = np.arange(team[k] * SLOTS_PER_TEAM, (team[k] + 1) * SLOTS_PER_TEAM)
        free = pool[busy_until[pool] < a]
        if not len(free):
            raise ValueError("more simultaneous tracks than slots for one team")
        slot = int(rng.choice(free)) if fragment else int(free[0])
        slots[a:b, slot] = players[a:b, k]
        busy_until[slot] = b - 1
    return slots


def observe(match, match_id, profile, seed):
    """Observation dict (ball, slots) for one match, profile and seed. Pure function of positions."""
    mean_s, crowded, full = PROFILES[profile]
    rng = rng_for(match_id, profile, seed)
    ball = match["ball"].astype(np.float32).copy()
    players = match["players"].astype(np.float32).copy()
    missing = ~np.isfinite(ball[:, 0])
    if mean_s is not None:
        weights = crowd_weights(ball, players) if crowded else None
        missing = ball_gaps(missing, match["period"], mean_s, weights, rng)
    ball[missing] = np.nan
    slots = assign_slots(players, match["team"], full, rng)
    if full:
        seen = np.isfinite(slots[:, :, 0])
        slots[:, :, :2][seen] += rng.normal(0, NOISE_PLAYER_M, (int(seen.sum()), 2)).astype(np.float32)
        located = np.isfinite(ball[:, 0])
        ball[located, :2] += rng.normal(0, NOISE_BALL_M, (int(located.sum()), 2)).astype(np.float32)
    return {"ball": ball, "slots": slots}
