"""Strict indexed ATD adapter. No input values or paths enter error messages."""

from array import array
import math
from pathlib import Path
import time
import xml.etree.ElementTree as ET

import numpy as np

import games
from solution.a_opus.atd import read_metadata
from solution.contract import normalized_to_metres, validate_positions
from starter.load_atd import video_frame_of


class ViewerError(ValueError):
    """A diagnostic that is safe to share without match material."""


def fingerprint(path):
    stat = path.stat()
    return stat.st_dev, stat.st_ino, stat.st_size, stat.st_mtime_ns


class IndexedTracking:
    """Validate once, keep byte offsets, and decode bounded windows on demand."""

    def __init__(self, meta_path, raw_path, progress=None, n_frames=None):
        started = time.perf_counter()
        self.n_frames = games.source_frames() if n_frames is None else n_frames
        self.fps = games.GAMES[games.GAME]["fps"]
        self.pitch = games.GAMES[games.GAME]["pitch"]
        self.blocks = games.half_video_blocks(games.GAME)
        self.synthetic = False
        self.path = Path(raw_path)
        try:
            # The existing metadata reader supplies channel layout and team convention.
            # Reject its permissive unknown-team fallback in this diagnostic viewer.
            root = ET.parse(meta_path).getroot()
            for element in root.iter():
                element.tag = element.tag.rsplit("}", 1)[-1]
            teams = list(root.iter("Team"))
            ids = [team.get("id") for team in teams]
            if len(ids) != 2 or None in ids or len(set(ids)) != 2:
                raise ViewerError("Metadata must define two distinct team IDs.")
            slots = list(root.iter("Player"))
            if not slots or any(slot.get("teamId") not in ids for slot in slots):
                raise ViewerError("Every tracking slot needs a known metadata team.")
            self.meta = read_metadata(meta_path)
            if self.meta["unknown_slots"]:
                raise ViewerError("Tracking layout refers to an unknown slot.")
            self.slot_ids = self.meta["layout"]["player_ids"]
            if len(set(self.slot_ids)) != len(self.slot_ids):
                raise ViewerError("Tracking slot IDs must be unique.")
            self.teams = ["H" if team == 0 else "A" for team in self.meta["slot_team"]]
            if set(self.teams) != {"H", "A"}:
                raise ViewerError("Metadata must include both teams.")
            self.names = self.meta["team_names"]
            self.layout = self.meta["layout"]
            if self.layout["source"] == "documented fallback":
                # DATA.md and the official baseline document x,y,speed for this export.
                self.layout["ball_roles"] = ["x", "y", "speed"]
            self.offsets = array("Q")
            self.signature = fingerprint(self.path)
            with self.path.open("rb") as handle:
                for expected in range(1, self.n_frames + 1):
                    offset = handle.tell()
                    line = handle.readline()
                    if not line:
                        raise ViewerError("ATD is shorter than the tactical video.")
                    self._parse(line, expected)
                    self.offsets.append(offset)
                    if progress and expected % 4096 == 0:
                        progress(expected / self.n_frames)
                if handle.readline():
                    raise ViewerError("ATD is longer than the tactical video.")
            if fingerprint(self.path) != self.signature:
                raise ViewerError("Tracking changed while indexing. Restart the viewer.")
        except ViewerError:
            raise
        except (OSError, ValueError, TypeError, KeyError, IndexError, ET.ParseError):
            raise ViewerError("Cannot read metadata or tracking; verify the tactical XML/TXT pair.") from None
        self.load_seconds = time.perf_counter() - started

    def _group(self, text, separator, roles):
        if text.strip().casefold() == "nan":
            return None
        values = text.split(separator)
        if len(values) != len(roles):
            raise ViewerError("ATD channel count disagrees with the metadata layout.")
        try:
            numbers = [float(value) for value in values]
        except ValueError:
            raise ViewerError("ATD contains a non-numeric coordinate or channel.") from None
        if any(math.isinf(value) for value in numbers):
            raise ViewerError("ATD contains an infinite coordinate or channel.")
        x, y = numbers[roles.index("x")], numbers[roles.index("y")]
        if math.isnan(x) and math.isnan(y):
            return None
        if math.isnan(x) or math.isnan(y):
            raise ViewerError("ATD observation has only one valid coordinate.")
        return [x, y]

    def _parse(self, line, expected):
        try:
            text = line.decode("utf-8-sig").rstrip("\r\n")
            layout = self.layout
            fields = text.split(layout["sep"])
            if len(fields) != layout["n_fields"]:
                raise ViewerError("ATD record structure disagrees with metadata.")
            if int(fields[layout["i_frame"]]) != expected:
                raise ViewerError("ATD IDs must be consecutive from one, with no duplicates or offsets.")
            groups = fields[layout["i_players"]].rstrip(layout["player_sep"]).split(layout["player_sep"])
            if len(groups) != len(self.slot_ids):
                raise ViewerError("ATD slot count disagrees with metadata.")
            players = [self._group(group, layout["channel_sep"], layout["player_roles"])
                       for group in groups]
            ball = self._group(fields[layout["i_ball"]].rstrip(layout["player_sep"]),
                               layout["ball_sep"], layout["ball_roles"])
            return players, ball
        except ViewerError:
            raise
        except (ValueError, UnicodeError, IndexError):
            raise ViewerError("ATD has an invalid record or frame ID.") from None

    def window(self, start, count):
        try:
            if fingerprint(self.path) != self.signature:
                raise ViewerError("Tracking changed after indexing. Restart the viewer.")
            rows = []
            with self.path.open("rb") as handle:
                handle.seek(self.offsets[start])
                for frame in range(start, min(start + count, self.n_frames)):
                    players, ball = self._parse(handle.readline(), frame + 1)
                    rows.append((frame, players, ball))
            if fingerprint(self.path) != self.signature:
                raise ViewerError("Tracking changed during reading. Restart the viewer.")
            # Shared conversion and mask validation, bounded to this requested window.
            xy = np.array([[point if point is not None else [np.nan, np.nan]
                            for point in players + [ball]] for _, players, ball in rows])
            xy = normalized_to_metres(xy, self.pitch)
            observed = np.isfinite(xy).all(axis=-1)
            validate_positions(xy, observed, observed, np.zeros_like(observed))
            result = []
            for index, (frame, _, _) in enumerate(rows):
                points = [point.tolist() if valid else None
                          for point, valid in zip(xy[index], observed[index])]
                result.append({"frame": video_frame_of(frame + 1),
                               "players": points[:-1], "ball": points[-1]})
            return result
        except ViewerError:
            raise
        except (OSError, ValueError, IndexError):
            raise ViewerError("Cannot read the requested tracking window.") from None
