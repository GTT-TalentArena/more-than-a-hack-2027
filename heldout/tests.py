"""Synthetic tests for the held-out harness. No DFL file and no challenge data is opened.

    python -m unittest heldout.tests -v
"""

import hashlib
import os
import tempfile
import unittest

import numpy as np

import games
from evaluation import possession_metrics as pm
from . import bundle, degrade, score
from .run import observation_hash

PER_HALF = 3000


def synthetic_match(seed=1, players=28):
    """Two halves of PER_HALF frames: 11 v 11 on the pitch, substitutes appearing later."""
    rng = np.random.default_rng(seed)
    n = 2 * PER_HALF
    period = np.repeat(np.array([1, 2], dtype=np.int8), PER_HALF)
    t = np.arange(n) / 25.0
    ball = np.zeros((n, 3), dtype=np.float32)
    ball[:, 0] = 52 + 30 * np.sin(t / 7)
    ball[:, 1] = 34 + 20 * np.sin(t / 5)
    team = (np.arange(players) % 2).astype(np.int8)
    pos = np.full((n, players, 3), np.nan, dtype=np.float32)
    for k in range(players):
        on = slice(0, n) if k < 22 else slice(PER_HALF + 500, n)
        pos[on, k, 0] = 10 + (k * 7) % 85 + 3 * np.sin(t[on] / (3 + k % 5))
        pos[on, k, 1] = 5 + (k * 11) % 58 + 3 * np.cos(t[on] / (4 + k % 3))
        pos[on, k, 2] = 2.0
    ball[rng.random(n) < 0.02, :2] = np.nan       # the provider's own few missing frames
    label = np.where(np.sin(t / 9) > 0, 0, 1).astype(np.int8)
    label[(t % 60) < 8] = 2
    return {"period": period, "ball": ball, "players": pos, "team": team, "label": label}


class Degradation(unittest.TestCase):
    def test_labels_never_reach_the_observation(self):
        match = synthetic_match()
        shuffled = dict(match, label=np.random.default_rng(0).permutation(match["label"]))
        removed = {k: v for k, v in match.items() if k != "label"}
        for profile in degrade.PROFILES:
            ref = observation_hash(degrade.observe(match, "SYN", profile, 47))
            self.assertEqual(ref, observation_hash(degrade.observe(shuffled, "SYN", profile, 47)))
            self.assertEqual(ref, observation_hash(degrade.observe(removed, "SYN", profile, 47)))

    def test_exactly_41_percent_missing_per_half_original_gaps_kept(self):
        match = synthetic_match()
        originally_missing = ~np.isfinite(match["ball"][:, 0])
        for profile in degrade.PROFILES:
            if profile == "clean":
                continue
            obs = degrade.observe(match, "SYN", profile, 48)
            missing = ~np.isfinite(obs["ball"][:, 0])
            self.assertTrue(np.all(missing[originally_missing]))
            for p in (1, 2):
                self.assertEqual(int(missing[match["period"] == p].sum()),
                                 int(round(degrade.MISSING_SHARE * PER_HALF)))

    def test_deterministic_by_seed(self):
        match = synthetic_match()
        one = observation_hash(degrade.observe(match, "SYN", "full", 47))
        self.assertEqual(one, observation_hash(degrade.observe(match, "SYN", "full", 47)))
        self.assertNotEqual(one, observation_hash(degrade.observe(match, "SYN", "full", 48)))

    def test_fragmentation_moves_tracks_between_slots_without_moving_players(self):
        match = synthetic_match()
        rng = np.random.default_rng(3)
        plain = degrade.assign_slots(match["players"], match["team"], False, rng)
        frag = degrade.assign_slots(match["players"], match["team"], True, rng)
        for t in (0, 1500, 4000, 5999):
            for team in (0, 1):
                cols = slice(team * 23, team * 23 + 23)
                a = np.sort(plain[t, cols, 0][np.isfinite(plain[t, cols, 0])])
                b = np.sort(frag[t, cols, 0][np.isfinite(frag[t, cols, 0])])
                np.testing.assert_array_equal(a, b)
        changes = sum(int(np.any(np.isfinite(frag[:-1, s, 0]) & np.isfinite(frag[1:, s, 0])
                                 & (frag[:-1, s, 0] != frag[1:, s, 0]))) for s in range(46))
        self.assertGreater(changes, 0)

    def test_ground_truth_mask_does_not_depend_on_the_observation(self):
        match = synthetic_match()
        gt = bundle.ground_truth(match["label"], match["period"])
        hidden = dict(match, ball=np.full_like(match["ball"], np.nan))
        np.testing.assert_array_equal(gt, bundle.ground_truth(hidden["label"], hidden["period"]))
        blocks = games.half_video_blocks(games.GAME)
        self.assertEqual(int((gt != 3).sum()), 2 * PER_HALF)
        self.assertTrue(np.all(gt[:blocks[0][1]] == 3))
        self.assertTrue(np.all(gt[blocks[0][1]:blocks[0][1] + PER_HALF] != 3))
        self.assertTrue(np.all(gt[blocks[0][1] + PER_HALF:blocks[1][1]] == 3))


