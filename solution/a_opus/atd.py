"""Read the tactical ATD (FIFA/EPTS metadata XML + raw text) into numpy arrays. No kloppy.

The raw line is "<frame_id>:<player>;<player>;...:<ball>", each group comma-separated channels
with NaN for a missing observation (starter/baseline.py). Rather than assume which channels each
group carries, the layout is read from the metadata's DataFormatSpecification -- the part of the
EPTS file that exists to say exactly that -- and the documented layout (x, y, speed per player;
x, y first for the ball) is the fallback when it cannot be read.

Nothing here prints or returns rows: callers get arrays and a small summary of counts.
"""

import itertools
import unicodedata
import xml.etree.ElementTree as ET

import numpy as np

HOME, AWAY = 0, 1


def _local(tag):
    """Element name without its namespace."""
    return tag.rsplit("}", 1)[-1]


def _iter(root, name):
    return (el for el in root.iter() if _local(el.tag) == name)


def _text(el, name):
    for child in el:
        if _local(child.tag) == name:
            return (child.text or "").strip()
    return ""


def normalise_name(text):
    """Lower case, no accents, no punctuation: 'Athletic Club' and 'Atletic Club' compare."""
    text = unicodedata.normalize("NFKD", text or "")
    text = "".join(c for c in text if not unicodedata.combining(c)).lower()
    return "".join(c if c.isalnum() else " " for c in text).split()


def _role(channel_id, channel_name):
    """Map an EPTS channel to x / y / speed / z, or None."""
    for token in (channel_id or "", channel_name or ""):
        token = token.strip().lower()
        if token in ("x", "position_x", "pos_x") or token.endswith("_x"):
            return "x"
        if token in ("y", "position_y", "pos_y") or token.endswith("_y"):
            return "y"
        if token in ("z", "position_z", "pos_z", "height") or token.endswith("_z"):
            return "z"
        if token in ("s", "speed", "velocity") or "speed" in token:
            return "speed"
    return None


def read_metadata(meta_path, home_hint="barcelona"):
    """Teams, track slots and the raw-line layout from the EPTS metadata XML.

    Home side: the team whose name matches home_hint (DATA.md: home is Barcelona), else the
    Score element's idLocalTeam, else the first Team element (the convention starter/baseline.py
    uses). The rule that decided is reported, so a disagreement is visible.
    """
    root = ET.parse(meta_path).getroot()

    teams = [(el.get("id"), _text(el, "Name")) for el in _iter(root, "Team")]
    if len(teams) != 2:
        raise ValueError("{}: expected 2 teams, found {}".format(meta_path, len(teams)))
    hint = normalise_name(home_hint)
    by_name = [i for i, (_, name) in enumerate(teams) if all(w in normalise_name(name) for w in hint)]
    local_id = None
    for el in _iter(root, "Score"):
        local_id = el.get("idLocalTeam") or local_id
    if len(by_name) == 1:
        home_index, rule = by_name[0], "team name"
    elif local_id in [t[0] for t in teams]:
        home_index, rule = [t[0] for t in teams].index(local_id), "Score idLocalTeam"
    else:
        home_index, rule = 0, "first Team element"
    first_rule_agrees = home_index == 0
    home_id = teams[home_index][0]
    team_names = (teams[home_index][1], teams[1 - home_index][1])

    players = [(el.get("id"), el.get("teamId")) for el in _iter(root, "Player")]
    if not players:
        raise ValueError("{}: no Player entries".format(meta_path))
    player_team = {pid: (HOME if tid == home_id else AWAY) for pid, tid in players}

    channel_names = {el.get("id"): _text(el, "Name") for el in _iter(root, "Channel")}
    player_channels = {el.get("id"): (el.get("playerId"), el.get("channelId"))
                       for el in _iter(root, "PlayerChannel")}

    layout = _layout_from_spec(root, player_channels, channel_names)
    if layout is None:
        layout = {
            "sep": ":", "n_fields": 3, "i_frame": 0, "i_players": 1, "i_ball": 2,
            "player_sep": ";", "channel_sep": ",",
            "player_ids": [pid for pid, _ in players],
            "player_roles": ["x", "y", "speed"],
            "ball_sep": ",", "ball_roles": ["x", "y"],
            "source": "documented fallback",
        }

    slot_team = np.array([player_team.get(pid, AWAY) for pid in layout["player_ids"]],
                         dtype=np.int8)
    unknown_slots = sum(pid not in player_team for pid in layout["player_ids"])
    order_matches = layout["player_ids"] == [pid for pid, _ in players]

    return {
        "team_names": team_names,
        "home_rule": rule,
        "first_team_is_home": first_rule_agrees,
        "slot_team": slot_team,
        "n_slots": len(layout["player_ids"]),
        "unknown_slots": unknown_slots,
        "slot_order_matches_players": order_matches,
        "layout": layout,
    }


