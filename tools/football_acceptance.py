"""Invented development scenarios for issue #47; no real-data input is accepted.

Run with python -m tools.football_acceptance --out salidas/football/report.json.
--check returns 1 for unmet strict targets or symmetry flags. Report creation alone
is not a model-quality pass. Candidate A is run unchanged, not replaced.
"""
import argparse
from contextlib import ExitStack, contextmanager
from dataclasses import dataclass, replace
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import platform
import subprocess
import tempfile
import warnings
import xml.etree.ElementTree as ET
from unittest.mock import patch

import numpy as np

import games
from evaluation import possession_metrics as pm
from heldout import bundle
from solution import dead_ball
from solution.a_opus import config as a_config, pipeline as a_pipeline

FPS = games.GAMES[games.GAME]["fps"]
PITCH = np.asarray(games.GAMES[games.GAME]["pitch"])
VERSION = "1.0"


@dataclass
class Scenario:
    """Observations and evaluator-only references, deliberately separate."""
    id: str
    condition: str
    ball: np.ndarray
    players: np.ndarray
    period: np.ndarray
    events: list
    expected: np.ndarray
    observability: str = "clean"
    bracket: tuple = ()
    mirror: bool = False
    offset: int = 0
    permuted: bool = False

    def observations(self):
        return {"ball": self.ball.copy(), "players": self.players.copy(),
                "period": self.period.copy(), "events": self.events}


def labels(*runs):
    return np.concatenate([np.full(n, team, dtype="<U1") for team, n in runs])


def moving_ball(n, speed=3., spot=(20., 30.)):
    return np.column_stack((spot[0] + np.arange(n) * speed / FPS,
                            np.full(n, spot[1])))


def approach_distances(desired):
    distance = np.asarray(desired, float).copy()
    for t in range(len(distance) - 2, -1, -1):
        distance[t] = min(distance[t], distance[t + 1] + .4)
    for t in range(1, len(distance)):
        distance[t] = min(distance[t], distance[t - 1] + .4)
    return distance


def players_for(ball, owner):
    """22 team-known slots; carriers approach/leave with bounded lateral speed.

    The scripted owner controls the world, not a model feature. Observations
    carry positions/speeds only. References are constructed by each scenario.
    """
    n = len(ball)
    out = np.zeros((n, 22, 3))
    for slot in range(22):
        out[:, slot, 0] = 12 + (slot % 11) * 7 + np.arange(n) / FPS
        out[:, slot, 1] = 5 + (slot * 13) % 57
    # Keep the supporting players away from the scripted ball corridor.
    out[:, :, 1] = np.where(out[:, :, 1] < 34, 8., 60.)
    for team, slot in (("H", 0), ("A", 11)):
        desired = np.where(np.asarray(owner) == team, .5, 6.)
        # A maximum 0.4 m/frame lateral approach or departure, independent of
        # any candidate's thresholds. Interpolate hidden ball motion locally.
        distance = approach_distances(desired)
        out[:, slot, :2] = ball + np.column_stack((np.zeros(n), distance))
    out[1:, :, 2] = np.linalg.norm(np.diff(out[:, :, :2], axis=0), axis=2) * FPS
    out[0, :, 2] = out[1, :, 2] if n > 1 else 0
    return out


def event(start, end, kind):
    return {"code": "SET PIECES", "start_frame": start, "end_frame": end,
            "tags": {"Type": kind, "Team": "Barcelona"}}


