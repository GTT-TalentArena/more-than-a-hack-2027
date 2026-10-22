"""A synthetic match bundle in the exact formats of the real one, so the pipeline can be tested
without looking at any match data.

    python -m solution.a_opus.synth --out-dir <dir> [--seed 0] [--minutes 0]

writes <dir>/tactical/BAR-ATH_tactical_atd.xml, _atd.txt and _smart_tagging.xml (the names
games.asset_paths() expects), and <dir>/synthetic_gt.csv with the labels the simulation knows to
be true, 199,319 rows with X outside the two graded halves, like the real ground truth.

It is a test fixture, not a model of football: 22 agents in a 4-4-2 that shifts with the ball,
dribbles, passes, interceptions, tackles, loose balls, shots, balls out of play, fouls and every
restart, kick-offs included. On top, the noise the documentation describes for the real ATD: a
ball missing ~40% of the time in bursts (more in the air, in crowds and while dead), position
noise, a few wild detections, aerial balls projected away from the true point, fragmented tracks
that jump between the 46 slots, and Smart Tagging that tags only some restarts and phases with
jittered bounds. Parameter values here are invented and deliberately NOT those of the solution.
"""

import argparse
import os
import sys

import numpy as np

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(os.path.dirname(HERE))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)
import games  # noqa: E402

FPS = 25
L, W = 105.3, 68.0
HOME_NAME, AWAY_NAME = "FC Barcelona", "Athletic Club"
TAG_NAMES = ("Barcelona", "Atletic Club")
N_SLOTS_PER_TEAM = 23
GOAL_HALF_WIDTH = 3.66

# 4-4-2 in a team's own frame: x from its own goal line, y across.
FORMATION = np.array([
    [5, 34], [22, 10], [20, 26], [20, 42], [22, 58],
    [42, 12], [40, 27], [40, 41], [42, 56], [60, 28], [60, 40],
], dtype=np.float64)


