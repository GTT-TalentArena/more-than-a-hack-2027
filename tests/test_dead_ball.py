"""Synthetic P2 fixtures; no match extracts."""
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
from solution import dead_ball as db
from solution.predict import load_config

ROOT = Path(__file__).resolve().parents[1]


def event(start, end, kind="Free Kick", team="Barcelona"):
    return dict(code=" SET   PIECES ", start_frame=start, end_frame=end,
                tags={"Type": kind, "Team": team})


class DeadBallTests(unittest.TestCase):
    def detect(self, xy, events=(), periods=None, quiet=True, **parameters):
        xy = np.asarray(xy, dtype=float)
        n = len(xy)
        return db.detect(xy, np.all(np.isfinite(xy), axis=1),
                         np.ones(n, dtype=np.int64) if periods is None else np.asarray(periods),
                         events, 10, (100, 60), np.zeros(n) if quiet else None,
                         np.full(n, 22) if quiet else None, parameters)

    def preparation(self):
        return [[50, 30]] * 8 + [[50 + 0.3 * i, 30] for i in range(1, 10)]

    def test_absence_and_quiet_players_do_not_infer_dead(self):
        signals, candidates, _ = self.detect([[np.nan, np.nan]] * 30)
        self.assertFalse(signals["dead_valid"].any())
        self.assertFalse(signals["restart_valid"].any())
        self.assertEqual(candidates, [])

    def test_stationary_ball_without_event_is_unknown(self):
        signals, _, _ = self.detect([[50, 30]] * 30)
        self.assertFalse(signals["dead_valid"].any())

    def test_tag_window_is_not_entire_dead_period_and_end_is_exclusive(self):
        signals, candidates, _ = self.detect(self.preparation(), [event(0, 17)])
        self.assertTrue(np.all(signals["dead_score"][1:8] >= 0.75))
        self.assertEqual(signals["dead_score"][8], 0)
        self.assertGreaterEqual(signals["restart_score"][8], 0.75)
        self.assertEqual(candidates[0]["end_frame"], 8)
        signals, candidates, _ = self.detect(self.preparation(), [event(0, 10)])
        self.assertEqual(candidates, [])  # Third confirming motion frame is outside [0,10).

    def test_without_collective_support_preparation_is_weak(self):
        signals, _, _ = self.detect(self.preparation(), [event(0, 17)], quiet=False)
        self.assertEqual(signals["dead_score"][1], 0.6)

    def test_kickoff_covers_preparation_from_period_start(self):
        xy = [[np.nan, np.nan]] * 10 + self.preparation()
        signals, candidates, _ = self.detect(xy, [event(10, 27, "Kick Off (Start)")])
        self.assertTrue(np.all(signals["dead_score"][:18] >= 0.75))
        self.assertEqual(candidates[0]["restart_frame"], 18)

    def test_confirmed_kickoff_is_not_cut_by_unpaired_exit_timeout(self):
        xy = [[np.nan, np.nan]] * 10 + self.preparation()
        signals, _, _ = self.detect(xy, [event(10, 27, "Kick Off (Start)")], max_dead_s=1)
        self.assertTrue(np.all(signals["dead_score"][:18] >= 0.75))

    def test_kickoff_does_not_release_on_earlier_unrelated_movement(self):
        xy = [[10 + 0.3 * i, 20] for i in range(10)] + self.preparation()
        signals, _, _ = self.detect(xy, [event(10, 27, "Kick Off (Start)")])
        self.assertTrue(np.all(signals["dead_score"][:18] >= 0.75))

    def test_kickoff_requires_center(self):
        xy = np.asarray(self.preparation()) - [20, 0]
        _, candidates, _ = self.detect(xy, [event(0, 17, "Kick Off (Start)")])
        self.assertEqual(candidates, [])

    def test_initial_context_without_ball_does_not_label_entire_tag_window_dead(self):
        signals, candidates, _ = self.detect([[np.nan, np.nan]] * 30,
                                             [event(20, 30, "Kick Off (Start)")])
        self.assertTrue(np.all(signals["dead_score"][:20] >= .75))
        self.assertTrue(np.all(np.isnan(signals["dead_score"][20:])))
        self.assertIsNone(candidates[0]["restart_frame"])

    def test_initial_restart_does_not_require_observed_stationarity(self):
        xy = [[np.nan, np.nan]] * 10 + [[50 + .3 * i, 30] for i in range(10)]
        signals, candidates, _ = self.detect(xy, [event(10, 20, "Kick Off (Start)")])
        self.assertEqual(candidates[0]["restart_frame"], 11)
        self.assertGreaterEqual(signals["restart_score"][11], .75)

    def test_first_initial_tag_is_chronological_even_if_file_order_differs(self):
        _, candidates, _ = self.detect([[np.nan, np.nan]] * 30,
            [event(20, 30, "Kick Off (Start)"), event(10, 15, "Kick Off (Start)")])
        self.assertEqual(len(candidates), 1)
        self.assertEqual(candidates[0]["end_frame"], 10)

    def test_exit_and_reentry_same_team_can_separate_possessions(self):
        xy = [[50, -1]] * 5 + [[50, 0.3 * i] for i in range(8)]
        signals, candidates, _ = self.detect(xy)
        self.assertTrue(np.all(signals["dead_score"][:5] >= 0.75))
        self.assertGreaterEqual(signals["restart_score"][5], 0.75)
        self.assertEqual(candidates[0]["start_frame"], 0)

    def test_short_outlier_does_not_infer_exit(self):
        xy = [[50, 30]] * 5 + [[50, -1]] + [[50, 30]] * 5
        signals, candidates, _ = self.detect(xy)
        self.assertFalse(np.any(signals["dead_score"] >= 0.75))
        self.assertEqual(candidates, [])

    def test_no_speed_across_missing_ball_or_periods(self):
        xy = [[50, 30]] * 8 + [[np.nan, np.nan]] + [[51, 30]] * 5
        signals, candidates, _ = self.detect(xy, [event(0, 14)])
        self.assertEqual(candidates, [])
        self.assertFalse(signals["restart_valid"][9])
        signals, _, _ = self.detect([[50, -1]] * 4 + [[50, 1]] * 4,
                                     periods=[1] * 4 + [2] * 4)
        self.assertTrue(np.all(np.isnan(signals["dead_score"][4:])))

    def test_exit_evidence_expires_instead_of_infinite_dead_hold(self):
        xy = [[50, -1]] * 3 + [[np.nan, np.nan]] * 20
        signals, _, _ = self.detect(xy, max_dead_s=1)
        self.assertTrue(np.all(signals["dead_score"][:10] >= 0.75))
        self.assertTrue(np.all(np.isnan(signals["dead_score"][10:])))

    def test_overlap_and_unknown_team_keep_evidence_and_conflict_information(self):
        signals, candidates, summary = self.detect(self.preparation(),
            [event(0, 17, team="N/A"), event(0, 17, team="Atletic Club")])
        self.assertEqual(summary["unknown_teams"], 1)
        self.assertEqual(summary["overlap_frames"], 17)
        self.assertIsNone(candidates[0]["team"])
        self.assertEqual(candidates[1]["team"], "A")
        self.assertLessEqual(np.nanmax(signals["dead_score"]), 1)

    def test_invalid_masks_intervals_and_parameters(self):
        with self.assertRaises(ValueError):
            self.detect(self.preparation(), [event(0, 18)])
        with self.assertRaises(ValueError):
            self.detect(self.preparation(), moving_frames=True)
        with self.assertRaises(ValueError):
            db.detect(np.zeros((3, 2)), np.zeros(3, dtype=bool), np.ones(3, dtype=int), [], 10, (100, 60))

    def test_configs_differ_only_in_enabled_and_disabled_is_exact_p1(self):
        on = load_config(ROOT / "configs/baseline_dead_ball.json")
        off = load_config(ROOT / "configs/baseline_dead_ball_disabled.json")
        on["parameters"]["enabled"] = False
        self.assertEqual(on, off)
        with patch.object(db, "load_observations", return_value=(np.array(list("HXXA")), np.array([1, 0, 0, 1], bool), np.array([1, 0, 0, 1], bool))), patch.object(games, "half_video_blocks", return_value=[(1, 0, 3)]):
            labels, _ = db.build("unused", off["parameters"])
        self.assertEqual(labels.tolist(), list("HHHA"))

    def test_real_loader_with_fully_synthetic_files(self):
        with tempfile.TemporaryDirectory() as directory:
            tactical = Path(directory) / "tactical"
            tactical.mkdir()
            (tactical / "BAR-ATH_tactical_atd.txt").write_text(
                "1:0.1,0.2,1;NaN:0.5,0.5,0\n2:0.1,0.2,NaN;0.3,0.4,2:NaN\n", encoding="utf-8")
            with patch.object(games, "source_frames", return_value=2):
                ball, observed, speed, counts = db.load_geometry(directory)
            self.assertEqual(observed.tolist(), [True, False])
            self.assertEqual(counts.tolist(), [1, 1])
            np.testing.assert_array_equal(speed, [1, 2])
            np.testing.assert_allclose(ball[0], np.asarray(games.GAMES[games.GAME]["pitch"]) / 2)

    def test_restart_clears_retained_dead_when_team_unknown(self):
        parameters = dict(db.DEFAULTS, enabled=True, max_hold_frames=25)
        signals = dict(dead_score=np.array([.9, .9, 0., np.nan]), dead_valid=np.array([1, 1, 1, 0], bool),
                       restart_score=np.array([0., 0., .9, 0.]), restart_valid=np.ones(4, bool))
        with patch.object(db, "load_observations", return_value=(np.array(list("HXXX")), np.array([1, 0, 0, 0], bool), np.array([1, 0, 0, 0], bool))), patch.object(games, "half_video_blocks", return_value=[(1, 0, 3)]), patch.object(db, "load_geometry", return_value=(None, None, None, None)), patch.object(db, "load_events", return_value=[]), patch.object(db, "detect", return_value=(signals, [], {})):
            labels, _ = db.build("unused", parameters)
        self.assertEqual(labels.tolist(), list("DDXX"))

    def test_pipeline_end_to_end_full_synthetic_submission(self):
        with tempfile.TemporaryDirectory() as directory:
            tactical = Path(directory) / "tactical"
            tactical.mkdir()
            (tactical / "BAR-ATH_tactical_atd.xml").write_text(
                '<root><Team id="h"/><Team id="a"/><Player teamId="h"/><Player teamId="a"/></root>', encoding="utf-8")
            first = games.half_video_blocks(games.GAME)[0][1]
            fps = games.GAMES[games.GAME]["fps"]
            (tactical / "BAR-ATH_tactical_smart_tagging.xml").write_text(
                '<root><instance><start>{}</start><end>{}</end><code>SET PIECES</code>'
                '<label><group>Type</group><text>Kick Off (Start)</text></label></instance></root>'.format(first / fps, (first + 30) / fps), encoding="utf-8")
            with (tactical / "BAR-ATH_tactical_atd.txt").open("w", encoding="utf-8") as handle:
                for frame in range(games.source_frames()):
                    ball = "NaN"
                    if first <= frame < first + 30:
                        x = 0.5 if frame < first + 10 else 0.5 + (frame - first - 9) * .002
                        ball = f"{x},0.5,0"
                    handle.write(f"{frame + 1}:0.5,0.5,0;0.9,0.5,0:{ball}\n")
            env = dict(os.environ, GTT_SALIDAS=str(Path(directory) / "outputs"), PYTHONUTF8="1",
                       PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
            result = subprocess.run([sys.executable, "docker/pipeline.py", "modelo", "--config",
                "configs/baseline_dead_ball.json", "--data-dir", directory, "--repetir"],
                cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record_path = next((Path(directory) / "outputs").glob("*/run.json"))
            record = json.loads(record_path.read_text(encoding="utf-8"))
            self.assertTrue(record["determinista"])
            self.assertEqual(len(record["inputs"]), 3)
            candidate = next(e for e in record["csv"] if e["nombre"] == "candidato")
            self.assertTrue(candidate["valido"])
            self.assertGreater(record["diagnostics"]["dead_label_frames"], 0)


if __name__ == "__main__":
    unittest.main()
