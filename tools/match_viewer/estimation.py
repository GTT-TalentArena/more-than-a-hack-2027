"""Conservative, display-only interpolation. Original observations stay untouched."""

import math

MAX_GAP_SECONDS = 2
GRACE_SECONDS = 0.6
MAX_SPEED_M_S = 12
ANCHOR_FRAMES = 3
MIN_SEPARATION_M = 0.8
TEAM_CAPACITY = 11


def _distance(a, b):
    return math.hypot(a[0] - b[0], a[1] - b[1])


def estimated_window(source, start, count, diagnostics=None):
    """Add separate player estimates with enough halo for seek-independent results.

    Both ends and three observations on either side must exist in the same half.
    Speed, endpoint continuity, team capacity and same-team collisions are gates,
    not identity recognition or calibrated confidence. Long losses get at most
    0.6 seconds of decelerating prediction with a fading display weight. Never
    estimate the ball. Display weights are not probabilities.
    """
    max_gap = int(source.fps * MAX_GAP_SECONDS)
    halo = max_gap + ANCHOR_FRAMES
    first, end = max(0, start - halo), min(source.n_frames, start + count + halo)
    rows = source.window(first, end - first)
    slots = len(source.slot_ids)
    estimates = [[None] * slots for _ in rows]
    fades = [[0] * slots for _ in rows]
    counts = [{team: sum(point is not None and source.teams[slot] == team
                         for slot, point in enumerate(row['players'])) for team in ('H', 'A')}
              for row in rows]
    def note(reason):
        if diagnostics is not None:
            diagnostics[reason] = diagnostics.get(reason, 0) + 1

    def allowed(current, slot, xy):
        team = source.teams[slot]
        return 0 < counts[current][team] < TEAM_CAPACITY and not any(
            point is not None and source.teams[other] == team and _distance(xy, point) < MIN_SEPARATION_M
            for other, point in enumerate(rows[current]['players']))

    def grace(gap_start, gap_end, slot, lo, hi):
        """A long loss gets only a brief decelerating fade, never a full bridge."""
        grace_frames = max(1, int(source.fps * GRACE_SECONDS))
        if gap_start - ANCHOR_FRAMES < lo or gap_start + grace_frames > hi:
            return
        anchor = [row['players'][slot] for row in rows[gap_start - ANCHOR_FRAMES:gap_start]]
        if any(point is None for point in anchor) or any(
                _distance(a, b) * source.fps > MAX_SPEED_M_S for a, b in zip(anchor, anchor[1:])):
            return
        velocity = [(anchor[-1][axis] - anchor[0][axis]) * source.fps / (ANCHOR_FRAMES - 1)
                    for axis in (0, 1)]
        for age, current in enumerate(range(gap_start, min(gap_end, gap_start + grace_frames)), 1):
            t = age / source.fps
            elapsed = t - t * t / (2 * GRACE_SECONDS)
            xy = [anchor[-1][axis] + velocity[axis] * elapsed for axis in (0, 1)]
            if not allowed(current, slot, xy):
                break
            estimates[current][slot] = xy
            fades[current][slot] = 1 - age / (grace_frames + 1)
            note('grace_samples')
    for _, block_start, block_end in source.blocks:
        lo, hi = max(first, block_start) - first, min(end, block_end + 1) - first
        if lo >= hi:
            continue
        for slot, team in enumerate(source.teams):
            index = lo
            while index < hi:
                if rows[index]['players'][slot] is not None:
                    index += 1
                    continue
                gap_start = index
                while index < hi and rows[index]['players'][slot] is None:
                    index += 1
                gap_end = index
                if (gap_end - gap_start > max_gap or gap_start - ANCHOR_FRAMES < lo
                        or gap_end + ANCHOR_FRAMES > hi):
                    note('length_or_boundary')
                    if gap_end - gap_start > max_gap:
                        grace(gap_start, gap_end, slot, lo, hi)
                    continue
                before = [row['players'][slot] for row in rows[gap_start - ANCHOR_FRAMES:gap_start]]
                after = [row['players'][slot] for row in rows[gap_end:gap_end + ANCHOR_FRAMES]]
                if any(point is None for point in before + after):
                    note('missing_anchors')
                    continue
                # Estimate only when the visible endpoints are locally continuous.
                if any(_distance(a, b) * source.fps > MAX_SPEED_M_S
                       for anchor in (before, after) for a, b in zip(anchor, anchor[1:])):
                    note('anchor_speed')
                    continue
                a, b = before[-1], after[0]
                duration = (gap_end - gap_start + 1) / source.fps
                if _distance(a, b) / duration > MAX_SPEED_M_S:
                    note('bridge_speed')
                    continue
                velocity_before = [(a[axis] - before[0][axis]) * source.fps / (ANCHOR_FRAMES - 1)
                                   for axis in (0, 1)]
                velocity_after = [(after[-1][axis] - b[axis]) * source.fps / (ANCHOR_FRAMES - 1)
                                  for axis in (0, 1)]
                tolerance = 3 + 3 * duration
                if (_distance([a[axis] + velocity_before[axis] * duration for axis in (0, 1)], b) > tolerance
                        or _distance([b[axis] - velocity_after[axis] * duration for axis in (0, 1)], a) > tolerance):
                    note('endpoint_continuity')
                    continue
                proposed = []
                for current in range(gap_start, gap_end):
                    fraction = (current - gap_start + 1) / (gap_end - gap_start + 1)
                    xy = [a[axis] + (b[axis] - a[axis]) * fraction for axis in (0, 1)]
                    # Do not bridge an empty team, a full team, or an apparent duplicate.
                    if not allowed(current, slot, xy):
                        note('team_capacity_or_duplicate')
                        break
                    proposed.append(xy)
                if len(proposed) == gap_end - gap_start:
                    note('accepted_before_competition')
                    for current, xy in zip(range(gap_start, gap_end), proposed):
                        estimates[current][slot] = xy
                        fades[current][slot] = 1
    # Competing estimates are ambiguous: drop both, independent of slot order.
    result = []
    for index in range(start - first, min(start + count, source.n_frames) - first):
        candidates = estimates[index]
        rejected = set()
        for team in ('H', 'A'):
            active = [slot for slot, point in enumerate(candidates)
                      if point is not None and source.teams[slot] == team]
            if counts[index][team] + len(active) > TEAM_CAPACITY:
                rejected.update(active)
            for position, slot in enumerate(active):
                for other in active[position + 1:]:
                    if _distance(candidates[slot], candidates[other]) < MIN_SEPARATION_M:
                        rejected.update((slot, other))
        result.append({**rows[index], 'player_estimates': [None if slot in rejected else point
                                                        for slot, point in enumerate(candidates)],
                       'player_estimate_fade': [0 if slot in rejected else value
                                                for slot, value in enumerate(fades[index])]})
    return result
