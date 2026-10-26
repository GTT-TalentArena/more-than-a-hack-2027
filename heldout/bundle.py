"""Write an observation in the challenge's file format, so every model runs unmodified (§3.1).

The bundle has exactly the files and layout games.asset_paths() expects for the tactical source:
FIFA/EPTS metadata (XML), raw tracking (TXT) and Smart Tagging (XML, with no instances: §1.3).
Each DFL half is placed at the start of the matching challenge half (games.half_video_blocks), so
models keep the challenge's frame count and halves; the rest of each block has no tracking and
is labelled X, i.e. never scored. Ground truth is written beside the bundle, never inside it.
"""

import hashlib
import os

import numpy as np

import games
from .degrade import SLOTS_PER_TEAM

GAME = games.GAME
PITCH = tuple(games.GAMES[GAME]["pitch"])
N_FRAMES = games.source_frames("tactical", GAME)
# The challenge's team names: every model decides the home side the same way it does on the
# challenge game. Home in the bundle is the DFL home team.
HOME_NAME, AWAY_NAME = "FC Barcelona", "Athletic Club"
LETTERS = np.array(list("HADX"))


def placement(period):
    """For each challenge frame, the DFL frame index placed there (-1 = nothing). Fails if a
    DFL half is longer than the challenge half it goes into."""
    index = np.full(N_FRAMES, -1, dtype=np.int64)
    for half, first, last in games.half_video_blocks(GAME):
        frames = np.flatnonzero(period == half)
        if len(frames) > last - first + 1:
            raise ValueError("DFL half {} has {} frames, the challenge half only {}".format(
                half, len(frames), last - first + 1))
        index[first:first + len(frames)] = frames
    return index


def _metadata(n_slots):
    order = [k for pair in zip(range(SLOTS_PER_TEAM), range(SLOTS_PER_TEAM, 2 * SLOTS_PER_TEAM))
             for k in pair]
    team_of = ["T1" if s < SLOTS_PER_TEAM else "T2" for s in order]
    lines = ['<?xml version="1.0" encoding="utf-8"?>', "<main>", "  <Metadata>",
             "    <GlobalConfig><FrameRate>25</FrameRate><ProviderName>GTT held-out (DFL open data)"
             "</ProviderName></GlobalConfig>",
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
    lines += ["    </PlayerChannels>", "  </Metadata>", "  <DataFormatSpecifications>",
              '    <DataFormatSpecification separator=":" startFrame="1" endFrame="{}">'.format(N_FRAMES),
              '      <StringRegister name="frameCount"/>', '      <SplitRegister separator=";">']
    for i in range(n_slots):
        lines.append('        <SplitRegister separator=",">'
                     '<PlayerChannelRef playerChannelId="player{0}_x"/>'
                     '<PlayerChannelRef playerChannelId="player{0}_y"/>'
                     '<PlayerChannelRef playerChannelId="player{0}_speed"/>'
                     "</SplitRegister>".format(i))
    lines += ["      </SplitRegister>",
              '      <SplitRegister separator=",">'
              '<BallChannelRef channelId="x"/><BallChannelRef channelId="y"/>'
              '<BallChannelRef channelId="speed"/></SplitRegister>',
              "    </DataFormatSpecification>", "  </DataFormatSpecifications>", "</main>"]
    return order, "\n".join(lines) + "\n"


def _group(x, y, s):
    if not (np.isfinite(x) and np.isfinite(y)):
        return "NaN,NaN,NaN"
    return "{:.5f},{:.5f},{:.2f}".format(x / PITCH[0], y / PITCH[1], s if np.isfinite(s) else 0.0)


def write(out_dir, observation, period):
    """Write the bundle into out_dir/tactical/. Returns {asset: sha256} of the written inputs."""
    paths = games.asset_paths(GAME, data_dir=out_dir)
    os.makedirs(os.path.dirname(paths["atd_meta"]), exist_ok=True)
    where = placement(period)
    ball, slots = observation["ball"], observation["slots"]
    order, meta = _metadata(slots.shape[1])
    with open(paths["atd_meta"], "w", encoding="utf-8", newline="\n") as handle:
        handle.write(meta)
    empty = ";".join(["NaN,NaN,NaN"] * slots.shape[1])
    with open(paths["atd_raw"], "w", newline="\n") as handle:
        for t in range(N_FRAMES):
            k = where[t]
            if k < 0:
                handle.write("{}:{}:NaN,NaN,NaN\n".format(t + 1, empty))
                continue
            row = slots[k, order]
            groups = ";".join(_group(*g) for g in row)
            handle.write("{}:{}:{}\n".format(t + 1, groups, _group(*ball[k])))
    with open(paths["smart_tagging"], "w", encoding="utf-8", newline="\n") as handle:
        handle.write('<?xml version="1.0" encoding="utf-8"?>\n<file>\n  <ALL_INSTANCES>\n'
                     "  </ALL_INSTANCES>\n</file>\n")
    return {name: sha256(paths[name]) for name in ("atd_meta", "atd_raw", "smart_tagging")}


def ground_truth(label, period):
    """Challenge-length label codes (0..3 = H A D X): X wherever no DFL frame is placed."""
    where = placement(period)
    codes = np.full(N_FRAMES, 3, dtype=np.int8)
    codes[where >= 0] = label[where[where >= 0]]
    return codes


def write_ground_truth(path, codes):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", newline="\n") as handle:
        handle.write("frame,label\n")
        handle.write("".join("{},{}\n".format(i, c) for i, c in enumerate(LETTERS[codes])))


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()