def scenarios():
    """All concrete cases are public development examples, not held-out data."""
    result = []

    def add(id, condition, ball, owner, expected, events=(), **extra):
        result.append(Scenario(id, condition, ball, players_for(ball, owner),
                               np.ones(len(ball), dtype=int), list(events), expected, **extra))

    truth = labels(("H", 50), ("A", 30), ("H", 50))
    add("FA01", "short-control", moving_ball(130), truth, truth.copy())
    truth = labels(("H", 114))
    ball = moving_ball(114)
    ball[50:, 0] += np.minimum(np.arange(64), 12) * 12 / FPS
    add("FA02", "deflection", ball, labels(("H", 50), ("A", 2), ("H", 62)), truth)
    add("FA03", "contested", moving_ball(140), labels(("H", 50), ("?", 40), ("H", 50)),
        labels(("H", 140)))
    # Both teams are equally near during the contest, not a hidden A recovery.
    for slot, sign in ((0, 1), (11, -1)):
        desired = np.full(140, .5 if slot == 0 else 6.)
        desired[50:90] = .7
        result[-1].players[:, slot, :2] = result[-1].ball + np.column_stack(
            (np.zeros(140), sign * approach_distances(desired)))
    for id, final in (("FA04", "H"), ("FA05", "A")):
        truth = labels(("H", 100), (final, 50))
        add(id, "missing-ball", moving_ball(150), truth, truth.copy(),
            observability="bracket" if id == "FA05" else "clean",
            bracket=(49, 104) if id == "FA05" else ())
        result[-1].ball[50:100] = np.nan
    for kind, spot in (("Throw-in", (40., .1)), ("Corner Kick", (.1, .1)),
                       ("Free Kick", (45., 30.))):
        ball = moving_ball(175, spot=spot)
        ball[50:125] = [ball[49, 0], -.6] if kind != "Free Kick" else ball[49]
        ball[125:, 0] = ball[124, 0] + np.arange(1, 51) * 3 / FPS
        ball[125:, 1] = .12 + np.arange(50) * 3 / FPS if kind != "Free Kick" else 30.
        if kind == "Corner Kick":
            # Keep the restart at the corner, with continuous approach and
            # plausible motion, rather than six metres along the touchline.
            ball[:50, 0] = .1
            ball[:50, 1] = 6. - np.arange(50) * .12
            ball[50:125] = [.1, -.6]
            ball[125:, 0] = .1 + np.arange(1, 51) * 3 / FPS
            ball[125:, 1] = .12
        truth = labels(("H", 50), ("D", 75), ("H", 50))
        add("FA06", kind, ball, labels(("H", 175)), truth, [event(30, 165, kind)])
    for smooth in (False, True):
        speed = np.r_[np.zeros(75), [.7, 1.1, 1.6, 1.9], np.full(71, 3.)]
        ball = np.column_stack((45 + np.cumsum(speed) / FPS, np.full(150, 30.)))
        if smooth:
            ball[:, 0] = np.convolve(np.pad(ball[:, 0], (12, 12), mode="edge"),
                                      np.ones(25) / 25, mode="valid")
        add("FA07", "smoothed" if smooth else "gradual", ball, labels(("H", 150)),
            labels(("D", 75), ("H", 75)), [event(20, 130, "Free Kick")],
            observability="diagnostic")
    for shift in (-25, 0, 25):
        ball = moving_ball(150, speed=2.5, spot=tuple(PITCH / 2))
        ball[:75] = PITCH / 2
        ball[75:, 0] = PITCH[0] / 2 + np.arange(1, 76) * 2.5 / FPS
        ball[:20] = moving_ball(20, speed=2.5, spot=(45., 20.))
        ball[20:50] = np.linspace(ball[19], PITCH / 2, 31)[1:]
        add("FA08", "tag-shift-{:+d}".format(shift), ball, labels(("H", 150)),
            labels(("D", 75), ("H", 75)), [event(50 + shift, 120 + shift, "Kick Off (Start)")],
            observability="diagnostic")
        # This kickoff really belongs to period 2, after an independently
        # observed first half and an unscored break, rather than a renamed half.
        case = result[-1]
        previous = moving_ball(100)
        case.ball = np.vstack((previous, np.full((25, 2), np.nan), case.ball))
        case.players = np.concatenate((players_for(previous, labels(("H", 100))),
                                       np.tile(case.players[:1], (25, 1, 1)), case.players))
        case.expected = np.r_[labels(("H", 100), ("X", 25)), case.expected]
        case.period = np.r_[np.ones(100, int), np.zeros(25, int), np.full(150, 2, int)]
        for item in case.events:
            item["start_frame"] += 125
            item["end_frame"] += 125
    for available in (True, False):
        ball = moving_ball(225)
        truth = labels(("H", 100), ("X", 25), ("A" if available else "X", 100))
        add("FA09", "control" if available else "unsupported", ball, truth, truth.copy(),
            observability="reset")
        result[-1].period = np.r_[np.ones(100, int), np.zeros(25, int), np.full(100, 2, int)]
        result[-1].ball[100:125] = np.nan
        if not available:
            result[-1].ball[125:] = np.nan
    for tagged in (True, False):
        add("FA10", "tag-only" if tagged else "no-evidence", moving_ball(150), labels(("?", 150)),
            labels(("X", 150)), [event(25, 125, "Kick Off (Start)")] if tagged else [],
            observability="unsupported")
        result[-1].ball[:] = np.nan
    # Recompute reported speeds after intentional contest edits. Missingness
    # concerns the ball only; players remain original, finite observations.
    for case in result:
        case.players[1:, :, 2] = np.linalg.norm(np.diff(case.players[:, :, :2], axis=0), axis=2) * FPS
        reset = np.r_[True, case.period[1:] != case.period[:-1]] | (case.period == 0)
        case.players[reset, :, 2] = 0.
    return result