def _layout_from_spec(root, player_channels, channel_names):
    """Raw-line layout from the first DataFormatSpecification, or None if it cannot be read."""
    specs = list(_iter(root, "DataFormatSpecification"))
    if not specs:
        return None
    spec = specs[0]
    try:
        fields = list(spec)
        layout = {"sep": spec.get("separator") or ":", "n_fields": len(fields),
                  "i_frame": None, "i_players": None, "i_ball": None,
                  "source": "DataFormatSpecification"}
        for index, field in enumerate(fields):
            name = _local(field.tag)
            if name == "StringRegister" and layout["i_frame"] is None:
                layout["i_frame"] = index
            elif name == "SplitRegister":
                player_refs = list(_iter(field, "PlayerChannelRef"))
                ball_refs = list(_iter(field, "BallChannelRef"))
                if player_refs and layout["i_players"] is None:
                    layout["i_players"] = index
                    layout["player_sep"] = field.get("separator") or ";"
                    groups = [sub for sub in field if _local(sub.tag) == "SplitRegister"]
                    ids, roles = [], None
                    if groups:
                        layout["channel_sep"] = groups[0].get("separator") or ","
                        for group in groups:
                            refs = [player_channels.get(ref.get("playerChannelId"), (None, None))
                                    for ref in group if _local(ref.tag) == "PlayerChannelRef"]
                            ids.append(refs[0][0])
                            group_roles = [_role(cid, channel_names.get(cid)) for _, cid in refs]
                            if roles is None:
                                roles = group_roles
                            elif group_roles != roles:
                                return None  # heterogeneous groups: use the fallback
                    else:
                        return None
                    if any(pid is None for pid in ids) or len(set(ids)) != len(ids):
                        return None  # references that do not resolve: trust the fallback
                    layout["player_ids"] = ids
                    layout["player_roles"] = roles
                elif ball_refs and layout["i_ball"] is None:
                    layout["i_ball"] = index
                    layout["ball_sep"] = field.get("separator") or ","
                    layout["ball_roles"] = [_role(ref.get("channelId"),
                                                  channel_names.get(ref.get("channelId")))
                                            for ref in ball_refs]
        if None in (layout["i_frame"], layout["i_players"], layout["i_ball"]):
            return None
        if "x" not in layout["player_roles"] or "y" not in layout["player_roles"]:
            return None
        if "x" not in layout["ball_roles"] or "y" not in layout["ball_roles"]:
            return None
        return layout
    except (AttributeError, IndexError, KeyError, TypeError):
        return None


def _to_float(text):
    try:
        return float(text)
    except ValueError:
        return np.nan


def _parse_group(text, sep, n):
    """One comma group -> n floats, tolerant of a bare 'NaN' or a short group."""
    values = text.split(sep)
    if len(values) == n:
        return [_to_float(v) for v in values]
    out = [_to_float(v) for v in values[:n]]
    return out + [np.nan] * (n - len(out))


