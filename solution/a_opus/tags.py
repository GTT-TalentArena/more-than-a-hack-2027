"""Smart Tagging: load the intervals and map each Team tag to a side.

Reading the XML is starter/load_smart_tagging.py's job and is reused as is. What this module adds
is the side: the XML names clubs ('Barcelona', 'Atletic Club', 'N/A'), the submission wants H or A,
and the ATD metadata may spell the clubs differently.
"""

import difflib

from .atd import HOME, AWAY, normalise_name

# Codes whose Team tag is the side WITH the ball, and codes whose Team tag is the side WITHOUT it
# (OVERVIEW.md: "Team -- the team performing the event"; a team performs defending phases when the
# other one has the ball). This is only the prior: pipeline.calibrate_tag_codes re-estimates the
# polarity and reliability of every code against ball proximity, without labels.
IN_POSSESSION = (
    "build up", "progression", "creating chances", "ball in final third", "ball in the box",
    "players in the box", "long ball", "attacking transition",
)
OUT_OF_POSSESSION = (
    "defending in defensive third", "defending in middle third", "defending in attacking third",
    "defensive transition",
)
SET_PIECES = "set pieces"
KICKOFF_TYPES = ("kick off (start)", "kick off (after goal)")

GENERIC_WORDS = {"fc", "cf", "club", "sc", "ud", "cd", "sd", "rc", "the", "de", "del"}
HOME_WORDS = ("barcelona", "barca")
AWAY_WORDS = ("athletic", "atletic", "bilbao")


def _significant(name):
    return " ".join(w for w in normalise_name(name) if w not in GENERIC_WORDS)


def side_of(team_tag, team_names):
    """HOME, AWAY or None for a Team tag value, matched against the ATD club names."""
    words = normalise_name(team_tag)
    if not words or words in (["n", "a"], ["na"], ["none"]):
        return None
    tag = _significant(team_tag)
    if tag:
        ratios = [difflib.SequenceMatcher(None, tag, _significant(name)).ratio()
                  for name in team_names]
        best = max(range(2), key=lambda i: ratios[i])
        if ratios[best] >= 0.6 and ratios[best] - ratios[1 - best] >= 0.15:
            return HOME if best == 0 else AWAY
    if any(w in words for w in HOME_WORDS):
        return HOME
    if any(w in words for w in AWAY_WORDS):
        return AWAY
    return None


def load(game, data_dir, team_names):
    """[{code, start, end, side, type}] with frames half-open on the right, or [] if absent.

    A missing or unreadable file is not fatal -- every use of the tags is a prior on top of the
    tracking -- but it is reported.
    """
    try:
        from starter import load_smart_tagging
        events = load_smart_tagging.load(game, data_dir)
    except (IOError, OSError, ImportError) as error:
        return [], "Smart Tagging not used: {}".format(str(error).splitlines()[0])

    out = []
    for event in events:
        tags = {str(k).strip().lower(): v for k, v in event["tags"].items()}
        out.append({
            "code": (event["code"] or "").strip().lower(),
            "start": int(event["start_frame"]),
            "end": max(int(event["end_frame"]), int(event["start_frame"]) + 1),
            "side": side_of(tags.get("team") or "", team_names),
            "type": (tags.get("type") or "").strip().lower(),
        })
    return out, None


def prior_polarity(code):
    """+1 if the tagged side has the ball, -1 if the other side has it, 0 if not a phase."""
    if code in IN_POSSESSION:
        return 1
    if code in OUT_OF_POSSESSION:
        return -1
    return 0