def transform(case, mirror=False, offset=0, permute=False):
    """Symmetry/placement probes; no independent validation claim."""
    ball, players = case.ball.copy(), case.players.copy()
    expected = case.expected.copy()
    events = json.loads(json.dumps(case.events))
    if mirror:
        players = np.concatenate((players[:, 11:], players[:, :11]), axis=1)
        expected = np.where(expected == "H", "A", np.where(expected == "A", "H", expected))
        for item in events:
            item["tags"]["Team"] = "Athletic Club"
    if permute:
        order = np.r_[np.arange(10, -1, -1), np.arange(21, 10, -1)]
        players = players[:, order]
    if offset:
        # Unscored prefix: moving a case changes no inference context within it.
        ball = np.vstack((np.full((offset, 2), np.nan), ball))
        players = np.concatenate((np.full((offset, 22, 3), np.nan), players))
        expected = np.r_[np.full(offset, "X"), expected]
        for item in events:
            item["start_frame"] += offset
            item["end_frame"] += offset
    return replace(case, ball=ball, players=players, expected=expected, events=events,
                   period=np.r_[np.zeros(offset, int), case.period], mirror=mirror, offset=offset,
                   permuted=permute, bracket=tuple(x + offset for x in case.bracket))


def observation_hash(case):
    digest = hashlib.sha256()
    for key, value in case.observations().items():
        digest.update(key.encode())
        digest.update(json.dumps(value, sort_keys=True).encode() if key == "events"
                      else np.ascontiguousarray(value).tobytes())
    return digest.hexdigest()


def p2_signals(case):
    observed = np.isfinite(case.ball).all(axis=1)
    count = np.isfinite(case.players[:, :, :2]).all(axis=2).sum(axis=1)
    collective = np.full(len(case.ball), np.nan)
    collective[count > 0] = np.nanmedian(case.players[count > 0, :, 2], axis=1)
    return dead_ball.detect(case.ball, observed, case.period, case.events,
                            FPS, PITCH, collective, count)


def raw_runs(sequence):
    if not len(sequence):
        return []
    edges = np.r_[0, np.flatnonzero(sequence[1:] != sequence[:-1]) + 1, len(sequence)]
    return [(str(sequence[a]), int(a), int(b)) for a, b in zip(edges[:-1], edges[1:])]


def assess(case, predicted):
    """Strict raw-label targets; diagnostic timing never becomes a fake pass."""
    predicted = np.asarray(predicted)
    if predicted.shape != case.expected.shape or not set(predicted) <= set("HADX"):
        raise ValueError("Prediction must contain one H/A/D/X label per synthetic frame")
    active = case.period > 0
    actual, truth = predicted[active], case.expected[active]
    # Do not compress halftime and accidentally merge equal team spells.
    got, want, errors, restarts = [], [], [], []
    same_topology = True
    for period in np.unique(case.period[active]):
        indices = np.flatnonzero(case.period == period)
        a, b = raw_runs(predicted[indices]), raw_runs(case.expected[indices])
        matching = [r[0] for r in a] == [r[0] for r in b]
        same_topology &= matching
        if matching:
            errors.extend(x[1] - y[1] for x, y in zip(a[1:], b[1:]))
        expected_restarts = [(v[0], v[1]) for u, v in zip(b, b[1:]) if u[0] == "D" and v[0] in "HA"]
        predicted_restarts = [(v[0], v[1]) for u, v in zip(a, a[1:]) if u[0] == "D" and v[0] in "HA"]
        used = set()
        matched_errors = []
        for team, frame in expected_restarts:
            eligible = [(abs(t - frame), j, t - frame) for j, (s, t) in enumerate(predicted_restarts)
                        if j not in used and s == team and abs(t - frame) <= 25]
            if eligible:
                _, j, error = min(eligible)
                used.add(j)
                matched_errors.append(error)
        restarts.append({"period": int(period), "tolerance_frames": 25,
                         "expected": len(expected_restarts), "predicted": len(predicted_restarts),
                         "missed": len(expected_restarts) - len(used),
                         "spurious": len(predicted_restarts) - len(used),
                         "matched_errors_frames": matched_errors})
        got.extend(a)
        want.extend(b)
    boundary_errors = errors if same_topology else None
    if case.observability == "clean":
        status = "pass" if np.array_equal(actual, truth) else "fail"
    elif case.observability == "bracket":
        transitions = np.flatnonzero(predicted[1:] != predicted[:-1]) + 1
        transitions = [int(t) for t in transitions if case.period[t] > 0 and case.period[t - 1] > 0]
        inside = len(transitions) == 1 and case.bracket[0] < transitions[0] <= case.bracket[1]
        status = "pass" if same_topology and inside else "fail"
        boundary_errors = None  # The hidden physical transition has no observable target.
    else:
        status = "diagnostic"
    return {"scenario": case.id, "condition": case.condition, "mirror": case.mirror,
            "offset": case.offset, "permuted": case.permuted, "status": status,
            "observability": case.observability, "observation_sha256": observation_hash(case),
            "restarts": restarts,
            "same_topology": same_topology, "boundary_errors_frames": boundary_errors,
            "boundary_errors_seconds": None if boundary_errors is None else [v / FPS for v in boundary_errors],
            "abstentions": int(np.sum(actual == "X")),
            "false_dead_frames": int(np.sum((actual == "D") & np.isin(truth, ["H", "A"]))),
            "expected_team_spells": sum(t in "HA" for t, _, _ in want),
            "predicted_team_spells": sum(t in "HA" for t, _, _ in got)}


