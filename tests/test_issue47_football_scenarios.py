"""Issue #47 development fixtures and assertions; never opens match data.

Tests exercise observations, failure reporting and isolated football components.
Candidate A's geometry-to-output failures remain visible in the separate report:
python -m tools.football_acceptance --out <new-report> --check
"""
from dataclasses import replace
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

import games
from solution import temporal_control as tc
from solution.a_opus import config, decode
from tools import football_acceptance as fa


def decode_evidence(team):
    """Supplied evidence isolates A's unchanged decoder, not its feature extraction."""
    cfg = config.build()
    team = np.asarray(team, float)
    states = decode.viterbi(team / 2, -team / 2, np.full(len(team), -.1) + abs(team) / 2,
                            cfg["decode.lam_ha"], cfg["decode.lam_ad"],
                            cfg["decode.lam_da"], cfg["decode.min_dead"])
    return np.array(list("HAD"))[states]


class FootballFixtureTests(unittest.TestCase):
    def setUp(self):
        self.cases = fa.scenarios()

    def case(self, id):
        return next(case for case in self.cases if case.id == id)

    def test_all_ten_scenarios_have_observations_and_separate_targets(self):
        self.assertEqual({case.id for case in self.cases}, {"FA%02d" % n for n in range(1, 11)})
        for case in self.cases:
            with self.subTest(id=case.id, condition=case.condition):
                n = len(case.ball)
                self.assertEqual(case.players.shape, (n, 22, 3))
                self.assertEqual(case.period.shape, (n,))
                self.assertEqual(case.expected.shape, (n,))
                self.assertNotIn("expected", case.observations())
                self.assertTrue(np.all(np.isfinite(case.players)))
                self.assertTrue(np.all(np.isfinite(case.ball).all(axis=1)
                                       | np.isnan(case.ball).all(axis=1)))
                self.assertLessEqual(float(np.nanmax(case.players[:, :, 2])), 45.)
                for event in case.events:
                    self.assertTrue(0 <= event["start_frame"] < event["end_frame"] <= n)

    def test_reference_changes_cannot_change_observation_or_bundle_hash(self):
        case = self.case("FA01")
        changed = replace(case, expected=np.full(len(case.ball), "D"))
        self.assertEqual(fa.observation_hash(case), fa.observation_hash(changed))
        with tempfile.TemporaryDirectory() as first, tempfile.TemporaryDirectory() as second:
            with fa.synthetic_bundle(case, first), fa.synthetic_bundle(changed, second):
                for name in ("atd_meta", "atd_raw", "smart_tagging"):
                    a = games.asset_paths(data_dir=first)[name]
                    b = games.asset_paths(data_dir=second)[name]
                    self.assertEqual(Path(a).read_bytes(), Path(b).read_bytes())

    def test_corner_world_restarts_at_corner_with_plausible_ball_speed(self):
        case = next(c for c in self.cases if c.id == "FA06" and c.condition == "Corner Kick")
        self.assertTrue(np.all(case.ball[125] < 1.))
        speed = np.linalg.norm(np.diff(case.ball, axis=0), axis=1) * fa.FPS
        self.assertLess(float(speed.max()), 45.)

    def test_team_swap_and_slot_permutation_preserve_physical_world(self):
        case = self.case("FA01")
        swapped = fa.transform(case, mirror=True)
        np.testing.assert_array_equal(swapped.ball, case.ball)
        np.testing.assert_array_equal(swapped.players[:, :11], case.players[:, 11:])
        self.assertEqual("".join(swapped.expected), "A" * 50 + "H" * 30 + "A" * 50)
        restored = fa.transform(swapped, mirror=True)
        np.testing.assert_array_equal(restored.players, case.players)
        for team in (slice(0, 11), slice(11, 22)):
            np.testing.assert_array_equal(np.sort(fa.transform(case, permute=True).players[:, team, 0]),
                                          np.sort(case.players[:, team, 0]))

    def test_offset_is_unscored_and_events_move_without_target_leakage(self):
        case = self.case("FA08")
        shifted = fa.transform(case, offset=17)
        self.assertTrue(np.all(shifted.period[:17] == 0))
        self.assertTrue(np.all(shifted.expected[:17] == "X"))
        np.testing.assert_array_equal(shifted.ball[17:], case.ball)
        self.assertEqual(shifted.events[0]["start_frame"], case.events[0]["start_frame"] + 17)

    def test_classifier_keeps_short_recovery_and_deflection_distinct(self):
        case = self.case("FA01")
        self.assertEqual(fa.assess(case, case.expected)["status"], "pass")
        erased = np.full(len(case.ball), "H")
        self.assertEqual(fa.assess(case, erased)["status"], "fail")
        deflection = self.case("FA02")
        flicker = deflection.expected.copy()
        flicker[50:52] = "A"
        self.assertEqual(fa.assess(deflection, flicker)["status"], "fail")

    def test_abstention_or_false_dead_is_not_hidden_by_forward_filling(self):
        case = self.case("FA04")
        for label in ("X", "D"):
            predicted = case.expected.copy()
            predicted[50:100] = label
            row = fa.assess(case, predicted)
            self.assertEqual(row["status"], "fail")
            self.assertEqual(row["abstentions"] if label == "X" else row["false_dead_frames"], 50)

    def test_hidden_change_uses_observable_bracket_instead_of_exact_truth(self):
        case = self.case("FA05")
        for boundary in (50, 75, 100, 104):
            row = fa.assess(case, fa.labels(("H", boundary), ("A", 150 - boundary)))
            self.assertEqual(row["status"], "pass")
            self.assertIsNone(row["boundary_errors_frames"])
        for boundary in (40, 110):
            self.assertEqual(fa.assess(case, fa.labels(("H", boundary), ("A", 150 - boundary)))["status"], "fail")

    def test_boundary_latency_is_signed_and_same_team_stoppage_is_not_merged(self):
        case = self.case("FA06")
        shifted = fa.labels(("H", 51), ("D", 75), ("H", 49))
        row = fa.assess(case, shifted)
        self.assertEqual(row["status"], "fail")
        self.assertEqual(row["boundary_errors_frames"], [1, 1])
        self.assertEqual(row["boundary_errors_seconds"], [.04, .04])
        row = fa.assess(case, np.full(175, "H"))
        self.assertEqual(row["predicted_team_spells"], 1)
        self.assertEqual(row["expected_team_spells"], 2)
        self.assertEqual(row["restarts"][0]["missed"], 1)
        late = fa.labels(("H", 50), ("D", 101), ("H", 24))
        late_row = fa.assess(case, late)
        self.assertEqual(late_row["restarts"][0]["missed"], 1)
        self.assertEqual(late_row["restarts"][0]["spurious"], 1)

    def test_diagnostics_are_never_counted_as_acceptance_passes(self):
        for id in ("FA07", "FA08", "FA09", "FA10"):
            case = self.case(id)
            self.assertEqual(fa.assess(case, case.expected)["status"], "diagnostic")

    def test_equal_team_spells_on_either_side_of_halftime_stay_separate(self):
        case = self.case("FA09")
        same = case.expected.copy()
        same[125:] = "H"
        case = replace(case, expected=same)
        row = fa.assess(case, same)
        self.assertEqual(row["expected_team_spells"], 2)
        self.assertEqual(row["predicted_team_spells"], 2)

    def test_invalid_model_output_is_rejected(self):
        case = self.case("FA01")
        for output in (case.expected[:-1], np.full(130, "?")):
            with self.assertRaises(ValueError):
                fa.assess(case, output)