def read_raw(raw_path, meta, n_video_frames, chunk_lines=4096):
    """(players, ball, report) arrays indexed by VIDEO frame (frame_id - 1).

    players: float32 (n_video_frames, n_slots, n_player_channels), ball: float32
    (n_video_frames, n_ball_channels). Coordinates stay normalised here; frames the file does not
    cover stay NaN. Each chunk is parsed with one vectorised conversion when every line has the
    expected shape, and line by line otherwise.
    """
    layout = meta["layout"]
    n_slots = meta["n_slots"]
    n_pc = len(layout["player_roles"])
    n_bc = len(layout["ball_roles"])
    sep, psep, csep, bsep = layout["sep"], layout["player_sep"], layout["channel_sep"], \
        layout["ball_sep"]
    i_frame, i_players, i_ball = layout["i_frame"], layout["i_players"], layout["i_ball"]

    players = np.full((n_video_frames, n_slots, n_pc), np.nan, dtype=np.float32)
    ball = np.full((n_video_frames, n_bc), np.nan, dtype=np.float32)
    report = {"n_records": 0, "first_id": None, "last_id": None, "out_of_range": 0,
              "slow_lines": 0, "bad_lines": 0}
    expected_values = n_slots * n_pc

    with open(raw_path, "r") as handle:
        while True:
            lines = list(itertools.islice(handle, chunk_lines))
            if not lines:
                break
            parts = [line.rstrip("\r\n").split(sep) for line in lines]
            ids, prow, brow = [], [], []
            fast = True
            for fields in parts:
                if len(fields) <= max(i_frame, i_players, i_ball):
                    report["bad_lines"] += 1
                    continue
                try:
                    frame_id = int(fields[i_frame])
                except ValueError:
                    report["bad_lines"] += 1
                    continue
                ids.append(frame_id)
                prow.append(fields[i_players])
                brow.append(fields[i_ball])
            if not ids:
                continue

            player_block = None
            if fast:
                values = csep.join(prow).replace(psep, csep).split(csep) if psep != csep \
                    else csep.join(prow).split(csep)
                if len(values) == len(ids) * expected_values:
                    try:
                        player_block = np.array(values, dtype=np.float32).reshape(
                            len(ids), n_slots, n_pc)
                    except ValueError:
                        player_block = None
            if player_block is None:
                report["slow_lines"] += len(ids)
                player_block = np.full((len(ids), n_slots, n_pc), np.nan, dtype=np.float32)
                for row, text in enumerate(prow):
                    groups = text.split(psep)
                    for slot, group in enumerate(groups[:n_slots]):
                        player_block[row, slot] = _parse_group(group, csep, n_pc)

            ball_block = np.array([_parse_group(text, bsep, n_bc) for text in brow],
                                  dtype=np.float32)

            ids = np.asarray(ids, dtype=np.int64)
            video = ids - 1
            inside = (video >= 0) & (video < n_video_frames)
            report["out_of_range"] += int(np.sum(~inside))
            players[video[inside]] = player_block[inside]
            ball[video[inside]] = ball_block[inside]
            report["n_records"] += len(ids)
            if report["first_id"] is None:
                report["first_id"] = int(ids[0])
            report["last_id"] = int(ids[-1])

    report["contiguous"] = (report["first_id"] == 1
                            and report["last_id"] == report["n_records"]
                            and report["bad_lines"] == 0)
    return players, ball, report


def load(atd_meta, atd_raw, n_video_frames, pitch):
    """Everything downstream needs from the ATD, in metres, plus a summary for the log."""
    meta = read_metadata(atd_meta)
    players, ball, report = read_raw(atd_raw, meta, n_video_frames)
    layout = meta["layout"]
    length, width = pitch

    proles, broles = layout["player_roles"], layout["ball_roles"]
    px = players[:, :, proles.index("x")] * np.float32(length)
    py = players[:, :, proles.index("y")] * np.float32(width)
    ps = players[:, :, proles.index("speed")] if "speed" in proles else None
    bx = ball[:, broles.index("x")] * np.float32(length)
    by = ball[:, broles.index("y")] * np.float32(width)
    bz = ball[:, broles.index("z")] if "z" in broles else None
    # A ball needs both coordinates; a player too.
    seen = np.isfinite(bx) & np.isfinite(by)
    bx[~seen] = np.nan
    by[~seen] = np.nan
    present = np.isfinite(px) & np.isfinite(py)
    px[~present] = np.nan
    py[~present] = np.nan
    if ps is not None:
        ps = np.where(present, ps, np.nan).astype(np.float32)
    del players, ball

    summary = dict(report)
    summary.update({
        "layout_source": layout["source"],
        "player_channels": [r or "?" for r in proles],
        "ball_channels": [r or "?" for r in broles],
        "n_slots": meta["n_slots"],
        "slots_home": int(np.sum(meta["slot_team"] == HOME)),
        "slots_away": int(np.sum(meta["slot_team"] == AWAY)),
        "unknown_slots": meta["unknown_slots"],
        "slot_order_matches_players": meta["slot_order_matches_players"],
        "home_rule": meta["home_rule"],
        "first_team_is_home": meta["first_team_is_home"],
        "ball_seen_pct": 100.0 * float(np.mean(seen)),
    })
    return {
        "px": px, "py": py, "ps": ps, "bx": bx, "by": by, "bz": bz,
        "slot_team": meta["slot_team"], "team_names": meta["team_names"],
        "summary": summary,
    }
