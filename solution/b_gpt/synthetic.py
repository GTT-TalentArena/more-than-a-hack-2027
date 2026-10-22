"""Independent fixtures, with no access to match files or public/private GT."""

import numpy as np
from .io import Tracking


def from_labels(labels, fps=25, seed=71, missing=True, slots=22):
    rng = np.random.default_rng(seed)
    n = len(labels)
    t = np.arange(n) / fps
    # Smooth, moving ball with known metres; teams can exchange control without teleports.
    ball = np.column_stack((52 + 15 * np.sin(t / 4), 34 + 12 * np.sin(t / 6),
                            np.full(n, 3.0))).astype(np.float32)
    teams = np.arange(slots) % 2
    players = np.zeros((n, slots, 3), dtype=np.float32)
    for slot in range(slots):
        players[:, slot, 0] = 15 + (slot % 6) * 14
        players[:, slot, 1] = 8 + (slot // 6) * 15
        players[:, slot, 2] = 2.7
    # Keep background slots away from the ball: this fixture isolates controlled touches.
    players[:, 2:, 0] = 10 + np.arange(slots - 2) % 3
    players[:, 2:, 1] = 10 + np.arange(slots - 2) // 3
    players[:, 0, :2] = ball[:, :2] + [8, 0]
    players[:, 1, :2] = ball[:, :2] + [-8, 0]
    players[labels == "H", 0, :2] = ball[labels == "H", :2] + [.4, 0]
    players[labels == "A", 1, :2] = ball[labels == "A", :2] + [-.4, 0]
    dead = labels == "D"
    ball[dead, :2] = [50, -1.2]
    ball[dead, 2] = 0
    players[dead, :, 2] = .4
    if missing:
        gaps = rng.random(n) < .15
        # Include long invisible intervals during live play, without false dead cues.
        for a in range(400, n - 150, 1500):
            if labels[a] in "HA" and np.all(labels[a:a + 100] == labels[a]):
                gaps[a:a + 100] = True
        ball[gaps] = np.nan
    return Tracking(ball, players, teams.astype(np.int8))


def make_match(n, blocks, fps=25):
    labels = np.full(n, "X", dtype="<U1")
    events = []
    # Arbitrary seed/distributions, deliberately unrelated to the 17 public possessions.
    rng = np.random.default_rng(20261021)
    for half, start, last in blocks:
        cursor, team = start, "H" if half % 2 else "A"
        lead = 0 if half == 1 else 37 * fps
        labels[cursor:cursor + lead] = "D"
        events.append(dict(start=cursor + lead - fps, end=cursor + lead + fps,
                           code="set pieces", tags={"type": "kick off (start)",
                                                     "team": "Barcelona" if team == "H" else "Atletic Club"}))
        cursor += lead
        while cursor <= last:
            duration = int(rng.uniform(.6, 1.5) * fps) if rng.random() < .2 else int(rng.uniform(4, 28) * fps)
            end = min(last + 1, cursor + duration)
            labels[cursor:end] = team
            cursor = end
            if cursor <= last and rng.random() < .3:
                end = min(last + 1, cursor + int(rng.uniform(3, 18) * fps))
                labels[cursor:end] = "D"
                if end <= last:
                    events.append(dict(start=end - fps, end=end + fps, code="set pieces",
                                       tags={"type": "throw-in", "team": "n/a"}))
                cursor = end
            team = "A" if team == "H" else "H"
    return from_labels(labels, fps, slots=46), events, ("Barcelona", "Athletic Club"), labels