class Bundle(unittest.TestCase):
    def test_both_candidates_readers_load_the_bundle(self):
        from solution.a_opus import atd
        from solution.b_gpt import io as b_io
        match = synthetic_match()
        obs = degrade.observe(match, "SYN", "full", 49)
        with tempfile.TemporaryDirectory() as tmp:
            hashes = bundle.write(tmp, obs, match["period"])
            self.assertEqual(set(hashes), {"atd_meta", "atd_raw", "smart_tagging"})
            paths = games.asset_paths(games.GAME, data_dir=tmp)
            n, pitch = bundle.N_FRAMES, bundle.PITCH
            data = atd.load(paths["atd_meta"], paths["atd_raw"], n, pitch)
            first = games.half_video_blocks(games.GAME)[0][1]
            k = 100
            self.assertAlmostEqual(float(data["bx"][first + k]), float(obs["ball"][k, 0]), places=2)
            self.assertEqual(len(data["slot_team"]), 46)
            tracking, names = b_io.read_tracking(paths["atd_meta"], paths["atd_raw"], n, pitch)
            self.assertEqual(names[0], bundle.HOME_NAME)
            self.assertAlmostEqual(float(tracking.ball[first + k, 0]), float(obs["ball"][k, 0]), places=2)

    def test_bundle_bytes_do_not_depend_on_labels(self):
        match = synthetic_match()
        obs = degrade.observe(match, "SYN", "gaps-long", 47)
        with tempfile.TemporaryDirectory() as one, tempfile.TemporaryDirectory() as two:
            self.assertEqual(bundle.write(one, obs, match["period"]),
                             bundle.write(two, obs, match["period"]))


class Scoring(unittest.TestCase):
    def setUp(self):
        match = synthetic_match()
        self.gt = bundle.ground_truth(match["label"], match["period"])

    def test_identical_predictions_give_a_zero_interval(self):
        result = score.paired_bootstrap([(self.gt, self.gt, self.gt)] * 2, draws=200)
        self.assertEqual((result["low"], result["high"]), (0.0, 0.0))
        self.assertFalse(result["excludes_zero"])

    def test_a_perfect_variant_beats_a_noisy_a(self):
        noisy = self.gt.copy()
        live = np.flatnonzero(np.isin(noisy, (0, 1)))
        flip = live[::40]
        noisy[flip] = 1 - noisy[flip]
        result = score.paired_bootstrap([(self.gt, noisy, self.gt)], draws=200)
        self.assertGreater(result["low"], 0)

    def test_false_short_possessions(self):
        pred = self.gt.copy()
        live = np.flatnonzero(pred == 0)
        start = live[200]
        pred[start:start + 10] = 1           # a 0.4 s away spell inside a home possession
        runs = pm.valid_runs(self.gt)
        filled = pm.fill_abstentions(pred, runs)
        clean_rate = score.false_short_rate(self.gt, pm.fill_abstentions(self.gt, runs), runs)
        rate = score.false_short_rate(self.gt, filled, runs)
        minutes = 2 * PER_HALF / 25 / 60
        self.assertAlmostEqual(rate - clean_rate, 90.0 / minutes)
        metrics = score.metrics(self.gt, pred)
        self.assertLess(metrics["spell_f1"], 1.0)


if __name__ == "__main__":
    unittest.main()
