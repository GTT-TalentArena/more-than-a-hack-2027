"""Issue #20: invented phase tags, observations and interval contracts only."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from solution.a_opus import config, evidence, pipeline, tags
from solution.a_opus.atd import HOME, AWAY
from starter import load_smart_tagging


def phase(code="build up", side=HOME, start=10, end=20):
    return dict(code=code, side=side, start=start, end=end, type="")


def calibration(*codes, reliability=1.):
    return {code: dict(polarity=tags.prior_polarity(code), reliability=reliability)
            for code in codes}


def context(n=200, first=0, home=True):
    return dict(n=n, first=first, confident=np.ones(n, bool),
                c_home=np.full(n, 1. if home else 0.),
                c_away=np.full(n, 0. if home else 1.))


class PhaseLoadingTests(unittest.TestCase):
    def test_case_and_team_normalisation_preserves_tactical_half_open_frames(self):
        xml = '''<file><ALL_INSTANCES><instance><code>  BuIlD Up  </code>
          <start>0.4</start><end>0.8</end>
          <label><group> TEAM </group><text> fc BARCELONA </text></label>
          </instance></ALL_INSTANCES></file>'''
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invented.xml"
            path.write_text(xml, encoding="utf-8")
            with patch.object(load_smart_tagging, "pattern_path", return_value=str(path)):
                loaded, note = tags.load("BAR-ATH", directory, ("FC Barcelona", "Athletic Club"))
        self.assertIsNone(note)
        self.assertEqual(loaded, [phase(start=10, end=20)])
        got = evidence.tag_team_llr(context(n=30), loaded, calibration("build up"), config.build())
        np.testing.assert_array_equal(np.flatnonzero(got), np.arange(10, 20))

    def test_missing_file_returns_no_tags_and_an_explicit_note(self):
        with patch.object(load_smart_tagging, "load", side_effect=FileNotFoundError("invented missing file")):
            loaded, note = tags.load("BAR-ATH", "unused", ("Home", "Away"))
        self.assertEqual(loaded, [])
        self.assertIn("not used", note)

    def test_empty_file_has_no_phase_evidence(self):
        with patch.object(load_smart_tagging, "load", return_value=[]):
            loaded, note = tags.load("BAR-ATH", "unused", ("Home", "Away"))
        self.assertEqual(loaded, [])
        self.assertIsNone(note)
        np.testing.assert_array_equal(evidence.tag_team_llr(context(), loaded, {}, config.build()), 0.)

    def test_missing_unknown_and_unavailable_team_do_not_choose_a_side(self):
        for name in (None, "", " N/A ", "NA", "none", "unrecognised team"):
            with self.subTest(name=name):
                self.assertIsNone(tags.side_of(name, ("FC Barcelona", "Athletic Club")))
        self.assertEqual(tags.side_of("ATLETIC CLUB", ("FC Barcelona", "Athletic Club")), AWAY)

    def test_phase_dictionary_separates_defending_from_restarts(self):
        self.assertEqual(tags.prior_polarity("attacking transition"), 1)
        self.assertEqual(tags.prior_polarity("defensive transition"), -1)
        for code in ("set pieces", "unknown phase", ""):
            self.assertEqual(tags.prior_polarity(code), 0)


class PhaseEvidenceTests(unittest.TestCase):
    def setUp(self):
        self.cfg = config.build()
        self.ctx = context(n=40)

    def signal(self, events, calibrated=None):
        if calibrated is None:
            calibrated = calibration(*(event["code"] for event in events))
        return evidence.tag_team_llr(self.ctx, events, calibrated, self.cfg)

    def test_attacking_and_defending_phases_name_the_correct_team(self):
        self.assertGreater(self.signal([phase()])[10], 0)
        self.assertLess(self.signal([phase(side=AWAY)])[10], 0)
        self.assertLess(self.signal([phase("defensive transition")])[10], 0)
        self.assertGreater(self.signal([phase("defensive transition", side=AWAY)])[10], 0)

    def test_identical_attacking_defending_pair_is_not_counted_twice(self):
        single = self.signal([phase()])
        paired = self.signal([phase(), phase("defending in middle third", side=AWAY)])
        np.testing.assert_array_equal(single, paired)

    def test_duplicate_support_uses_the_most_reliable_code(self):
        events = [phase(), phase("progression")]
        calibrated = calibration("build up", reliability=.2)
        calibrated.update(calibration("progression", reliability=.7))
        self.assertAlmostEqual(self.signal(events, calibrated)[10], .7 * self.cfg["tag.beta"])

    def test_equal_opposing_phases_cancel_and_unknown_sides_stay_neutral(self):
        np.testing.assert_array_equal(self.signal([phase(), phase(side=AWAY)]), 0.)
        np.testing.assert_array_equal(self.signal([phase(side=None)]), 0.)

    def test_partially_overlapping_opposing_phases_cancel_only_the_overlap(self):
        got = self.signal([phase(start=5, end=20), phase(side=AWAY, start=15, end=30)])
        self.assertTrue(np.all(got[5:15] > 0))
        self.assertTrue(np.all(got[15:20] == 0))
        self.assertTrue(np.all(got[20:30] < 0))

    def test_many_distinct_overlaps_remain_bounded_below_clear_control(self):
        got = self.signal([phase(start=index, end=35) for index in range(10)])
        self.assertLessEqual(float(np.max(np.abs(got))), self.cfg["tag.max_per_frame"])
        observed = dict(self.ctx, obs=np.ones(40, bool), isolated=np.zeros(40, bool),
                        interp=np.zeros(40, bool), gap=np.zeros(40))
        observed["weight"] = evidence.proximity_weight(observed, self.cfg)
        control = evidence.proximity_llr(observed, self.cfg, np.ones(40), np.zeros(40))
        opposing = self.signal([phase(side=AWAY, start=index, end=35) for index in range(10)])
        self.assertTrue(np.all(control + opposing > 0.))
        # This is a per-frame bound; it is not a guarantee about the Viterbi path.

    def test_intervals_clip_to_each_half_without_offset_wraparound(self):
        self.ctx = context(n=20, first=100)
        got = self.signal([phase(start=95, end=105), phase(side=AWAY, start=115, end=125)])
        self.assertTrue(np.all(got[:5] > 0))
        self.assertTrue(np.all(got[5:15] == 0))
        self.assertTrue(np.all(got[15:] < 0))
        np.testing.assert_array_equal(self.signal([phase(start=20, end=40)]), 0.)

    def test_unavailable_calibration_or_zero_reliability_contributes_nothing(self):
        np.testing.assert_array_equal(self.signal([phase()], {}), 0.)
        np.testing.assert_array_equal(self.signal([phase()], calibration("build up", reliability=0.)), 0.)

    def test_restart_windows_are_not_team_phases(self):
        event = phase("set pieces")
        event["type"] = "throw-in"
        np.testing.assert_array_equal(self.signal([event]), 0.)
        restart = evidence.setpiece_llr(self.ctx, [event], self.cfg)
        self.assertTrue(np.any(restart != 0))


class PhaseCalibrationTests(unittest.TestCase):
    def test_geometry_agreement_sets_polarity_without_reference_labels(self):
        event = phase(start=0, end=200)
        cfg = config.build()
        agreeing = pipeline.calibrate_tag_codes([event], [context()], cfg)["build up"]
        opposite = pipeline.calibrate_tag_codes([event], [context(home=False)], cfg)["build up"]
        self.assertEqual(agreeing["polarity"], 1)
        self.assertEqual(opposite["polarity"], -1)
        self.assertEqual(agreeing["reliability"], opposite["reliability"])
        self.assertEqual(agreeing["reliability"], 1.)

    def test_balanced_disagreement_is_neutral(self):
        ctx = context()
        ctx["c_home"][100:] = 0.
        ctx["c_away"][100:] = 1.
        entry = pipeline.calibrate_tag_codes([phase(start=0, end=200)], [ctx], config.build())["build up"]
        self.assertEqual(entry["reliability"], 0.)

    def test_no_confident_observations_keep_the_weak_prior(self):
        ctx = context()
        ctx["confident"][:] = False
        cfg = config.build()
        entry = pipeline.calibrate_tag_codes([phase(start=0, end=200)], [ctx], cfg)["build up"]
        self.assertEqual(entry["frames"], 0)
        self.assertEqual(entry["reliability"], cfg["tag.default_reliability"])
        self.assertIsNone(entry["agreement"])

    def test_disabling_phase_tags_is_separate_from_setpiece_and_p2_switches(self):
        cfg = config.build(["tag.enabled=0"])
        self.assertEqual(cfg["tag.enabled"], 0)
        self.assertEqual(cfg["dead.setpiece_enabled"], 1)
        self.assertEqual(cfg["p2.enabled"], 0)


if __name__ == "__main__":
    unittest.main()