class FootballComponentTests(unittest.TestCase):
    def test_fa01_fa02_fa03_a_decoder_with_fixed_evidence_both_teams(self):
        for sign in (1, -1):
            with self.subTest(sign=sign):
                evidence = np.r_[np.full(50, .4), np.full(30, -.4), np.full(50, .4)] * sign
                expected = fa.labels(("H", 50), ("A", 30), ("H", 50))
                if sign == -1:
                    expected = np.where(expected == "H", "A", "H")
                np.testing.assert_array_equal(decode_evidence(evidence), expected)
                for middle in ((-1.9, -.4), np.zeros(40)):
                    path = decode_evidence(np.r_[np.full(50, .4), middle, np.full(50, .4)] * sign)
                    self.assertTrue(np.all(path == ("H" if sign == 1 else "A")))

    def test_fa04_fa05_neutral_gap_in_a_decoder(self):
        for sign in (1, -1):
            for other in (.4, -.4):
                path = decode_evidence(np.r_[np.full(50, .4), np.zeros(50), np.full(50, other)] * sign)
                self.assertTrue(np.all(path[:100] == ("H" if sign == 1 else "A")))
                self.assertEqual(path[-1], "H" if other * sign > 0 else "A")

    def test_fa06_p2_exit_restart_both_teams_and_permutations(self):
        for base in (case for case in fa.scenarios() if case.id == "FA06" and case.condition != "Free Kick"):
            for mirror in (False, True):
                case = fa.transform(base, mirror=mirror, permute=True)
                signals, candidates, _ = fa.p2_signals(case)
                exits = [c for c in candidates if c["evidence"] == "observed_exit"]
                self.assertTrue(exits)
                self.assertEqual(exits[0]["start_frame"], 50)
                self.assertEqual(exits[0]["restart_frame"], 125)
                self.assertTrue(np.all(signals["dead_score"][50:125] >= .75))

    def test_fa07_p2_dates_supported_motion_not_confirmation_end(self):
        for case in (case for case in fa.scenarios() if case.id == "FA07"):
            signals, candidates, _ = fa.p2_signals(case)
            starts = [c["restart_frame"] for c in candidates if c["evidence"] == "tagged_preparation"]
            self.assertTrue(starts)
            r = starts[0]
            self.assertGreaterEqual(signals["restart_score"][r], .75)
            # The fixture's physical onset and a threshold-confirmed movement
            # need not coincide. Their difference is retained in the report.
            self.assertNotEqual(r, 75)

    def test_fa08_shifted_tags_and_unrelated_motion(self):
        for base in (case for case in fa.scenarios() if case.id == "FA08"):
            for offset in (0, 17):
                case = fa.transform(base, offset=offset)
                signals, candidates, _ = fa.p2_signals(case)
                kickoffs = [c for c in candidates if c["evidence"] == "initial_kickoff_context"]
                self.assertEqual(len(kickoffs), 1)
                self.assertEqual(kickoffs[0]["period"], 2)
                self.assertEqual(kickoffs[0]["restart_frame"], 200 + offset)
                self.assertTrue(np.all(signals["dead_score"][125 + offset:200 + offset] >= .75))

    def test_fa09_reset_and_speed_do_not_cross_halves_with_calibration_fixed(self):
        for base in (case for case in fa.scenarios() if case.id == "FA09"):
            distances = np.tile([.2, 6.], (225, 1))
            distances[125:] = [6., .2] if base.condition == "control" else [np.nan, np.nan]
            distances[100:125] = np.nan
            parameters = dict(tc.DEFAULTS, p2_enabled=False)
            first, _ = tc.predict(distances, base.ball, np.isfinite(base.ball).all(axis=1),
                                   base.period, fa.FPS, {}, parameters)
            changed = distances.copy()
            changed[:100] = [6., .2]
            second, _ = tc.predict(changed, base.ball, np.isfinite(base.ball).all(axis=1),
                                    base.period, fa.FPS, {}, parameters)
            np.testing.assert_array_equal(first[125:], second[125:])
            self.assertTrue(np.all(first[100:125] == "X"))
            self.assertEqual(first[-1], "A" if base.condition == "control" else "X")
            speed = tc.ball_speed(base.ball, np.isfinite(base.ball).all(axis=1), base.period, fa.FPS)
            self.assertTrue(np.isnan(speed[125]))

    def test_fa10_unknown_restart_preserves_invalid_evidence(self):
        for case in (case for case in fa.scenarios() if case.id == "FA10"):
            signals, candidates, _ = fa.p2_signals(case)
            self.assertFalse(signals["restart_valid"].any())
            if case.events:
                self.assertTrue(np.all(signals["dead_score"][:25] >= .75))
                self.assertFalse(signals["dead_valid"][25:].any())
                self.assertIsNone(candidates[0]["restart_frame"])
            else:
                self.assertFalse(signals["dead_valid"].any())


class GeometryToOutputTests(unittest.TestCase):
    def test_a_runs_normal_pipeline_and_is_deterministic_without_match_assets(self):
        case = fa.scenarios()[0]
        # Any accidental fallback to the real data root fails immediately.
        real_require = games.require

        def require(names, game=games.GAME, data_dir=None, source=games.DEFAULT_SOURCE):
            self.assertIsNotNone(data_dir)
            self.assertIn("issue47-invented-", str(data_dir))
            return real_require(names, game, data_dir, source)

        with patch.object(games, "require", side_effect=require):
            first, a = fa.run_a(case)
            second, b = fa.run_a(case)
        np.testing.assert_array_equal(first, second)
        self.assertEqual(a["csv_sha256"], b["csv_sha256"])
        self.assertLess(a["rows"], games.source_frames())
        self.assertFalse(a["official_length"])
        self.assertIn(fa.assess(case, first)["status"], ("pass", "fail"))


if __name__ == "__main__":
    unittest.main()
