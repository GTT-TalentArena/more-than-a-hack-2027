"""Per-frame geometry: a cleaned ball track, velocities, who is near the ball, team shape.

Everything works on one half at a time (a few tens of thousands of frames), vectorised over frames
and track slots. NaN means "not observed" throughout; nothing is filled in silently.
"""

import warnings

import numpy as np

from .atd import HOME, AWAY


def runs(mask):
    """(starts, stops) of the True runs of a boolean array, half-open."""
    edges = np.diff(np.concatenate(([0], np.asarray(mask, dtype=np.int8), [0])))
    return np.flatnonzero(edges == 1), np.flatnonzero(edges == -1)


def merged_runs(mask, max_gap):
    """Runs of True, joining runs separated by at most max_gap False frames."""
    starts, stops = runs(mask)
    if len(starts) == 0:
        return starts, stops
    keep = np.concatenate(([True], (starts[1:] - stops[:-1]) > max_gap))
    first = np.flatnonzero(keep)
    last = np.concatenate((first[1:] - 1, [len(starts) - 1]))
    return starts[first], stops[last]


def centred_sum(values, half):
    """Sum over a centred window of +/- half frames along axis 0 (zero outside the array)."""
    cumulative = np.cumsum(values, axis=0, dtype=np.float64)
    cumulative = np.concatenate([np.zeros((1,) + values.shape[1:]), cumulative], axis=0)
    index = np.arange(values.shape[0])
    high = np.minimum(values.shape[0], index + half + 1)
    low = np.maximum(0, index - half)
    return cumulative[high] - cumulative[low]


def nan_moving_mean(values, half):
    """Centred moving mean ignoring NaN; NaN where the window has no observation."""
    valid = np.isfinite(values)
    total = centred_sum(np.where(valid, values, 0.0), half)
    count = centred_sum(valid.astype(np.float64), half)
    with np.errstate(invalid="ignore", divide="ignore"):
        out = total / count
    out[count == 0] = np.nan
    return out


def local_slope(values, half, min_points):
    """Least-squares slope per frame over +/- half frames, using observed points only.

    Works along axis 0 for 1-D or 2-D arrays. NaN where fewer than min_points are observed or
    they all sit on one side of the frame.
    """
    valid = np.isfinite(values)
    filled = np.where(valid, values, 0.0).astype(np.float64)
    weight = valid.astype(np.float64)
    n = values.shape[0]
    s0 = np.zeros(values.shape)
    s1 = np.zeros(values.shape)
    s2 = np.zeros(values.shape)
    sx = np.zeros(values.shape)
    skx = np.zeros(values.shape)
    for k in range(-half, half + 1):
        if k < 0:
            src, dst = slice(0, n + k), slice(-k, n)
        elif k > 0:
            src, dst = slice(k, n), slice(0, n - k)
        else:
            src = dst = slice(0, n)
        w = weight[src]
        x = filled[src]
        s0[dst] += w
        s1[dst] += k * w
        s2[dst] += k * k * w
        sx[dst] += x
        skx[dst] += k * x
    denominator = s0 * s2 - s1 * s1
    with np.errstate(invalid="ignore", divide="ignore"):
        slope = (s0 * skx - s1 * sx) / denominator
    slope[(s0 < min_points) | (denominator < 1e-6)] = np.nan
    return slope