class Half:
    """Simulates one half: true positions, ball, labels, restarts and an aerial flag."""

    def __init__(self, rng, n, pre_kickoff, home_sign, first_kick_team):
        self.rng = rng
        self.n = n
        self.home_sign = home_sign  # +1: home attacks towards x = L
        self.pos = np.zeros((n, 22, 2))
        self.vel = np.zeros((n, 22, 2))
        self.ball = np.zeros((n, 2))
        self.height = np.zeros(n)
        self.label = np.zeros(n, dtype=np.int8)  # 0 H, 1 A, 2 D
        self.aerial = np.zeros(n, dtype=bool)
        self.restarts = []  # (kick_frame, type, team)
        self.goals = []
        self.team = np.array([0] * 11 + [1] * 11)

        p = self._formation(np.array([L / 2, W / 2]), owner=first_kick_team, kickoff=True)
        self.p = p + rng.normal(0, 0.5, p.shape)
        self.v = np.zeros((22, 2))
        self.b = np.array([L / 2, W / 2])
        self.bv = np.zeros(2)
        self.h = 0.0
        self.owner = first_kick_team
        self.carrier = None
        self.mode = "dead"
        self.flight = None
        self.dribble_left = 0
        self.dead = {"type": "kick off (start)", "team": first_kick_team,
                     "spot": np.array([L / 2, W / 2]), "kick": pre_kickoff,
                     "place": max(pre_kickoff - 75, 0)}

    # -- geometry helpers -------------------------------------------------------------------------
    def sign(self, team):
        return self.home_sign if team == 0 else -self.home_sign

    def to_abs(self, team, own_xy):
        out = own_xy.copy()
        if self.sign(team) < 0:
            out[..., 0] = L - out[..., 0]
        return out

    def own_x(self, team, x):
        return x if self.sign(team) > 0 else L - x

    def _formation(self, ball, owner, kickoff=False):
        """Target positions for everyone given the ball and who owns it."""
        targets = np.zeros((22, 2))
        for team in (0, 1):
            own = FORMATION.copy()
            bx_own = self.own_x(team, ball[0])
            if kickoff:
                own[:, 0] = np.minimum(own[:, 0] * 0.8, L / 2 - 1.5)
            else:
                attacking = team == owner
                push = 0.55 * (bx_own - 45) + (8 if attacking else -4)
                own[1:, 0] = own[1:, 0] + push
                spread = 1.15 if attacking else 0.75
                centre_y = W / 2 + (0.0 if attacking else 0.35 * (ball[1] - W / 2))
                own[1:, 1] = centre_y + (own[1:, 1] - W / 2) * spread
                own[0, 0] = 5 + max(0, bx_own - 70) * 0.1
            own[:, 0] = np.clip(own[:, 0], 1, L - 1)
            own[:, 1] = np.clip(own[:, 1], 1, W - 1)
            targets[team * 11:(team + 1) * 11] = self.to_abs(team, own)
        return targets

    def _move(self, targets, max_speed):
        """Player dynamics: steer towards the target, bounded speed and acceleration (6 m/s2)."""
        desired = targets - self.p
        dist = np.linalg.norm(desired, axis=1, keepdims=True)
        desired = desired / np.maximum(dist, 1e-6) * np.minimum(dist * 1.2, max_speed)
        self.v = self.v + np.clip(desired - self.v, -6.0 / FPS, 6.0 / FPS)
        speed = np.linalg.norm(self.v, axis=1, keepdims=True)
        self.v = self.v / np.maximum(speed, 1e-6) * np.minimum(speed, max_speed)
        self.v += self.rng.normal(0, 0.15, self.v.shape)
        self.p = self.p + self.v / FPS
        self.p[:, 0] = np.clip(self.p[:, 0], -1.5, L + 1.5)
        self.p[:, 1] = np.clip(self.p[:, 1], -1.5, W + 1.5)

    def _nearest(self, point, team=None, exclude=None):
        d = np.linalg.norm(self.p - point, axis=1)
        if team is not None:
            d = np.where(self.team == team, d, np.inf)
        if exclude is not None:
            d[exclude] = np.inf
        j = int(np.argmin(d))
        return j, float(d[j])

    # -- events ---------------------------------------------------------------------------------
    def _start_dead(self, t, kind, team, spot, duration_s):
        self.mode = "dead"
        self.carrier = None
        self.flight = None
        kick = t + int(duration_s * FPS)
        # Where the ball comes to rest before it is fetched: a few metres further out if it
        # left the pitch, where it was if the whistle went.
        rest = self.b.copy()
        outward = np.array([np.sign(rest[0] - L / 2) if not 0 <= rest[0] <= L else 0.0,
                            np.sign(rest[1] - W / 2) if not 0 <= rest[1] <= W else 0.0])
        rest += outward * self.rng.uniform(1, 4)
        self.dead = {"type": kind, "team": team, "spot": np.array(spot, dtype=np.float64),
                     "kick": kick, "place": kick - int(self.rng.uniform(1.5, 4.0) * FPS),
                     "rest": rest}

    def _out_of_play(self, t, point):
        """The ball crossed a line at `point`: choose the restart."""
        last = self.owner
        x, y = point
        rng = self.rng
        if y < 0 or y > W:
            spot = [np.clip(x, 0.5, L - 0.5), 0.0 if y < 0 else W]
            self._start_dead(t, "throw-in", 1 - last, spot, rng.uniform(5, 12))
            return
        goal_left = x < 0
        defending = 0 if (goal_left == (self.home_sign > 0)) else 1
        if abs(y - W / 2) < GOAL_HALF_WIDTH and rng.rand() < 0.04:
            self.goals.append(t)
            self._start_dead(t, "kick off (after goal)", defending, [L / 2, W / 2],
                             rng.uniform(45, 70))
            return
        if last == defending:
            spot = [0.0 if goal_left else L, 0.0 if y < W / 2 else W]
            self._start_dead(t, "corner kick", 1 - defending, spot, rng.uniform(18, 35))
        else:
            spot = [5.0 if goal_left else L - 5.0, W / 2 + rng.uniform(-6, 6)]
            self._start_dead(t, "goal kick", defending, spot, rng.uniform(9, 20))

    def _pass(self, t, shot=False):
        rng = self.rng
        start = self.b.copy()
        team = self.owner
        if shot:
            goal_x = L if self.sign(team) > 0 else 0.0
            target = np.array([goal_x + self.sign(team) * 2.0, W / 2 + rng.normal(0, 6)])
            speed, receiver, aerial = rng.uniform(18, 28), None, rng.rand() < 0.5
        else:
            mates = np.flatnonzero((self.team == team) & (np.arange(22) != self.carrier))
            d = np.linalg.norm(self.p[mates] - start, axis=1)
            forward = (self.p[mates, 0] - start[0]) * self.sign(team)
            weight = np.exp(-d / 22.0) * (1.0 + 0.6 * (forward > 0))
            weight[d < 4] = 0.05
            receiver = int(rng.choice(mates, p=weight / weight.sum()))
            dist = np.linalg.norm(self.p[receiver] - start)
            aerial = dist > 28 and rng.rand() < 0.65
            speed = rng.uniform(16, 24) if aerial else rng.uniform(9, 17)
            lead = self.v[receiver] * (dist / speed)
            target = self.p[receiver] + lead + rng.normal(0, 1.5 if not aerial else 3.0, 2)
            if rng.rand() < 0.07:  # a bad pass towards a line
                target = target + rng.normal(0, 18, 2)
        dist = max(np.linalg.norm(target - start), 0.5)
        frames = max(int(dist / speed * FPS), 2)
        self.flight = {"start": start, "end": target, "frames": frames, "elapsed": 0,
                       "receiver": receiver, "aerial": aerial, "apex": rng.uniform(3, 12),
                       "shot": shot, "passer": self.carrier}
        self.carrier = None
        self.mode = "flight"

    def _gain(self, player):
        self.carrier = player
        self.owner = int(self.team[player])
        self.mode = "carry"
        self.dribble_left = int(self.rng.exponential(1.3) * FPS) + 5
        self.flight = None
        self.h = 0.0

    # -- the loop ---------------------------------------------------------------------------------
    def run(self):
        rng = self.rng
        for t in range(self.n):
            if self.mode == "dead":
                self._dead_step(t)
            else:
                self._live_step(t)
            self.pos[t], self.vel[t] = self.p, self.v
            self.ball[t], self.height[t] = self.b, self.h
            self.label[t] = 2 if self.mode == "dead" else self.owner
            self.aerial[t] = self.mode == "flight" and self.flight is not None \
                and self.flight["aerial"]
        return self

    def _dead_step(self, t):
        dead = self.dead
        spot = dead["spot"]
        taker_team = dead["team"]
        if t >= dead["kick"]:
            taker, _ = self._nearest(spot, team=taker_team)
            self.p[taker] = spot - np.array([self.sign(taker_team) * 0.6, 0.0])
            self.b = spot.copy()
            self._gain(taker)
            self.restarts.append((t, dead["type"], taker_team))
            self._pass(t)
            self._live_step(t, advance_only=True)
            return
        kickoff = dead["type"].startswith("kick off")
        targets = self._formation(spot, owner=taker_team, kickoff=kickoff)
        # Nobody stands still during a stoppage: a slow random walk around the target.
        self.wander = getattr(self, "wander", np.zeros((22, 2)))
        self.wander = 0.998 * self.wander + self.rng.normal(0, 0.06, (22, 2))
        targets = targets + self.wander
        if t >= dead["place"]:
            taker, _ = self._nearest(spot, team=taker_team)
            targets[taker] = spot - np.array([self.sign(taker_team) * 1.0, 0.0])
            if dead["type"] == "throw-in":
                self.b = self.p[taker] + np.array([0.0, 0.3])
                self.h = 2.2
            else:
                self.b = spot.copy()
                self.h = 0.0
        else:
            rest = dead.get("rest", spot)
            self.b = self.b + (rest - self.b) * 0.02
        self._move(targets, 2.2 if not kickoff else 1.5)

    def _live_step(self, t, advance_only=False):
        rng = self.rng
        targets = self._formation(self.b, self.owner)
        if self.mode == "carry":
            c = self.carrier
            goal_x = L if self.sign(self.owner) > 0 else 0.0
            direction = np.array([goal_x, W / 2]) - self.p[c]
            targets[c] = self.p[c] + direction / max(np.linalg.norm(direction), 1e-6) * 6
            d_opp = np.linalg.norm(self.p - self.b, axis=1)
            d_opp[self.team == self.owner] = np.inf
            presser = int(np.argmin(d_opp))
            targets[presser] = self.b
        elif self.mode in ("flight", "loose"):
            for team in (0, 1):
                j, _ = self._nearest(self.b, team=team)
                targets[j] = self.b
            if self.mode == "flight" and self.flight["receiver"] is not None:
                targets[self.flight["receiver"]] = self.flight["end"]
        if not advance_only:
            self._move(targets, 7.5)

        if self.mode == "carry":
            c = self.carrier
            heading = self.v[c] / max(np.linalg.norm(self.v[c]), 1e-6)
            self.b = self.p[c] + heading * 0.5 + rng.normal(0, 0.1, 2)
            self.h = 0.0
            if advance_only:
                return
            if not (0 <= self.b[0] <= L and 0 <= self.b[1] <= W):
                self._out_of_play(t, self.b.copy())
                return
            j, d = self._nearest(self.b, team=1 - self.owner)
            if d < 1.3:
                roll = rng.rand()
                if roll < 0.022:
                    self._gain(j)
                    return
                if roll < 0.030:
                    self.mode = "loose"
                    self.bv = rng.normal(0, 5, 2)
                    return
                if roll < 0.035:
                    self._start_dead(t, "free kick", self.owner, self.b, rng.uniform(12, 30))
                    return
            self.dribble_left -= 1
            if self.dribble_left <= 0:
                own_x = self.own_x(self.owner, self.b[0])
                self._pass(t, shot=own_x > 82 and rng.rand() < 0.35)
            return

        if self.mode == "flight":
            f = self.flight
            f["elapsed"] += 1
            tau = min(f["elapsed"] / float(f["frames"]), 1.0)
            point = f["start"] + (f["end"] - f["start"]) * tau
            self.h = 4 * f["apex"] * tau * (1 - tau) if f["aerial"] else 0.0
            self.b = point
            if not (0 <= point[0] <= L and 0 <= point[1] <= W):
                self._out_of_play(t, point)
                return
            if self.h < 2.0:
                for j in np.flatnonzero(self.team != self.owner):
                    if np.linalg.norm(self.p[j] - point) < 1.0 and rng.rand() < 0.3:
                        self._gain(j)
                        return
            if tau >= 1.0:
                if f["shot"]:
                    keeper = 11 if self.owner == 0 else 0
                    if rng.rand() < 0.6:
                        self._gain(keeper)
                    else:
                        self._out_of_play(t, point + np.array([self.sign(self.owner) * 3, 0]))
                    return
                r = f["receiver"]
                if r is not None and np.linalg.norm(self.p[r] - point) < 2.0:
                    self._gain(r)
                else:
                    self.mode = "loose"
                    self.bv = (f["end"] - f["start"]) / f["frames"] * FPS * 0.4
            return

        if self.mode == "loose":
            self.bv *= 0.94
            self.b = self.b + self.bv / FPS
            self.h = 0.0
            if not (0 <= self.b[0] <= L and 0 <= self.b[1] <= W):
                self._out_of_play(t, self.b.copy())
                return
            j, d = self._nearest(self.b)
            if d < 0.9:
                self._gain(j)