@contextmanager
def synthetic_bundle(case, directory, full_size=False):
    """The normal EPTS readers and pipeline; only the compact timeline is mocked.

    Full-size mode uses games.py unchanged and validates the official 199319-row
    contract. No target file is written inside the model's input directory.
    """
    obs = case.observations()
    active = case.period > 0
    original_indices = np.flatnonzero(active)
    periods = case.period[active]
    ball = case.ball[active]
    slots = np.full((len(ball), 46, 3), np.nan)
    slots[:, :11] = case.players[active, :11]
    slots[:, 23:34] = case.players[active, 11:]
    speed = np.full(len(ball), np.nan)
    pairs = (periods[1:] == periods[:-1]) & np.isfinite(ball[1:]).all(axis=1) & np.isfinite(ball[:-1]).all(axis=1)
    speed[np.flatnonzero(pairs) + 1] = np.linalg.norm(np.diff(ball, axis=0)[pairs], axis=1) * FPS
    observed = {"ball": np.column_stack((ball, speed)), "slots": slots}
    with ExitStack() as stack:
        if not full_size:
            sizes = [int(np.sum(periods == p)) for p in (1, 2)]
            # Supply an observed companion half so A's normal cross-half code runs.
            if not sizes[1]:
                companion = moving_ball(150)
                companion_players = players_for(companion, labels(("A" if case.mirror else "H", 150)))
                if case.permuted:
                    companion_players = companion_players[:, np.r_[np.arange(10, -1, -1), np.arange(21, 10, -1)]]
                other = np.full((150, 46, 3), np.nan)
                other[:, :11] = companion_players[:, :11]
                other[:, 23:34] = companion_players[:, 11:]
                observed["ball"] = np.vstack((observed["ball"], np.column_stack((companion, np.full(150, 3.)))))
                observed["slots"] = np.concatenate((slots, other))
                periods = np.r_[periods, np.full(150, 2)]
                sizes[1] = 150
            first = 25 + case.offset
            second = first + sizes[0] + 25
            blocks = [(1, first, first + sizes[0] - 1), (2, second, second + sizes[1] - 1)]
            n = second + sizes[1] + 25
            stack.enter_context(patch.object(games, "source_frames", return_value=n))
            stack.enter_context(patch.object(games, "half_video_blocks", return_value=blocks))
            stack.enter_context(patch.object(bundle, "N_FRAMES", n))
        else:
            blocks = games.half_video_blocks(games.GAME)
            n = games.source_frames()
        bundle.write(str(directory), observed, periods)
        where = bundle.placement(periods)
        target_indices = np.flatnonzero(where >= 0)[:len(original_indices)]
        mapping = dict(zip(original_indices.tolist(), target_indices.tolist()))
        # Shift imperfect event windows onto the input timeline without consulting targets.
        xml = ET.Element("file")
        all_events = ET.SubElement(xml, "ALL_INSTANCES")
        for item in obs["events"]:
            available = [i for i in mapping if item["start_frame"] <= i < item["end_frame"]]
            if not available:
                continue
            instance = ET.SubElement(all_events, "instance")
            ET.SubElement(instance, "code").text = item["code"]
            ET.SubElement(instance, "start").text = str(mapping[min(available)] / FPS)
            ET.SubElement(instance, "end").text = str((mapping[max(available)] + 1) / FPS)
            for key, value in item["tags"].items():
                label = ET.SubElement(instance, "label")
                ET.SubElement(label, "group").text = key
                ET.SubElement(label, "text").text = value
        path = games.asset_paths(data_dir=str(directory))["smart_tagging"]
        ET.ElementTree(xml).write(path, encoding="utf-8", xml_declaration=True)
        yield n, target_indices, original_indices


