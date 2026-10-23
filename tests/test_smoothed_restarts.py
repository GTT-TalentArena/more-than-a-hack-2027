"""Regression fixtures for gradual acceleration; all trajectories are invented."""
import unittest

import numpy as np

from solution import dead_ball as db


FPS = 25
PITCH = (105.3, 68.0)


def trajectory(speeds, spot=(50., 30.)):
    xy = np.tile(np.asarray(spot, float), (len(speeds), 1))
    xy[:, 0] += np.cumsum(speeds) / FPS
    return xy


def gradual(spot=(50., 30.)):
    return trajectory([0.] * 10 + [.7, 1.1, 1.6, 1.9] + [2.5] * 10, spot)


def detect(xy, kind="Free Kick", end=None, periods=None, **parameters):
    n = len(xy)
    event = dict(code="SET PIECES", start_frame=0, end_frame=n if end is None else end,
                 tags={"Type": kind, "Team": "Barcelona"})
    return db.detect(xy, np.all(np.isfinite(xy), axis=1),
                     np.ones(n, int) if periods is None else periods, [event], FPS, PITCH,
                     np.zeros(n), np.full(n, 22), parameters)


def preparations(candidates):
    return [c for c in candidates if c["evidence"] == "tagged_preparation"]


class SmoothedRestartTests(unittest.TestCase):
    def test_gradual_acceleration_is_detected_and_dated_at_motion(self):
        signals, candidates, _ = detect(gradual())
        found = preparations(candidates)
        self.assertEqual(len(found), 1)
        self.assertEqual(found[0]["restart_frame"], 14)
        self.assertEqual(found[0]["end_frame"], 14)
        self.assertTrue(np.all(signals["dead_score"][1:14] >= .75))
        self.assertEqual(signals["dead_score"][14], 0.)
        self.assertGreaterEqual(signals["restart_score"][14], .75)

    def test_zero_wait_preserves_legacy_rule_and_immediate_restarts(self):
        self.assertEqual(preparations(detect(gradual(), restart_search_s=0)[1]), [])
        immediate = trajectory([0.] * 10 + [3.] * 10)
        _, candidates, _ = detect(immediate, restart_search_s=0)
        self.assertEqual(preparations(candidates)[0]["restart_frame"], 10)

    def test_wait_limit_is_inclusive_and_only_limits_motion_start(self):
        found = preparations(detect(gradual(), restart_search_s=4 / FPS)[1])
        self.assertEqual(found[0]["restart_frame"], 14)
        self.assertEqual(preparations(detect(gradual(), restart_search_s=3 / FPS)[1]), [])

    def test_confirmation_cannot_cross_exclusive_event_end(self):
        self.assertEqual(preparations(detect(gradual(), end=16)[1]), [])
        self.assertEqual(preparations(detect(gradual(), end=17)[1])[0]["restart_frame"], 14)

    def test_confirmation_cannot_cross_halves(self):
        xy = gradual()
        periods = np.r_[np.ones(16, int), np.full(len(xy) - 16, 2, int)]
        self.assertEqual(preparations(detect(xy, periods=periods)[1]), [])

    def test_wait_does_not_bridge_missing_ball_or_rejected_speed_jumps(self):
        for missing in (True, False):
            with self.subTest(missing=missing):
                xy = gradual()
                xy[11] = np.nan if missing else xy[11] + [30., 0.]
                self.assertEqual(preparations(detect(xy)[1]), [])

    def test_late_motion_is_rejected_and_spikes_need_sustained_confirmation(self):
        late = trajectory([0.] * 10 + [1.] * 26 + [3.] * 5)
        self.assertEqual(preparations(detect(late)[1]), [])
        spike = trajectory([0.] * 10 + [1., 2.5, 1., 1., 1.])
        self.assertEqual(preparations(detect(spike)[1]), [])
        followed = trajectory([0.] * 10 + [1., 2.5, 1., 1.] + [2.5] * 5)
        self.assertEqual(preparations(detect(followed)[1])[0]["restart_frame"], 14)

    def test_supported_set_piece_zones_accept_gradual_acceleration(self):
        for kind, spot in (("Corner Kick", (1., 1.)), ("Throw-in", (50., 1.)),
                           ("Goal Kick", (1., 34.)), ("Free Kick", (50., 30.)),
                           ("Kick Off (After Goal)", (PITCH[0] / 2, PITCH[1] / 2))):
            with self.subTest(kind=kind):
                self.assertEqual(preparations(detect(gradual(spot), kind=kind)[1])[0]["restart_frame"], 14)

    def test_centre_smoothed_trajectory_reproduces_the_reported_blind_spot(self):
        n, kick, half = 100, 40, 12
        true_x = 50. + np.maximum(np.arange(n) - kick, 0) * 6. / FPS
        smooth_x = np.convolve(np.pad(true_x, (half, half), mode="edge"),
                               np.ones(2 * half + 1) / (2 * half + 1), mode="valid")
        xy = np.column_stack((smooth_x, np.full(n, 30.)))
        self.assertEqual(preparations(detect(xy, restart_search_s=0)[1]), [])
        found = preparations(detect(xy)[1])
        self.assertEqual(len(found), 1)
        speed = np.r_[np.nan, np.diff(smooth_x) * FPS]
        expected = next(i for i in range(n - 2) if np.all(speed[i:i + 3] >= 2.))
        self.assertEqual(found[0]["restart_frame"], expected)

    def test_wait_parameter_validation_and_unknown_options(self):
        for invalid in (-1, True, float("nan"), float("inf"), "1"):
            with self.subTest(invalid=invalid), self.assertRaises(ValueError):
                detect(gradual(), restart_search_s=invalid)
        with self.assertRaises(ValueError):
            detect(gradual(), restart_search_frames=25)


if __name__ == "__main__":
    unittest.main()