def local_curvature(values, half, min_points):
    """Second derivative per frame from a local quadratic least-squares fit over +/- half frames
    (observed points only), in units per frame squared. NaN where fewer than min_points are
    observed or the fit is degenerate."""
    valid = np.isfinite(values)
    filled = np.where(valid, values, 0.0).astype(np.float64)
    weight = valid.astype(np.float64)
    n = values.shape[0]
    s = [np.zeros(n) for _ in range(5)]   # sum of w * k^p, p = 0..4
    r = [np.zeros(n) for _ in range(3)]   # sum of w * k^p * x, p = 0..2
    for k in range(-half, half + 1):
        if k < 0:
            src, dst = slice(0, n + k), slice(-k, n)
        elif k > 0:
            src, dst = slice(k, n), slice(0, n - k)
        else:
            src = dst = slice(0, n)
        w = weight[src]
        x = filled[src]
        for p in range(5):
            s[p][dst] += w * k ** p
        for p in range(3):
            r[p][dst] += x * k ** p
    # Cramer's rule for the quadratic coefficient of [[s0 s1 s2] [s1 s2 s3] [s2 s3 s4]] c = r.
    det = (s[0] * (s[2] * s[4] - s[3] * s[3]) - s[1] * (s[1] * s[4] - s[3] * s[2])
           + s[2] * (s[1] * s[3] - s[2] * s[2]))
    num = (s[0] * (s[2] * r[2] - s[3] * r[1]) - s[1] * (s[1] * r[2] - s[2] * r[1])
           + r[0] * (s[1] * s[3] - s[2] * s[2]))
    with np.errstate(invalid="ignore", divide="ignore"):
        quadratic = num / det
    quadratic[(s[0] < min_points) | (np.abs(det) < 1e-6)] = np.nan
    return 2.0 * quadratic


def velocity_change(bx, by, half):
    """|v after - v before| per frame (units per frame): the net change of the ball's velocity
    across t, from the chords (b[t] - b[t-half]) / half and (b[t+half] - b[t]) / half.

    Unlike a point acceleration this does not depend on how sharp a kick looks after the
    tracker's smoothing -- a pass or a reception changes the velocity by metres per second
    whatever the smoothing, as long as half is wider than it. NaN where any of the three points
    is missing.
    """
    return velocity_change_parts(bx, by, half)[0]


def velocity_change_parts(bx, by, half):
    """(change, chord speed before, chord speed after), all in units per frame (see above)."""
    n = len(bx)
    out = [np.full(n, np.nan) for _ in range(3)]
    if n <= 2 * half:
        return out
    t = np.arange(half, n - half)
    before_x = (bx[t] - bx[t - half]) / half
    before_y = (by[t] - by[t - half]) / half
    after_x = (bx[t + half] - bx[t]) / half
    after_y = (by[t + half] - by[t]) / half
    out[0][t] = np.hypot(after_x - before_x, after_y - before_y)
    out[1][t] = np.hypot(before_x, before_y)
    out[2][t] = np.hypot(after_x, after_y)
    return out


def window_min(values, half):
    """Minimum over a centred window of +/- half frames (inf-padded)."""
    out = np.array(values, dtype=np.float64, copy=True)
    for k in range(1, half + 1):
        out[:-k] = np.minimum(out[:-k], values[k:])
        out[k:] = np.minimum(out[k:], values[:-k])
    return out


def touch_frames(acc, seen, threshold, peak_half):
    """Frames where the ball's acceleration peaks above threshold: kicks, receptions, deflections."""
    a = np.where(seen & np.isfinite(acc), acc, 0.0)
    peak = a >= threshold
    for k in range(1, peak_half + 1):
        peak &= a >= np.concatenate((a[k:], np.zeros(k)))
        peak &= a > np.concatenate((np.zeros(k), a[:-k]))
    return np.flatnonzero(peak)


def despike(bx, by, half, max_dist):
    """Mask of detections far from the median of their neighbours on both sides."""
    n = len(bx)
    seen = np.isfinite(bx)
    neighbours_x, neighbours_y = [], []
    left = np.zeros(n, dtype=np.int16)
    right = np.zeros(n, dtype=np.int16)
    for k in range(-half, half + 1):
        if k == 0:
            continue
        shifted_x = np.full(n, np.nan)
        shifted_y = np.full(n, np.nan)
        if k < 0:
            shifted_x[-k:], shifted_y[-k:] = bx[:n + k], by[:n + k]
        else:
            shifted_x[:n - k], shifted_y[:n - k] = bx[k:], by[k:]
        present = np.isfinite(shifted_x)
        if k < 0:
            left += present
        else:
            right += present
        neighbours_x.append(shifted_x)
        neighbours_y.append(shifted_y)
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        median_x = np.nanmedian(np.vstack(neighbours_x), axis=0)
        median_y = np.nanmedian(np.vstack(neighbours_y), axis=0)
    deviation = np.hypot(bx - median_x, by - median_y)
    return seen & (left > 0) & (right > 0) & (deviation > max_dist)


