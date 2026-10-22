"""Invented fixtures only; no match observations or labels."""
import itertools
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
from solution import temporal_control as tc
from solution.predict import load_config

ROOT = Path(__file__).resolve().parents[1]


def parameters(**changes):
    return dict(tc.DEFAULTS, p2_enabled=False, **changes)


def signal_fixture(n):
    return {key: np.zeros(n, dtype=bool) if key.endswith("valid") else np.full(n, np.nan)
            for key in ("dead_score", "dead_valid", "restart_score", "restart_valid")}


class TemporalControlTests(unittest.TestCase):
    def predict(self, distances, periods=None, signals=None, **changes):
        n = len(distances)
        p = dict(tc.DEFAULTS, p2_enabled=signals is not None)
        p.update(changes)
        return tc.predict(np.asarray(distances, float), np.tile([50., 30.], (n, 1)),
                          np.ones(n, dtype=bool), np.ones(n, dtype=int) if periods is None else periods,
                          25, {} if signals is None else signals, p)

    def test_decoder_matches_exhaustive_optimum(self):
        rng = np.random.default_rng(42)
        for _ in range(40):
            emissions = rng.normal(size=(6, 3))
            cost = float(rng.uniform(0, 3))
            if rng.random() < .5:
                emissions[3, 2] = -np.inf
            def score(states):
                return sum(emissions[t, s] for t, s in enumerate(states)) - cost * sum(
                    states[t] != states[t - 1] for t in range(1, len(states)))
            states = tc.decode(emissions, cost)
            best = max(score(path) for path in itertools.product(range(3), repeat=6))
            self.assertAlmostEqual(score(states), best)

    def test_gap_tie_keeps_previous_owner_until_new_evidence(self):
        emissions = np.zeros((50, 3))
        emissions[:, 2] = -2
        emissions[:20, 0] = 1
        emissions[30:, 1] = 1
        states = tc.decode(emissions, 8)
        np.testing.assert_array_equal(states[:30], 0)
        np.testing.assert_array_equal(states[30:], 1)

    def test_confirmation_is_backdated_but_not_across_a_gap(self):
        d = np.tile([.3, 5.], (14, 1))
        speed = np.zeros(14)
        speed[3] = np.nan
        evidence = tc.control_evidence(d, speed, np.ones(14, int), parameters())
        self.assertFalse(evidence[:4].any())
        self.assertTrue(np.all(evidence[4:, 0] == 1))
        evidence = tc.control_evidence(d[:5], np.zeros(5), np.ones(5, int), parameters())
        self.assertTrue(np.all(evidence[:, 0] == 1))

    def test_transient_control_is_removed_but_sustained_short_possession_survives(self):
        d = [[.2, 6.]] * 40 + [[6., .2]] * 6 + [[.2, 6.]] * 40
        labels, _ = self.predict(d)
        self.assertFalse(np.any(labels == "A"))
        d = [[.2, 6.]] * 40 + [[6., .2]] * 25 + [[.2, 6.]] * 40
        labels, _ = self.predict(d)
        self.assertTrue(np.all(labels[40:65] == "A"))
        self.assertEqual(labels[39], "H")
        self.assertEqual(labels[65], "H")

    def test_fast_pass_and_ambiguous_duel_do_not_confirm_control(self):
        d = np.tile([.2, 5.], (20, 1))
        p = parameters()
        self.assertFalse(tc.control_evidence(d, np.full(20, 12.), np.ones(20, int), p).any())
        self.assertFalse(tc.control_evidence(np.tile([.2, .3], (20, 1)), np.zeros(20), np.ones(20, int), p).any())

    def test_missing_ball_does_not_create_dead_and_no_observation_abstains(self):
        n = 80
        d = np.tile([.2, 5.], (n, 1))
        ball = np.tile([50., 30.], (n, 1))
        observed = np.ones(n, bool)
        observed[30:60] = False
        ball[~observed] = np.nan
        d[~observed] = np.nan
        labels, _ = tc.predict(d, ball, observed, np.ones(n, int), 25, {}, parameters())
        self.assertTrue(np.all(labels[30:60] == "H"))
        self.assertFalse(np.any(labels == "D"))
        labels, _ = tc.predict(np.full((n, 2), np.nan), np.full((n, 2), np.nan),
                              np.zeros(n, bool), np.ones(n, int), 25, {}, parameters())
        self.assertTrue(np.all(labels == "X"))

    def test_speed_does_not_cross_missing_observations_or_halftime(self):
        ball = np.array([[0., 0.], [1., 0.], [np.nan, np.nan], [10., 0.], [20., 0.]])
        observed = np.array([1, 1, 0, 1, 1], bool)
        speed = tc.ball_speed(ball, observed, np.array([1, 1, 0, 2, 3]), 25)
        self.assertEqual(speed[1], 25)
        self.assertTrue(np.all(np.isnan(speed[[0, 2, 3, 4]])))

    def test_same_team_stoppage_and_explicit_restart(self):
        signals = signal_fixture(100)
        signals["dead_score"][30:60] = .9
        signals["dead_valid"][30:60] = True
        signals["restart_score"][60] = .9
        signals["restart_valid"][60] = True
        labels, _ = self.predict([[.2, 5.]] * 100, signals=signals)
        self.assertTrue(np.all(labels[30:60] == "D"))
        self.assertEqual(labels[29], "H")
        self.assertEqual(labels[60], "H")

    def test_periods_reset_and_never_confirm_across_boundary(self):
        labels, _ = self.predict([[.2, 5.]] * 30 + [[np.nan, np.nan]] * 30,
                                 periods=np.r_[np.ones(30, int), np.full(30, 2, int)])
        self.assertTrue(np.all(labels[30:] == "X"))
        evidence = tc.control_evidence(np.tile([.2, 5.], (6, 1)), np.zeros(6),
                                       np.array([1, 1, 1, 2, 2, 2]), parameters())
        self.assertFalse(evidence.any())

    def test_invalid_parameters_geometry_and_scores(self):
        for change in ({"switch_cost": -1}, {"confirmation_frames": True},
                       {"control_radius_m": float("nan")}, {"unknown": 1}, {"p2_enabled": 1}):
            p = parameters()
            p.update(change)
            with self.assertRaises(ValueError):
                tc.validate_parameters(p)
        with self.assertRaises(ValueError):
            tc.decode(np.full((2, 3), -np.inf), 8)
        with self.assertRaises(ValueError):
            tc.validate_periods(np.array([1, 0, 1]))
        signals = signal_fixture(20)
        signals["dead_score"][0] = 0
        with self.assertRaises(ValueError):
            self.predict([[.2, 5.]] * 20, signals=signals)

    def test_streaming_loader_synthetic_known_unknown_slots(self):
        with tempfile.TemporaryDirectory() as directory:
            tactical = Path(directory) / "tactical"
            tactical.mkdir()
            (tactical / "BAR-ATH_tactical_atd.xml").write_text(
                '<root><Team id="h"/><Team id="a"/><Player teamId="h"/>'
                '<Player teamId="a"/><Player teamId="?"/></root>', encoding="utf-8")
            raw = tactical / "BAR-ATH_tactical_atd.txt"
            raw.write_text('1:0.1,0.5,1;0.9,0.5,2;0.5,0.5,0:0.5,0.5,0\n'
                           '2:NaN;0.9,0.5,2;0.1,0.5,0:0.1,0.5,0\n', encoding="utf-8")
            with patch.object(games, "source_frames", return_value=2):
                distances, _, observed, _, counts = tc.load_features(directory)
            np.testing.assert_allclose(distances[0], [42.12, 42.12])
            self.assertTrue(np.isnan(distances[1, 0]))
            self.assertTrue(observed.all())
            np.testing.assert_array_equal(counts, [3, 2])
            raw.write_text('1:0.1,0.5,1:NaN\n', encoding="utf-8")
            with patch.object(games, "source_frames", return_value=1), self.assertRaises(ValueError):
                tc.load_features(directory)

    def test_configs_and_complete_pipeline_with_synthetic_tracking(self):
        on = load_config(ROOT / "configs/temporal_control.json")
        off = load_config(ROOT / "configs/temporal_control_no_p2.json")
        on["parameters"]["p2_enabled"] = False
        self.assertEqual(on, off)
        with tempfile.TemporaryDirectory() as directory:
            tactical = Path(directory) / "tactical"
            tactical.mkdir()
            (tactical / "BAR-ATH_tactical_atd.xml").write_text(
                '<root><Team id="h"/><Team id="a"/><Player teamId="h"/><Player teamId="a"/></root>', encoding="utf-8")
            (tactical / "BAR-ATH_tactical_smart_tagging.xml").write_text('<root/>', encoding="utf-8")
            first = games.half_video_blocks(games.GAME)[0][1]
            with (tactical / "BAR-ATH_tactical_atd.txt").open('w', encoding="utf-8") as handle:
                for frame in range(games.source_frames()):
                    ball = '0.1,0.5,0' if first <= frame < first + 40 else 'NaN'
                    handle.write(f'{frame + 1}:0.1,0.5,0;0.9,0.5,0:{ball}\n')
            config = load_config(ROOT / "configs/temporal_control.json")
            config["evaluation"]["bootstrap"] = 0
            path = Path(directory) / 'config.json'
            path.write_text(json.dumps(config), encoding="utf-8")
            env = dict(os.environ, GTT_SALIDAS=str(Path(directory) / "outputs"),
                       PYTHONDONTWRITEBYTECODE="1", PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            result = subprocess.run([sys.executable, 'docker/pipeline.py', 'modelo', '--config', str(path),
                '--data-dir', directory, '--repetir'], cwd=ROOT, env=env, capture_output=True, text=True, encoding="utf-8")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = json.loads(next((Path(directory) / 'outputs').glob('*/run.json')).read_text(encoding="utf-8"))
            self.assertTrue(record['determinista'])
            self.assertEqual(len(record['inputs']), 3)
            self.assertIn('solution/temporal_control.py', record['model_sources'])
            self.assertGreater(record['diagnostics']['control_evidence_frames'], 0)
            self.assertTrue(next(e for e in record['csv'] if e['nombre'] == 'candidato')['valido'])


if __name__ == '__main__':
    unittest.main()