def simulate(seed=0, minutes=0):
    """Full-length arrays for the tactical timeline plus the event lists for the tagging."""
    rng = np.random.RandomState(seed)
    n_frames = games.source_frames("tactical")
    blocks = games.half_video_blocks(games.GAME)
    truth = {
        "pos": np.full((n_frames, 22, 2), np.nan), "vel": np.zeros((n_frames, 22, 2)),
        "ball": np.full((n_frames, 2), np.nan), "height": np.zeros(n_frames),
        "aerial": np.zeros(n_frames, dtype=bool),
        "label": np.full(n_frames, 3, dtype=np.int8), "restarts": [], "goals": [],
        "blocks": [],
    }
    for index, (half, first, last) in enumerate(blocks):
        n = last - first + 1
        if minutes:
            n = min(n, minutes * 60 * FPS)
        pre = 0 if half == 1 else 2934
        sim = Half(rng, n, pre, home_sign=1 if half == 1 else -1,
                   first_kick_team=0 if half == 1 else 1).run()
        span = slice(first, first + n)
        truth["pos"][span], truth["vel"][span] = sim.pos, sim.vel
        truth["ball"][span], truth["height"][span] = sim.ball, sim.height
        truth["aerial"][span] = sim.aerial
        truth["label"][span] = sim.label
        truth["restarts"] += [(first + t, kind, team) for t, kind, team in sim.restarts]
        truth["goals"] += [first + t for t in sim.goals]
        truth["blocks"].append((half, first, first + n - 1))
    return truth, rng