def second_difference(bx, by, seen):
    """|b[t+1] - 2 b[t] + b[t-1]| per axis over consecutive detections: for smooth motion this
    is position noise times sqrt(6), so its median measures the noise of this track."""
    both = seen[2:] & seen[1:-1] & seen[:-2]
    dx = (bx[2:] - 2 * bx[1:-1] + bx[:-2])[both]
    dy = (by[2:] - 2 * by[1:-1] + by[:-2])[both]
    return np.abs(np.concatenate([dx, dy]))


def isolated(seen, half):
    """Detections with no other detection within +/- half frames."""
    count = centred_sum(seen.astype(np.float64), half)
    return seen & (count <= 1.0)


def interpolate(bx, by, seen, max_gap):
    """Straight-line fill of gaps up to max_gap frames between two detections.

    Returns (x, y, filled_mask, gap_length, vx, vy) where vx, vy are the chord velocity across the
    gap in metres per frame (the only velocity an interpolated frame has).
    """
    n = len(bx)
    index = np.arange(n)
    previous = np.maximum.accumulate(np.where(seen, index, -1))
    following = np.where(seen, index, n)
    following = np.minimum.accumulate(following[::-1])[::-1]
    gap = following - previous - 1
    fill = (~seen) & (previous >= 0) & (following < n) & (gap <= max_gap)
    x = bx.astype(np.float64).copy()
    y = by.astype(np.float64).copy()
    vx = np.full(n, np.nan)
    vy = np.full(n, np.nan)
    if fill.any():
        p = previous[fill]
        f = following[fill]
        frac = (index[fill] - p) / (f - p).astype(np.float64)
        x[fill] = bx[p] + frac * (bx[f] - bx[p])
        y[fill] = by[p] + frac * (by[f] - by[p])
        vx[fill] = (bx[f] - bx[p]) / (f - p)
        vy[fill] = (by[f] - by[p]) / (f - p)
    gap_length = np.where(fill, gap, 0)
    return x, y, fill, gap_length, vx, vy


def shift_track(values, delta):
    """values[t + delta] at t (NaN past the ends): delta > 0 moves a lagging track earlier."""
    out = np.full_like(values, np.nan)
    if delta > 0:
        out[:-delta] = values[delta:]
    elif delta < 0:
        out[-delta:] = values[:delta]
    else:
        out[:] = values
    return out


def ball_lag_profile(bx, by, px, py, frames, slots, max_lag, half=4, step=3):
    """Median |v_ball(t + delta) - v_carrier(t)| over carried balls, for each delta (m/s).

    A carried ball moves with its carrier, so if the ball track lags the players by d frames
    the two velocities agree best at delta = d. Velocities, not positions: a dribbled ball runs
    half a metre ahead of the player, and a position criterion mistakes that lead for a lag.
    Velocities are central differences over +/- half frames; `slots` is the carrier's slot at
    each frame. Returns [(delta, median speed mismatch, frames used)].
    """
    keep = (frames - max_lag - half >= 0) & (frames + max_lag + half < len(bx))
    frames, slots = frames[keep][::step], slots[keep][::step]
    pvx = (px[frames + half, slots] - px[frames - half, slots]) / (2.0 * half)
    pvy = (py[frames + half, slots] - py[frames - half, slots]) / (2.0 * half)
    profile = []
    for delta in range(-max_lag, max_lag + 1):
        t = frames + delta
        bvx = (bx[t + half] - bx[t - half]) / (2.0 * half)
        bvy = (by[t + half] - by[t - half]) / (2.0 * half)
        mismatch = np.hypot(bvx - pvx, bvy - pvy) * 25.0
        mismatch = mismatch[np.isfinite(mismatch)]
        profile.append((delta, float(np.median(mismatch)) if len(mismatch) >= 200 else None,
                        int(len(mismatch))))
    return profile


def in_area(px, py, pitch, margin):
    length, width = pitch
    return (np.isfinite(px) & (px > -margin) & (px < length + margin)
            & (py > -margin) & (py < width + margin))


