"""Strict input adapters. Exceptions never include input content."""

from dataclasses import dataclass
from pathlib import Path
import os
import tempfile
import xml.etree.ElementTree as ET

import numpy as np


class InputError(Exception):
    """Safe, fixed-text diagnostics, suitable for sharing without data."""


@dataclass
class Tracking:
    ball: np.ndarray              # n x 3: metres, metres, m/s
    players: np.ndarray           # n x slots x 3, same units
    teams: np.ndarray             # slots: 0 = H, 1 = A


def _xml(path):
    try:
        root = ET.parse(path).getroot()
    except (OSError, ET.ParseError):
        raise InputError("Cannot read XML input or invalid XML syntax.") from None
    for element in root.iter():
        element.tag = element.tag.rsplit("}", 1)[-1]
    return root


def metadata(path):
    root = _xml(path)
    teams = list(root.iter("Team"))
    if len(teams) != 2 or any(t.get("id") is None for t in teams):
        raise InputError("ATD metadata must define exactly two teams with IDs.")
    ids = [t.get("id") for t in teams]
    if len(set(ids)) != 2:
        raise InputError("ATD metadata has duplicate team IDs.")
    players = list(root.iter("Player"))
    if not players or any(p.get("teamId") not in ids for p in players):
        raise InputError("ATD metadata has missing or unrecognised slot team membership.")
    slots = np.array([ids.index(p.get("teamId")) for p in players], dtype=np.int8)
    if len(set(slots)) != 2:
        raise InputError("ATD metadata must contain slots from both teams.")
    return slots, tuple(t.findtext("Name", "") for t in teams)


def read_tracking(meta_path, raw_path, n_frames, pitch):
    teams, names = metadata(meta_path)
    ball = np.full((n_frames, 3), np.nan, dtype=np.float32)
    players = np.full((n_frames, len(teams), 3), np.nan, dtype=np.float32)
    count = 0
    try:
        with open(raw_path, encoding="utf-8-sig") as handle:
            for line in handle:
                parts = line.strip().split(":")
                if len(parts) != 3 or count >= n_frames:
                    raise InputError("ATD record structure or record count is invalid.")
                if int(parts[0]) != count + 1:
                    raise InputError("ATD frame IDs must be consecutive, starting at one.")
                # The documented format has precisely x,y,speed per slot and ball.
                groups = parts[1].rstrip(";").split(";")
                if len(groups) != len(teams) or any(g.count(",") != 2 for g in groups):
                    raise InputError("ATD slot count or slot field count disagrees with metadata.")
                if parts[2].rstrip(";").count(",") != 2:
                    raise InputError("ATD ball must contain exactly three fields.")
                p = np.fromstring(",".join(groups), sep=",", dtype=np.float32)
                b = np.fromstring(parts[2].rstrip(";"), sep=",", dtype=np.float32)
                if p.size != len(teams) * 3 or b.size != 3:
                    raise InputError("ATD numeric record could not be parsed completely.")
                players[count] = p.reshape(-1, 3)
                ball[count] = b
                count += 1
    except InputError:
        raise
    except (OSError, ValueError, OverflowError):
        raise InputError("Cannot read ATD or invalid numeric field; input values suppressed.") from None
    if count != n_frames:
        raise InputError("ATD does not contain the expected number of tactical frames.")
    ball[:, :2] *= np.asarray(pitch, dtype=np.float32)
    players[:, :, :2] *= np.asarray(pitch, dtype=np.float32)
    return Tracking(ball, players, teams), names


def read_events(path, fps):
    events = []
    for node in _xml(path).iter("instance"):
        try:
            start = float(node.findtext("start"))
            end = float(node.findtext("end"))
            if not np.isfinite([start, end]).all() or end <= start:
                raise ValueError
            events.append({
                "start": round(start * fps), "end": round(end * fps),
                "code": (node.findtext("code") or "").strip().casefold(),
                "tags": {(label.findtext("group") or "").strip().casefold():
                         (label.findtext("text") or "").strip().casefold()
                         for label in node.findall("label")},
            })
        except (ValueError, TypeError, OverflowError):
            raise InputError("Smart Tagging has an invalid time interval; values suppressed.") from None
    return events


def write_submission(path, labels, expected):
    if len(labels) != expected or not np.isin(labels, list("HADX")).all():
        raise InputError("Internal submission contract failed.")
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    # Atomic replacement: an interrupted run never leaves a partial submission.
    fd, temporary = tempfile.mkstemp(prefix=".possession-", suffix=".tmp", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="ascii", newline="") as handle:
            handle.write("frame,label\n")
            handle.writelines(f"{i},{label}\n" for i, label in enumerate(labels))
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)