def run_a(case, full_size=False):
    with tempfile.TemporaryDirectory(prefix="issue47-invented-") as temp:
        root = Path(temp)
        with synthetic_bundle(case, root / "inputs", full_size) as (n, target, original):
            with warnings.catch_warnings(record=True) as seen:
                warnings.simplefilter("always", RuntimeWarning)
                a_pipeline.run(str(root / "prediction.csv"), str(root / "inputs"), log=lambda *args: None)
            table = pm.read_label_csv(str(root / "prediction.csv"))
            error = pm.validate_submission(table, n)
            if error is not None:
                raise ValueError(error)
            raw = table["label"].to_numpy()
            output = np.full(len(case.ball), "X", dtype="<U1")
            output[original] = raw[target]
            return output, {"rows": n, "official_length": full_size,
                            "csv_sha256": bundle.sha256(str(root / "prediction.csv")),
                            "runtime_warnings": len(seen)}


def source_identity():
    root = Path(__file__).resolve().parents[1]
    paths = [Path(__file__), root / "games.py", root / "heldout/bundle.py",
             root / "evaluation/possession_metrics.py"]
    paths += sorted((root / "solution/a_opus").glob("*.py"))
    digest = hashlib.sha256()
    for path in paths:
        digest.update(path.relative_to(root).as_posix().encode())
        digest.update(path.read_bytes())
    state = subprocess.run(["git", "rev-parse", "HEAD"], capture_output=True, text=True)
    dirty = subprocess.run(["git", "status", "--porcelain"], capture_output=True, text=True)
    return {"commit": state.stdout.strip() if state.returncode == 0 else None,
            "dirty": bool(dirty.stdout.strip()) if dirty.returncode == 0 else None,
            "source_sha256": digest.hexdigest(), "python": platform.python_version(),
            "numpy": np.__version__, "pandas": version("pandas"), "config_sha256": hashlib.sha256(
                json.dumps(a_config.build(), sort_keys=True).encode()).hexdigest()}


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--check", action="store_true")
    parser.add_argument("--full-size-smoke", action="store_true")
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("The report destination must be new")
    rows = []
    for base in scenarios():
        reference = None
        for mirror, offset, permute in ((False, 0, False), (True, 0, False), (False, 17, False), (False, 0, True)):
            case = transform(base, mirror, offset, permute)
            predicted, technical = run_a(case)
            row = assess(case, predicted)
            aligned = predicted[offset:]
            if mirror:
                aligned = np.where(aligned == "H", "A", np.where(aligned == "A", "H", aligned))
            if reference is None:
                reference = aligned.copy()
            row["equivariance_mismatches"] = int(np.sum(aligned != reference))
            row.update(technical)
            rows.append(row)
    smoke = None
    if args.full_size_smoke:
        _, smoke = run_a(scenarios()[0], full_size=True)
        _, repeated = run_a(scenarios()[0], full_size=True)
        smoke["repeat_sha256"] = repeated["csv_sha256"]
        smoke["deterministic"] = smoke["csv_sha256"] == repeated["csv_sha256"]
        if not smoke["deterministic"]:
            raise RuntimeError("Synthetic full-size prediction did not reproduce")
    counts = {status: sum(row["status"] == status for row in rows)
              for status in ("pass", "fail", "diagnostic")}
    counts["invariance_failures"] = sum(row["equivariance_mismatches"] > 0 for row in rows)
    report = {"fixture_version": VERSION, "scope": "public synthetic development only",
              "model": "candidate A unchanged; no improvement variant supplied",
              "identity": source_identity(), "counts": counts, "rows": rows,
              "full_size_smoke": smoke, "limitations": [
                  "Compact runs replace only the timeline and use the normal A pipeline with default calibration.",
                  "Small invented worlds do not establish real-match generalisation.",
                  "Diagnostic rows are not acceptance passes; no reserved or public challenge GT is read."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print("Candidate A synthetic development: " + json.dumps(counts, sort_keys=True))
    print("Report written; diagnostic rows require interpretation, not automatic adoption.")
    return 1 if args.check and (counts["fail"] or counts["invariance_failures"]) else 0


if __name__ == "__main__":
    raise SystemExit(main())