def nearest_by_team(bx, by, px, py, slot_team, valid):
    """For each team: distance from the ball to its nearest tracked player, and that slot.

    Frames without a ball position or without players of that team get inf and -1.
    """
    out = {}
    with np.errstate(invalid="ignore"):
        distance = np.hypot(px - bx[:, None], py - by[:, None])
    distance = np.where(valid & np.isfinite(distance), distance, np.inf)
    for team in (HOME, AWAY):
        slots = np.flatnonzero(slot_team == team)
        if len(slots) == 0:
            out[team] = (np.full(len(bx), np.inf), np.full(len(bx), -1))
            continue
        block = distance[:, slots]
        best = np.argmin(block, axis=1)
        dmin = block[np.arange(len(bx)), best]
        slot = np.where(np.isfinite(dmin), slots[best], -1)
        out[team] = (dmin, slot)
    return out


def attack_sign(px, slot_team, valid, length):
    """+1 if the home side attacks towards x = length in this half, -1 otherwise, and a margin.

    Decided by where each team's deepest player usually is: a goalkeeper stands near his own goal
    line almost all the time, so the side with players close to the x = 0 line most of the half is
    the side defending it. The margin (metres) is how clear the decision was.
    """
    stats = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for team in (HOME, AWAY):
            block = np.where(valid[:, slot_team == team], px[:, slot_team == team], np.nan)
            xmin = np.nanmin(block, axis=1)
            xmax = np.nanmax(block, axis=1)
            stats[team] = (np.nanmedian(xmin), np.nanmedian(length - xmax))
    left_h, right_h = stats[HOME]
    left_a, right_a = stats[AWAY]
    home_left = (left_h + right_a) - (left_a + right_h)
    if not np.isfinite(home_left):
        return 1, 0.0
    return (1 if home_left < 0 else -1), float(abs(home_left))


def team_shape(px, py, vx, vy, ps, slot_team, valid):
    """Per-frame collective features of each team: count, centroid, spread, velocity, speed."""
    shape = {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        for team in (HOME, AWAY):
            cols = slot_team == team
            mask = valid[:, cols]
            x = np.where(mask, px[:, cols], np.nan)
            y = np.where(mask, py[:, cols], np.nan)
            shape[team] = {
                "n": mask.sum(axis=1),
                "mx": np.nanmean(x, axis=1),
                "my": np.nanmean(y, axis=1),
                "sx": np.nanstd(x, axis=1),
                "sy": np.nanstd(y, axis=1),
                "vx": np.nanmean(np.where(mask, vx[:, cols], np.nan), axis=1),
                "speed": np.nanmean(np.where(mask, ps[:, cols], np.nan), axis=1),
            }
    return shape


def player_speed(px, py, ps, half, min_points, fps):
    """Velocity components from positions and a speed per slot (the ATD channel if present)."""
    vx = local_slope(px, half, min_points) * fps
    vy = local_slope(py, half, min_points) * fps
    speed = np.hypot(vx, vy)
    if ps is not None:
        speed = np.where(np.isfinite(ps), ps, speed)
    return vx.astype(np.float32), vy.astype(np.float32), speed.astype(np.float32)


def distance_outside(x, y, pitch):
    """Metres outside the pitch rectangle (0 inside), and signed distance to the nearest line
    (positive inside)."""
    length, width = pitch
    outside = np.maximum.reduce([-x, x - length, -y, y - width, np.zeros_like(x)])
    inside = np.minimum.reduce([x, length - x, y, width - y])
    return outside, inside


def outward_speed(x, y, vx, vy, pitch):
    """Ball velocity component towards the nearest line (positive = heading out)."""
    length, width = pitch
    to_line = np.vstack([x, length - x, y, width - y])
    nearest = np.argmin(to_line, axis=0)
    normal_x = np.choose(nearest, [-1.0, 1.0, 0.0, 0.0])
    normal_y = np.choose(nearest, [0.0, 0.0, -1.0, 1.0])
    return vx * normal_x + vy * normal_y
