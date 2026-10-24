"""Invented movement only. Never resolves a match asset path."""

import math
from pathlib import Path

from games import GAME, GAMES


class SyntheticTracking:
    synthetic = True
    load_seconds = 0.0

    def __init__(self):
        self.n_frames = 1500
        self.fps = GAMES[GAME]["fps"]
        self.pitch = GAMES[GAME]["pitch"]
        self.blocks = [(1, 0, 649), (2, 850, 1499)]
        self.names = ("Home", "Away")
        self.slot_ids = [str(index + 1) for index in range(22)]
        self.teams = ["H"] * 11 + ["A"] * 11

    def label(self, frame):
        if 650 <= frame < 850:
            return "X"
        if 500 <= frame < 650 or 1200 <= frame < 1325:
            return "D"
        return "H" if frame < 250 or frame >= 1000 else "A"

    def window(self, start, count):
        rows = []
        length, width = self.pitch
        for frame in range(start, min(start + count, self.n_frames)):
            if 650 <= frame < 850:
                players, ball = [None] * 22, None
            else:
                phase = frame / self.fps
                players = []
                for slot in range(22):
                    home = slot < 11
                    index = slot % 11
                    x = 8 if index == 0 else 22 + ((index - 1) // 3) * 13
                    y = width / 2 if index == 0 else 12 + ((index - 1) % 3) * 22
                    x = x + 5 * math.sin(phase * .35 + index)
                    if not home:
                        x, y = length - x, width - y
                    missing = (slot == 4 and 350 <= frame < 400) or (slot == 5 and 420 <= frame < 500)
                    players.append(None if missing else [x, y])
                ball = [length * (.5 + .30 * math.sin(phase * .42)),
                        width * (.5 + .30 * math.sin(phase * .63))]
                if 100 <= frame < 150:
                    ball = None
                elif 500 <= frame < 650:
                    ball = [length + 1.5, width * .3]
                elif 1200 <= frame < 1325:
                    ball = [length / 2, width / 2]
            rows.append({"frame": frame, "players": players, "ball": ball})
        return rows


def write_fixture(directory, n_frames, slots=22):
    """Generate an invented, full-size ATD for adapter tests and local benchmarks."""
    directory = Path(directory)
    directory.mkdir(parents=True, exist_ok=True)
    meta = directory / "synthetic.xml"
    raw = directory / "synthetic.txt"
    meta.write_text('<root><Team id="h"><Name>Home</Name></Team>'
                    '<Team id="a"><Name>Away</Name></Team>' +
                    ''.join('<Player id="{}" teamId="{}"/>'.format(i + 1, "h" if i < slots // 2 else "a")
                            for i in range(slots)) + '</root>', encoding="utf-8")
    groups = ';'.join("0.5,0.5,0" for _ in range(slots))
    with raw.open("w", encoding="utf-8", newline="\n") as handle:
        for frame in range(n_frames):
            handle.write('{}:{}:{}\n'.format(frame + 1, groups,
                                             "NaN,NaN,NaN" if frame % 7 == 0 else "0.25,0.75,0"))
    return meta, raw
