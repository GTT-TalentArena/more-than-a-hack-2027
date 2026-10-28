"""Verify synthetic review evidence without treating it as real-match validation."""
import unittest

import numpy as np

from tools import football_acceptance as fa
from tools import football_rule_review as review


class FootballRuleReviewTests(unittest.TestCase):
    def test_decoder_probe_explains_zero_dead_evidence_without_changing_a(self):
        zero, negative = review.neutral_dead_probe()
        self.assertEqual(zero["predicted_runs"], [("D", 0, 130)])
        self.assertGreater(zero["decoded_score"], zero["reference_live_score"])
        self.assertEqual(negative["predicted_runs"], [("H", 0, 50), ("A", 50, 80), ("H", 80, 130)])
        self.assertAlmostEqual(negative["decoded_score"], negative["reference_live_score"])

    def test_kickoff_probes_change_only_declared_observations_or_window(self):
        base = next(c for c in fa.scenarios() if c.id == "FA08" and c.condition == "tag-shift-+0")
        for case in review.kickoff_probes():
            np.testing.assert_array_equal(case.expected, base.expected)
            np.testing.assert_array_equal(case.players, base.players)
            np.testing.assert_array_equal(case.period, base.period)
            valid = np.isfinite(case.ball).all(axis=1)
            np.testing.assert_array_equal(case.ball[valid], base.ball[valid])
            self.assertNotEqual(fa.observation_hash(case), fa.observation_hash(base))

    def test_p2_unknown_and_late_boundaries_remain_explicit(self):
        results = {case.condition: review.p2_review(case) for case in review.kickoff_probes()}
        for name in ("window-ends-at-motion", "only-two-moving-frames", "missing-until-outside-centre-zone"):
            self.assertEqual(results[name]["confirmed_restarts"], [])
            self.assertIsNone(results[name]["initial_contexts"][0]["restart_frame"])
        self.assertEqual(results["missing-five-frames"]["nearest_errors_frames"], [5])

    def test_observing_a_preserves_normal_csv_and_exposes_separate_scores(self):
        case = fa.scenarios()[0]
        before = fa.observation_hash(case)
        result = review.trace_a(case)
        self.assertTrue(result["observer_preserved_csv"])
        self.assertEqual(fa.observation_hash(case), before)
        self.assertGreater(result["nonzero_team_evidence_live_frames"], 0)
        self.assertEqual(result["positive_dead_evidence_live_frames"], 0)
        self.assertTrue(all(part["positive"] == 0 for part in result["dead_terms_on_live_frames"].values()))


if __name__ == "__main__":
    unittest.main()