def realistic_ball(ball, max_gap=50, half=3):
    """Post-process a noisy ball track the way the real ATD looks (v1.3 log): short gaps
    already bridged by straight lines and the track smoothed, so there are no gaps under 2 s
    and almost no position noise. Long gaps stay missing."""
    from .features import interpolate, nan_moving_mean
    seen = np.isfinite(ball[:, 0])
    x, y, fill, _, _, _ = interpolate(ball[:, 0], ball[:, 1], seen, max_gap)
    keep = seen | fill
    out = np.full_like(ball, np.nan)
    out[:, 0] = np.where(keep, nan_moving_mean(np.where(keep, x, np.nan), half), np.nan)
    out[:, 1] = np.where(keep, nan_moving_mean(np.where(keep, y, np.nan), half), np.nan)
    return out


def observe(truth, rng, ball_style="noisy", smooth_half=3):
    """The automatic tracking: what the ATD would contain for this truth."""
    n_frames = len(truth["label"])
    graded = truth["label"] != 3
    # Ball visibility: a two-state chain, then extra losses in the air, in crowds, when dead.
    visible = np.zeros(n_frames, dtype=bool)
    state = True
    flips = rng.rand(n_frames)
    for t in range(n_frames):
        if state and flips[t] < 1 / 38.0:
            state = False
        elif not state and flips[t] < 1 / 24.0:
            state = True
        visible[t] = state
    crowd = np.zeros(n_frames, dtype=bool)
    with np.errstate(invalid="ignore"):
        d = np.linalg.norm(truth["pos"] - truth["ball"][:, None, :], axis=2)
        crowd = np.nansum(d < 3.0, axis=1) >= 4
    lose = rng.rand(n_frames)
    visible &= ~(truth["aerial"] & (lose < 0.7))
    visible &= ~(crowd & (lose < 0.35))
    visible &= ~((truth["label"] == 2) & (lose < 0.45))
    visible &= graded

    ball = truth["ball"] + rng.normal(0, 0.25, truth["ball"].shape)
    # A ball in the air is projected onto the pitch away from the (main-stand) camera.
    ball[:, 1] += truth["height"] * 0.9
    wild = visible & (rng.rand(n_frames) < 0.003)
    ball[wild] += rng.uniform(-18, 18, (int(wild.sum()), 2))
    ball[~visible] = np.nan
    if ball_style == "real":
        ball = realistic_ball(ball, half=smooth_half)
        visible = np.isfinite(ball[:, 0])
    z = np.where(visible, truth["height"] + rng.normal(0, 0.3, n_frames), np.nan)

    # Players: fragmented tracks over 23 slots per team, short occlusions, noise.
    slots = np.full((n_frames, 2 * N_SLOTS_PER_TEAM, 3), np.nan)
    frames = np.flatnonzero(graded)
    noise = rng.normal(0, 0.15, (len(frames), 22, 2))
    speed_noise = rng.normal(0, 0.2, (len(frames), 22))
    draws = rng.rand(len(frames), 22)
    lose_rate, occlude_rate = 1.0 / (40 * FPS), 0.002
    for team in (0, 1):
        free = list(range(11, N_SLOTS_PER_TEAM))
        current = list(range(11))
        lost = np.zeros(11, dtype=int)       # frames until re-acquired, in another slot
        occluded = np.zeros(11, dtype=int)   # frames of a short occlusion, same slot
        for row, t in enumerate(frames):
            for k in range(11):
                player = team * 11 + k
                if lost[k] > 0:
                    lost[k] -= 1
                    if lost[k] == 0:
                        free.append(current[k])
                        current[k] = free.pop(rng.randint(len(free)))
                    continue
                if occluded[k] > 0:
                    occluded[k] -= 1
                    continue
                draw = draws[row, player]
                if draw < lose_rate:
                    lost[k] = rng.randint(5, 50)
                    continue
                if draw < lose_rate + occlude_rate:
                    occluded[k] = rng.randint(5, 20)
                    continue
                p = truth["pos"][t, player] + noise[row, player]
                s = np.linalg.norm(truth["vel"][t, player]) + speed_noise[row, player]
                slots[t, team * N_SLOTS_PER_TEAM + current[k]] = (p[0], p[1], max(s, 0.0))
    return ball, z, slots


