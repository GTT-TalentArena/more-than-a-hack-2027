"""DFL/IDSSE files -> one cached array file per match (needs kloppy; see heldout/requirements.lock).

    python -m heldout.convert [MATCH_ID ...]

Writes salidas/heldout/arrays/<match>.npz with:
  period   (n,)       1 or 2
  ball     (n, 3)     x, y in the challenge's metres (Metrica orientation), speed in m/s
  players  (n, P, 3)  the same per player; NaN when the player is not on the pitch
  team     (P,)       0 = home, 1 = away
  label    (n,)       target only (0..3 = H A D X), never read by heldout.degrade (§1.3)

Loaded with only_alive=False: kloppy's default drops every dead-ball frame (§1.1). Coordinates are
kloppy's Metrica system (0..1, origin top-left), the challenge ATD's convention, scaled to the
challenge pitch (105.3 x 68.0 m). Speeds are recomputed from positions so their unit does not
depend on the provider (DFL reports km/h; the challenge ATD m/s).
"""

import argparse
import glob
import json
import os
import sys

import numpy as np

from .fetch import MATCHES, default_dir as raw_dir

PITCH = (105.3, 68.0)
FPS = 25
SPEED_HALF = 3  # +/- 3 frames: a 0.24 s chord, as noise-robust as the challenge ATD's speeds


def arrays_dir():
    return os.path.join(os.path.dirname(raw_dir()), "arrays")


def speed(xy, period):
    """m/s from positions, central chord within each half; NaN where an end is missing."""
    out = np.full(len(xy), np.nan, dtype=np.float32)
    for p in np.unique(period):
        idx = np.flatnonzero(period == p)
        a, b = idx[0], idx[-1] + 1
        seg = xy[a:b].astype(np.float64)
        lo = np.clip(np.arange(len(seg)) - SPEED_HALF, 0, len(seg) - 1)
        hi = np.clip(np.arange(len(seg)) + SPEED_HALF, 0, len(seg) - 1)
        span = np.maximum(hi - lo, 1)
        out[a:b] = np.linalg.norm(seg[hi] - seg[lo], axis=-1) * FPS / span
    return out


def convert(match_id, src, out):
    from kloppy import sportec
    from kloppy.domain import BallState
    meta = glob.glob(os.path.join(src, "*matchinformation*{}.xml".format(match_id)))[0]
    raw = glob.glob(os.path.join(src, "*positions_raw_observed*{}.xml".format(match_id)))[0]
    ds = sportec.load_tracking(meta_data=meta, raw_data=raw, only_alive=False, coordinates="metrica")
    home, away = ds.metadata.teams
    players = [p for team in (home, away) for p in team.players]
    column = {p.player_id: k for k, p in enumerate(players)}
    team = np.array([0 if p.team.team_id == home.team_id else 1 for p in players], dtype=np.int8)

    n = len(ds.frames)
    period = np.empty(n, dtype=np.int8)
    label = np.full(n, 3, dtype=np.int8)
    ball = np.full((n, 3), np.nan, dtype=np.float32)
    pos = np.full((n, len(players), 3), np.nan, dtype=np.float32)
    for t, frame in enumerate(ds.frames):
        period[t] = frame.period.id
        if frame.ball_state == BallState.DEAD:
            label[t] = 2
        elif frame.ball_state == BallState.ALIVE and frame.ball_owning_team is not None:
            label[t] = 0 if frame.ball_owning_team.team_id == home.team_id else 1
        c = frame.ball_coordinates
        if c is not None and c.x is not None and c.y is not None:
            ball[t, :2] = (c.x * PITCH[0], c.y * PITCH[1])
        for player, data in frame.players_data.items():
            if data.coordinates is not None:
                pos[t, column[player.player_id], :2] = (data.coordinates.x * PITCH[0],
                                                         data.coordinates.y * PITCH[1])
    ball[:, 2] = speed(ball[:, :2], period)
    for k in range(len(players)):
        pos[:, k, 2] = speed(pos[:, k, :2], period)

    os.makedirs(out, exist_ok=True)
    path = os.path.join(out, match_id + ".npz")
    np.savez_compressed(path, period=period, ball=ball, players=pos, team=team, label=label)
    summary = {"match": match_id, "frames": int(n),
               "frames_per_half": {int(p): int((period == p).sum()) for p in np.unique(period)},
               "players": len(players), "ball_missing_share": float(np.mean(~np.isfinite(ball[:, 0]))),
               "label_counts": {"HADX"[k]: int((label == k).sum()) for k in range(4)}}
    with open(os.path.join(out, match_id + ".json"), "w") as handle:
        json.dump(summary, handle, indent=2)
    return summary


def load(match_id, folder=None):
    with np.load(os.path.join(folder or arrays_dir(), match_id + ".npz")) as data:
        return {key: data[key] for key in data.files}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("matches", nargs="*", default=list(MATCHES))
    parser.add_argument("--src", default=raw_dir())
    parser.add_argument("--out", default=arrays_dir())
    args = parser.parse_args(argv)
    for match_id in args.matches:
        if os.path.exists(os.path.join(args.out, match_id + ".npz")):
            print("have", match_id, flush=True)
            continue
        print(json.dumps(convert(match_id, args.src, args.out)), flush=True)
    return 0


if __name__ == "__main__":
    sys.exit(main())
