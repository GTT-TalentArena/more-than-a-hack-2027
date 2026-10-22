"""P1 regression tests: all tracking fixtures are invented, never match extracts."""
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import games
from solution import hold
from solution.predict import load_config

ROOT = Path(__file__).resolve().parents[1]


def write_metadata(tactical, unknown_slot=False):
    tactical.mkdir(parents=True, exist_ok=True)
    xml = ('<root><Team id="h"><Name>Synthetic H</Name></Team>'
           '<Team id="a"><Name>Synthetic A</Name></Team>'
           '<Player teamId="h"/><Player teamId="a"/>')
    if unknown_slot:
        xml += '<Player teamId="unknown"/>'
    (tactical / "BAR-ATH_tactical_atd.xml").write_text(xml + "</root>", encoding="utf-8")


class HoldTests(unittest.TestCase):
    def apply(self, teams, limit=25, periods=None, valid=None):
        return hold.apply_hold(np.array(list(teams)),
                               np.array([t != "X" for t in teams]) if valid is None else valid,
                               np.ones(len(teams), dtype=np.int64) if periods is None else np.array(periods),
                               limit).tolist()

    def test_short_gaps_home_and_away(self):
        for team in ("H", "A"):
            self.assertEqual(self.apply(team + "XX" + team), [team] * 4)

    def test_exact_hold_boundary_24_25_26(self):
        for missing in (24, 25, 26):
            labels = self.apply("H" + "X" * missing)
            self.assertEqual(labels.count("H"), min(missing, 25) + 1)
            self.assertEqual(labels[-1], "H" if missing <= 25 else "X")

    def test_disabled_hold_and_initial_missing(self):
        self.assertEqual(self.apply("XHXXA", limit=0), list("XHXXA"))
        self.assertEqual(self.apply("XXHXX"), list("XXHHH"))

    def test_reappearance_changes_team_without_rewriting_gap(self):
        self.assertEqual(self.apply("HXXAX"), list("HHHAA"))

    def test_reset_between_periods_and_outside(self):
        self.assertEqual(self.apply("HXXAX", periods=[1, 1, 2, 2, 2]), list("HHXAA"))
        self.assertEqual(self.apply("HXXAX", periods=[1, 0, 1, 2, 2]), list("HXXAA"))

    def test_independent_dead_evidence_can_override_hold(self):
        self.assertEqual(self.apply("HXDXA"), list("HHDDA"))
        self.assertNotIn("D", self.apply("HXXXX", limit=2))

    def test_invalid_parameters_and_masks(self):
        for limit in (-1, True, 1.5):
            with self.assertRaises(ValueError):
                self.apply("H", limit=limit)
        with self.assertRaises(ValueError):
            self.apply("H", valid=np.array([1]))
        with self.assertRaises(ValueError):
            self.apply("Z", valid=np.array([True]))
        with self.assertRaises(ValueError):
            self.apply("H", periods=[1, 2])

    def test_period_mapping_inclusive_ends(self):
        np.testing.assert_array_equal(hold.make_period_id(8, [(1, 1, 2), (2, 5, 6)]), [0, 1, 1, 0, 0, 2, 2, 0])
        for blocks in ([(1, 1, 3), (2, 3, 5)], [(1, 1, 8)]):
            with self.assertRaises(ValueError):
                hold.make_period_id(8, blocks)

    def test_diagnostics_do_not_count_halftime_or_join_period_gaps(self):
        summary = hold.summarize_gaps(np.array([False, True, False, False, False, True]),
                                     np.array([False, True, False, False, False, True]),
                                     np.array([0, 1, 1, 0, 2, 2]), 25)
        self.assertEqual(summary["periods"]["1"]["ball_absent"]["frames"], 2)
        self.assertEqual(summary["periods"]["2"]["ball_absent"]["gap_count"], 1)
        self.assertEqual(summary["periods"]["1"]["ball_absent"]["max_gap_s"], 1 / 25)
        self.assertEqual(hold._gap_stats(np.array([], dtype=bool), 25)["gap_count"], 0)

    def test_loader_rejects_bad_positions_and_ignores_unknown_team(self):
        with tempfile.TemporaryDirectory() as directory:
            tactical = Path(directory) / "tactical"
            write_metadata(tactical, unknown_slot=True)
            (tactical / "BAR-ATH_tactical_atd.txt").write_text(
                "1:0.1,0.5,0;0.9,0.5,0;NaN:0.1,0.5,0\n"
                "2:0.1,0.5,0;0.9,0.5,0;NaN:NaN,NaN,0\n"
                "3:NaN;inf,0.5,0;0.1,0.5,0:0.1,0.5,0\n"
                "4:NaN;0.9,0.5,0;0.1,0.5,0:0.1,0.5,0\n"
                "5:0.1,0.5,0;0.9,0.5,0;NaN:0.1,inf,0\n", encoding="utf-8")
            with patch.object(games, "source_frames", return_value=5):
                teams, ball_observed, observation_valid = hold.load_observations(directory)
            self.assertEqual(teams.tolist(), list("HXXAX"))
            self.assertEqual(ball_observed.tolist(), [True, False, True, True, False])
            self.assertEqual(observation_valid.tolist(), [True, False, False, True, False])

    def test_hold_config_and_validation(self):
        config = load_config(ROOT / "configs/baseline_hold.json")
        self.assertEqual(config["parameters"]["max_hold_frames"], 25)
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            for parameters in ({"max_hold_frames": -1}, {"max_hold_frames": True}, {"window": 25}):
                config["parameters"] = parameters
                path.write_text(json.dumps(config), encoding="utf-8")
                with self.assertRaises(ValueError):
                    load_config(path)

    def test_pipeline_end_to_end_with_synthetic_gaps(self):
        with tempfile.TemporaryDirectory() as directory:
            tactical = Path(directory) / "tactical"
            write_metadata(tactical)
            first_play_frame = games.half_video_blocks(games.GAME)[0][1]
            with (tactical / "BAR-ATH_tactical_atd.txt").open("w", encoding="utf-8") as handle:
                for frame in range(games.source_frames()):
                    ball = "NaN,NaN,0"
                    if frame == first_play_frame:
                        ball = "0.1,0.5,0"
                    elif frame == first_play_frame + 30:
                        ball = "0.9,0.5,0"
                    handle.write(f"{frame + 1}:0.1,0.5,0;0.9,0.5,0:{ball}\n")
            env = dict(os.environ, GTT_SALIDAS=str(Path(directory) / "outputs"),
                       PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([sys.executable, "docker/pipeline.py", "modelo", "--config",
                                     "configs/baseline_hold.json", "--data-dir", directory, "--repetir"],
                                    cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record_path = next((Path(directory) / "outputs").glob("*/run.json"))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertTrue(record["determinista"])
            self.assertEqual(record["modelo"], "baseline_hold")
            self.assertEqual(len(record["inputs"]), 2)
            self.assertEqual(record["diagnostics"]["retained_frames"], 50)
            candidate = next(e for e in record["csv"] if e["nombre"] == "candidato")
            self.assertTrue(candidate["valido"])
            self.assertIn("fragmentacion", candidate["metricas"])
            import pandas as pd
            labels = pd.read_csv(record_path.parent / "results/candidato.csv")["label"]
            self.assertEqual(labels[first_play_frame + 25], "H")
            self.assertEqual(labels[first_play_frame + 26], "X")
            self.assertEqual(labels[first_play_frame + 30], "A")
            self.assertEqual(labels[games.half_video_blocks(games.GAME)[1][1]], "X")


if __name__ == "__main__":
    unittest.main()