def tagging(truth, rng):
    """Smart-Tagging-like instances: some restarts, some phases, jittered."""
    instances = []

    def name_half(frame):
        for half, first, last in truth["blocks"]:
            if first - 3000 <= frame <= last + 3000:
                return "1st Half" if half == 1 else "2nd Half"
        return "1st Half"

    for frame, kind, team in truth["restarts"]:
        if not kind.startswith("kick off") and rng.rand() > 0.6:
            continue
        start = frame - int((3.5 + rng.normal(0, 0.5)) * FPS)
        end = frame + int((1.5 + abs(rng.normal(0, 0.5))) * FPS)
        side = "N/A" if kind == "throw-in" else TAG_NAMES[team]
        instances.append(("SET PIECES", start, end, {
            "Team": side, "Half": name_half(frame), "Type": kind.title()}))
    label = truth["label"]
    for half, first, last in truth["blocks"]:
        window = label[first:last + 1]
        breaks = np.flatnonzero(window[1:] != window[:-1]) + 1
        bounds = np.concatenate(([0], breaks, [len(window)]))
        for a, b in zip(bounds[:-1], bounds[1:]):
            team = window[a]
            if team > 1 or b - a < 4 * FPS or rng.rand() > 0.7:
                continue
            start = first + a + int(rng.uniform(0, 2) * FPS)
            end = first + b + int(rng.uniform(-2, 2) * FPS)
            if end - start < FPS:
                continue
            code = ["BUILD UP", "PROGRESSION", "CREATING CHANCES"][rng.randint(3)]
            instances.append((code, start, end, {"Team": TAG_NAMES[team],
                                                 "Half": name_half(start)}))
            if rng.rand() < 0.5:
                instances.append(("DEFENDING IN MIDDLE THIRD", start, end,
                                  {"Team": TAG_NAMES[1 - team], "Half": name_half(start)}))
    instances.sort(key=lambda item: item[1])
    return instances


def write_bundle(out_dir, truth, ball, z, slots, instances, with_spec=True):
    tactical = os.path.join(out_dir, "tactical")
    os.makedirs(tactical, exist_ok=True)
    paths = games.asset_paths(data_dir=out_dir)
    n_frames = len(truth["label"])
    n_slots = slots.shape[1]
    # Interleave the slot order of the two teams so the reader cannot assume one block per team.
    order = []
    for k in range(N_SLOTS_PER_TEAM):
        order += [k, N_SLOTS_PER_TEAM + k]
    team_of = ["T1" if s < N_SLOTS_PER_TEAM else "T2" for s in order]

    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<main>", "  <Metadata>",
             "    <GlobalConfig><FrameRate>25</FrameRate><ProviderName>Synthetic</ProviderName>"
             "</GlobalConfig>",
             '    <Sessions><Session id="Session_1"><MatchParameters>'
             "<FieldSize><Width>105</Width><Height>68</Height></FieldSize>"
             '<Score idLocalTeam="T1" idVisitingTeam="T2"><LocalTeamName>{}</LocalTeamName>'
             "<VisitingTeamName>{}</VisitingTeamName></Score>"
             "</MatchParameters></Session></Sessions>".format(HOME_NAME, AWAY_NAME),
             "    <Teams>",
             '      <Team id="T1"><Name>{}</Name></Team>'.format(HOME_NAME),
             '      <Team id="T2"><Name>{}</Name></Team>'.format(AWAY_NAME),
             "    </Teams>", "    <Players>"]
    for i, team_id in enumerate(team_of):
        lines.append('      <Player id="P{0}" teamId="{1}"><Name>Track {2}</Name>'
                     "<ShirtNumber>{2}</ShirtNumber></Player>".format(i, team_id, i + 1))
    lines += ["    </Players>",
              '    <Devices><Device id="device1"><Sensors>'
              '<Sensor id="position"><Channels>'
              '<Channel id="x"><Name>position_x</Name><Unit>normalized</Unit></Channel>'
              '<Channel id="y"><Name>position_y</Name><Unit>normalized</Unit></Channel>'
              "</Channels></Sensor>"
              '<Sensor id="speed"><Channels><Channel id="speed"><Name>speed</Name>'
              "<Unit>m/s</Unit></Channel></Channels></Sensor>"
              "</Sensors></Device></Devices>",
              "    <PlayerChannels>"]
    for i in range(n_slots):
        for ch in ("x", "y", "speed"):
            lines.append('      <PlayerChannel id="player{0}_{1}" playerId="P{0}" channelId="{1}"/>'
                         .format(i, ch))
    lines += ["    </PlayerChannels>", "  </Metadata>"]
    if with_spec:
        lines += ["  <DataFormatSpecifications>",
                  '    <DataFormatSpecification separator=":" startFrame="1" endFrame="{}">'
                  .format(n_frames),
                  '      <StringRegister name="frameCount"/>',
                  '      <SplitRegister separator=";">']
        for i in range(n_slots):
            lines.append('        <SplitRegister separator=",">'
                         '<PlayerChannelRef playerChannelId="player{0}_x"/>'
                         '<PlayerChannelRef playerChannelId="player{0}_y"/>'
                         '<PlayerChannelRef playerChannelId="player{0}_speed"/>'
                         "</SplitRegister>".format(i))
        lines += ["      </SplitRegister>",
                  '      <SplitRegister separator=",">'
                  '<BallChannelRef channelId="x"/><BallChannelRef channelId="y"/>'
                  '<BallChannelRef channelId="z"/></SplitRegister>',
                  "    </DataFormatSpecification>", "  </DataFormatSpecifications>"]
    lines.append("</main>")
    with open(paths["atd_meta"], "w", encoding="utf-8") as handle:
        handle.write("\n".join(lines) + "\n")

    missing = "NaN,NaN,NaN"
    with open(paths["atd_raw"], "w", newline="\n") as handle:
        for t in range(n_frames):
            row = slots[t, order]
            groups = [missing if not np.isfinite(g[0]) else
                      "{:.5f},{:.5f},{:.2f}".format(g[0] / L, g[1] / W, g[2]) for g in row]
            if np.isfinite(ball[t, 0]):
                b = "{:.5f},{:.5f},{:.2f}".format(ball[t, 0] / L, ball[t, 1] / W, z[t])
            else:
                b = missing
            handle.write("{}:{}:{}\n".format(t + 1, ";".join(groups), b))

    out = ['<?xml version="1.0" encoding="utf-8"?>', "<file>", "  <ALL_INSTANCES>"]
    for index, (code, start, end, tags) in enumerate(instances):
        out.append("    <instance><ID>{}</ID><start>{:.2f}</start><end>{:.2f}</end>"
                   "<code>{}</code>".format(index + 1, start / FPS, end / FPS, code))
        for group, text in tags.items():
            out.append("      <label><group>{}</group><text>{}</text></label>".format(
                group, text))
        out.append("    </instance>")
    out += ["  </ALL_INSTANCES>", "</file>"]
    with open(paths["smart_tagging"], "w", encoding="utf-8") as handle:
        handle.write("\n".join(out) + "\n")

    gt_path = os.path.join(out_dir, "synthetic_gt.csv")
    letters = np.array(["H", "A", "D", "X"])[truth["label"]]
    with open(gt_path, "w", newline="\n") as handle:
        handle.write("frame,label\n")
        handle.write("".join("{},{}\n".format(i, c) for i, c in enumerate(letters)))
    return gt_path


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--out-dir", required=True)
    parser.add_argument("--seed", type=int, default=0)
    parser.add_argument("--minutes", type=int, default=0,
                        help="simulate only the first N minutes of each half (0 = all)")
    parser.add_argument("--no-spec", action="store_true",
                        help="omit the DataFormatSpecification, to test the fallback layout")
    parser.add_argument("--ball-style", choices=("noisy", "real"), default="noisy",
                        help="'real': bridge gaps under 2 s and smooth the ball, like the real ATD")
    parser.add_argument("--smooth-half", type=int, default=3,
                        help="with --ball-style real: half-width of the smoothing, in frames")
    args = parser.parse_args(argv)
    truth, rng = simulate(args.seed, args.minutes)
    ball, z, slots = observe(truth, rng, args.ball_style, args.smooth_half)
    instances = tagging(truth, rng)
    gt = write_bundle(args.out_dir, truth, ball, z, slots, instances, not args.no_spec)
    labels = truth["label"]
    print("synthetic bundle in {}: {} restarts, {} goals, {} tag instances; gt {}".format(
        args.out_dir, len(truth["restarts"]), len(truth["goals"]), len(instances), gt))
    print("  graded {} frames: H {:.1%} A {:.1%} D {:.1%}; ball visible {:.1%} of graded".format(
        int(np.sum(labels != 3)), np.mean(labels[labels != 3] == 0),
        np.mean(labels[labels != 3] == 1), np.mean(labels[labels != 3] == 2),
        np.mean(np.isfinite(ball[labels != 3, 0]))))
    return 0


if __name__ == "__main__":
    sys.exit(main())
