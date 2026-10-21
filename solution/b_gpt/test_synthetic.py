"""All fixtures are generated here; never open a match asset or ground-truth CSV."""

import contextlib
import io
import itertools
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from .config import CONFIG
from .io import InputError, read_events, read_tracking, write_submission
from .model import (build_evidence, clean_ball, decode, event_team, features, predict,
                    tag_priors)
from .synthetic import from_labels


NAMES = ("Barcelona", "Athletic Club")
PITCH = (105.3, 68.0)


def infer(truth, missing=False, events=()):
    tracking = from_labels(truth, missing=missing)
    labels, _ = predict(tracking, events, NAMES, [(1, 0, len(truth) - 1)], 25, PITCH)
    return labels


class SyntheticBehaviour(unittest.TestCase):
    def test_short_control_and_stoppage_separate_same_team(self):
        truth = np.array(list("H" * 250 + "A" * 20 + "H" * 250 + "D" * 150 + "H" * 250))
        result = infer(truth)
        self.assertTrue(np.all(result[250:270] == "A"))
        self.assertGreater(np.mean(result == truth), .98)
        self.assertTrue(np.all(result[530:660] == "D"))

    def test_short_missing_ball_does_not_mean_dead(self):
        # v2 (Claude): a short occlusion (< medium_gap_s) keeps the possession.
        truth = np.full(800, "H")
        tracking = from_labels(truth, missing=False)
        tracking.ball[150:250] = np.nan
        result, _ = predict(tracking, [], NAMES, [(1, 0, 799)], 25, PITCH)
        self.assertTrue(np.all(result == "H"))

    def test_shielded_ball_that_comes_back_moving_keeps_possession(self):
        # v3 (Claude): a player with his back to the camera hides the ball for 8 s; it comes
        # back moving inside the pitch with the same team. That is live play, not a stoppage.
        truth = np.full(900, "H")
        tracking = from_labels(truth, missing=False)
        tracking.ball[300:500] = np.nan
        result, _ = predict(tracking, [], NAMES, [(1, 0, 899)], 25, PITCH)
        self.assertTrue(np.all(result == "H"))

    def _gap_then(self, gap_frames, ball_after, players_running=True):
        truth = np.full(300 + gap_frames + 300, "H")
        tracking = from_labels(truth, missing=False)
        end = 300 + gap_frames
        tracking.ball[300:end] = np.nan
        if ball_after is not None:
            # The restart: ball placed at ball_after for 1 s, with the H taker next to it.
            tracking.ball[end:end + 25, :2] = ball_after
            tracking.players[end:end + 25, 0, :2] = np.asarray(ball_after) + [.6, 0]
        result, _ = predict(tracking, [], NAMES, [(1, 0, len(truth) - 1)], 25, PITCH)
        return result, end

    def test_gap_ending_with_a_placed_ball_is_a_stoppage(self):
        result, end = self._gap_then(375, (60, 30))  # 15 s, free kick in midfield
        self.assertTrue(np.all(result[310:end - 10] == "D"))

    def test_gap_ending_at_the_touchline_is_a_stoppage(self):
        result, end = self._gap_then(200, (40, .4))  # 8 s, throw-in
        self.assertTrue(np.all(result[310:end - 10] == "D"))

    def test_very_long_gap_is_a_stoppage_even_if_play_resumes_moving(self):
        result, end = self._gap_then(round(31 * 25), None)
        self.assertTrue(np.all(result[310:end - 10] == "D"))

    def test_ball_lost_after_leaving_pitch_is_dead_even_with_running_players(self):
        # v1 (Claude): exit over the touchline, then the tracker loses the ball for 6 s while
        # players keep jogging (2.7 m/s), as at a throw-in. Play resumes with the ball back inside.
        truth = np.full(900, "H")
        tracking = from_labels(truth, missing=False)
        tracking.ball[300:302, :2] = [50, -1.5]
        tracking.ball[302:452] = np.nan
        result, totals = predict(tracking, [], NAMES, [(1, 0, 899)], 25, PITCH)
        self.assertTrue(np.all(result[310:450] == "D"))
        self.assertTrue(np.all(result[:290] == "H"))
        self.assertTrue(np.all(result[470:] == "H"))
        self.assertEqual(totals["out_of_play_gap_frames"], 150)

    def test_gap_without_a_clear_exit_keeps_possession(self):
        # Same occlusion, but the ball was last seen just over the line by tracking noise only.
        truth = np.full(900, "H")
        tracking = from_labels(truth, missing=False)
        tracking.ball[301, :2] = [50, -.5]
        tracking.ball[302:402] = np.nan  # v2: short, so only the exit rule could make it D
        result, totals = predict(tracking, [], NAMES, [(1, 0, 899)], 25, PITCH)
        self.assertTrue(np.all(result == "H"))
        self.assertEqual(totals["out_of_play_gap_frames"], 0)

    def test_ball_and_players_missing_is_an_outage_not_a_stoppage(self):
        truth = np.full(1200, "H")
        tracking = from_labels(truth, missing=False)
        tracking.ball[300:800] = np.nan
        tracking.players[300:800] = np.nan
        result, _ = predict(tracking, [], NAMES, [(1, 0, 1199)], 25, PITCH)
        self.assertFalse(np.any(result == "D"))

    def test_out_of_play_gap_is_capped_by_restart_look_back(self):
        truth = np.full(2000, "H")
        tracking = from_labels(truth, missing=False)
        tracking.ball[100:102, :2] = [50, -1.5]
        tracking.ball[102:1902] = np.nan
        _, totals = predict(tracking, [], NAMES, [(1, 0, 1999)], 25, PITCH)
        self.assertEqual(totals["out_of_play_gap_frames"], round(CONFIG.stop_lookback_s * 25))

    def test_v4_diagnostics_are_aggregates_and_see_a_placed_ball_and_a_duel(self):
        import json
        truth = np.full(1500, "H")
        tracking = from_labels(truth, missing=False)
        # A ball placed still for 4 s in open play, with the H taker next to it.
        tracking.ball[600:700, :2] = [60, 30]
        tracking.players[600:700, 0, :2] = [60.4, 30]
        # Two seconds of duel: H at 0.4 m and A at 0.7 m from the ball.
        tracking.players[900:950, 1, :2] = tracking.ball[900:950, :2] + [-.7, 0]
        _, totals = predict(tracking, [], NAMES, [(1, 0, 1499)], 25, PITCH)
        diagnostics = totals["v4_diagnostics"]
        json.dumps(diagnostics, allow_nan=False)  # aggregates only, serialisable
        self.assertEqual(diagnostics["still_ball_1s_by_zone"]["open"]["runs_3s"], 1)
        self.assertGreaterEqual(diagnostics["duels"]["minutes"], round(50 / 25 / 60, 2))
        leaves = []
        def walk(node):
            for value in node.values():
                walk(value) if isinstance(value, dict) else leaves.append(value)
        walk(diagnostics)
        self.assertTrue(all(v is None or isinstance(v, (int, float)) for v in leaves))

    def test_flight_past_opponent_retains_previous_team(self):
        truth = np.full(700, "H")
        tracking = from_labels(truth, missing=False)
        # Opponent is closer for three seconds, but far from control radius.
        tracking.players[250:325, 0, :2] = tracking.ball[250:325, :2] + [12, 0]
        tracking.players[250:325, 1, :2] = tracking.ball[250:325, :2] + [-6, 0]
        result, _ = predict(tracking, [], NAMES, [(1, 0, 699)], 25, PITCH)
        self.assertTrue(np.all(result == "H"))

    def test_one_frame_deflection_does_not_split(self):
        truth = np.full(600, "H")
        tracking = from_labels(truth, missing=False)
        tracking.players[300, 0, :2] = tracking.ball[300, :2] + [9, 0]
        tracking.players[300, 1, :2] = tracking.ball[300, :2] + [.2, 0]
        result, _ = predict(tracking, [], NAMES, [(1, 0, 599)], 25, PITCH)
        self.assertTrue(np.all(result == "H"))

    def test_change_after_occlusion_is_not_backdated_to_start_of_gap(self):
        truth = np.array(list("H" * 400 + "A" * 400))
        tracking = from_labels(truth, missing=False)
        tracking.ball[300:400] = np.nan  # v2: short occlusion (< medium_gap_s)
        result, _ = predict(tracking, [], NAMES, [(1, 0, 799)], 25, PITCH)
        self.assertTrue(np.all(result[:400] == "H"))
        self.assertTrue(np.all(result[400:] == "A"))

    def test_halves_do_not_share_state(self):
        truth = np.array(list("X" * 20 + "H" * 250 + "X" * 100 + "A" * 250 + "X" * 20))
        tracking = from_labels(truth, missing=False)
        labels, _ = predict(tracking, [], NAMES, [(1, 20, 269), (2, 370, 619)], 25, PITCH)
        self.assertTrue(np.array_equal(truth, labels))

    def test_fully_unobserved_half_abstains(self):
        tracking = from_labels(np.full(500, "H"), missing=False)
        tracking.ball[:] = np.nan
        tracking.players[:] = np.nan
        result, _ = predict(tracking, [], NAMES, [(1, 0, 499)], 25, PITCH)
        self.assertTrue(np.all(result == "X"))

    def test_ball_teleport_rejected_and_long_gap_not_interpolated(self):
        raw = np.tile([50., 30., 1.], (200, 1))
        raw[50, :2] = [100, 60]
        raw[100:150] = np.nan
        ball, quality, _ = clean_ball(raw, 25, PITCH)
        self.assertLess(quality[50], 1.)
        self.assertLess(np.linalg.norm(ball[50] - [50, 30]), .01)
        self.assertTrue(np.all(quality[100:150] == 0))

    def test_defending_tags_invert_and_duplicate_phases_do_not_multiply(self):
        event = dict(start=0, end=300, code="defending in middle third", tags={"team": "Barcelona"})
        tag, _ = tag_priors([event], 300, NAMES, 25)
        repeated, _ = tag_priors([event] * 10, 300, NAMES, 25)
        self.assertLess(tag[100], 0)
        self.assertTrue(np.array_equal(tag, repeated))
        self.assertEqual(event_team("Atletic Club", NAMES), 1)
        self.assertIsNone(event_team("N/A", NAMES))

    def test_tags_cannot_overrule_strong_opposite_control(self):
        truth = np.full(600, "H")
        event = dict(start=0, end=600, code="build up", tags={"team": "Atletic Club"})
        result = infer(truth, events=[event])
        self.assertTrue(np.all(result == "H"))

    def test_kickoff_lead_in_is_derived_from_tag(self):
        truth = np.array(list("D" * 1000 + "A" * 500))
        event = dict(start=975, end=1025, code="set pieces",
                     tags={"team": "Atletic Club", "type": "kick off (start)"})
        tracking = from_labels(truth, missing=False)
        # No ball/low-activity cues in the lead-in: the automatic kickoff tag is sufficient.
        tracking.ball[:1000] = np.nan
        tracking.players[:1000, :, 2] = 1.6
        result, _ = predict(tracking, [event], NAMES, [(1, 0, 1499)], 25, PITCH)
        self.assertTrue(np.all(result[:970] == "D"))
        self.assertTrue(np.all(result[1030:] == "A"))

    def test_dead_and_restart_evidence_does_not_assume_tag_interval_dead(self):
        truth = np.full(1000, "H")
        event = dict(start=400, end=550, code="set pieces", tags={"type": "throw-in", "team": "n/a"})
        result = infer(truth, events=[event])
        self.assertTrue(np.all(result == "H"))

    def test_half_already_live_does_not_get_fake_kickoff_lead_in(self):
        truth = np.full(500, "H")
        event = dict(start=-10, end=90, code="set pieces",
                     tags={"type": "kick off (start)", "team": "Barcelona"})
        result = infer(truth, events=[event])
        self.assertTrue(np.all(result == "H"))

    def test_slot_order_and_identity_fragmentation_invariant(self):
        truth = np.array(list("H" * 300 + "A" * 300))
        tracking = from_labels(truth, missing=False)
        baseline, _ = predict(tracking, [], NAMES, [(1, 0, 599)], 25, PITCH)
        order = np.random.default_rng(1).permutation(len(tracking.teams))
        tracking.players = tracking.players[:, order]
        tracking.teams = tracking.teams[order]
        swapped, _ = predict(tracking, [], NAMES, [(1, 0, 599)], 25, PITCH)
        self.assertTrue(np.array_equal(baseline, swapped))

    def test_decoder_agrees_with_exhaustive_constrained_search(self):
        rng = np.random.default_rng(4)
        for _ in range(12):
            scores = rng.normal(size=(6, 3))
            acquire = rng.random((6, 2)) > .35
            seed = rng.random(6) > .4
            live = rng.random(6) > .3
            restart = rng.random((6, 2)) > .8
            result = decode(scores, acquire, seed, live, restart)

            def value(path):
                score = sum(scores[t, state] for t, state in enumerate(path))
                if path[0] == 2:
                    score -= 1e-9
                for t in range(1, 6):
                    old, new = path[t - 1:t + 1]
                    if old == new:
                        continue
                    if new == 2:
                        allowed, cost = seed[t], CONFIG.dead_switch_cost
                    elif old == 2:
                        allowed = live[t] and (acquire[t, new] or restart[t, new])
                        cost = CONFIG.dead_switch_cost
                    else:
                        allowed, cost = acquire[t, new], CONFIG.team_switch_cost
                    if not allowed:
                        return -np.inf
                    score -= cost
                return score

            optimum = max(value(p) for p in itertools.product(range(3), repeat=6))
            self.assertAlmostEqual(value(result), optimum)


class SyntheticIO(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="gtt-synthetic-")
        self.root = Path(self.temp.name)
        self.meta = self.root / "meta.xml"
        self.meta.write_text('<Root xmlns="urn:test"><Team id="one"><Name>Barcelona</Name></Team>'
                             '<Team id="two"><Name>Athletic Club</Name></Team>'
                             '<Player teamId="one"/><Player teamId="two"/></Root>')

    def tearDown(self):
        self.temp.cleanup()

    def test_raw_alignment_units_and_missing_values(self):
        raw = self.root / "raw.txt"
        raw.write_text("1:0.2,0.3,2;0.8,0.7,3:0.4,0.5,6\n"
                       "2:NaN,NaN,NaN;0.8,0.7,3:NaN,NaN,NaN\n")
        tracking, _ = read_tracking(self.meta, raw, 2, PITCH)
        self.assertAlmostEqual(float(tracking.ball[0, 0]), .4 * PITCH[0], places=4)
        self.assertAlmostEqual(float(tracking.players[0, 0, 1]), .3 * PITCH[1], places=4)
        self.assertTrue(np.isnan(tracking.ball[1]).all())

    def test_bad_record_fails_without_echoing_input(self):
        raw = self.root / "raw.txt"
        secret = "SYNTHETIC_PRIVATE_VALUE"
        for content in (f"{secret}:0,0,0;0,0,0:0,0,0\n",
                        "2:0,0,0;0,0,0:0,0,0\n", "1:0,0,0:0,0,0\n"):
            raw.write_text(content)
            stream = io.StringIO()
            with contextlib.redirect_stdout(stream), contextlib.redirect_stderr(stream):
                with self.assertRaises(InputError) as captured:
                    read_tracking(self.meta, raw, 1, PITCH)
            self.assertNotIn(secret, str(captured.exception))
            self.assertEqual(stream.getvalue(), "")

    def test_short_and_duplicate_inputs_rejected(self):
        raw = self.root / "raw.txt"
        raw.write_text("1:0,0,0;0,0,0:0,0,0\n")
        with self.assertRaises(InputError):
            read_tracking(self.meta, raw, 2, PITCH)
        raw.write_text("1:0,0,0;0,0,0:0,0,0\n" * 2)
        with self.assertRaises(InputError):
            read_tracking(self.meta, raw, 2, PITCH)

    def test_xml_case_and_frame_conversion(self):
        xml = self.root / "tags.xml"
        xml.write_text('<root><instance><start>1.2</start><end>2.4</end><code>SET PIECES</code>'
                       '<label><group>Team</group><text>N/A</text></label></instance></root>')
        events = read_events(xml, 25)
        self.assertEqual(events[0]["start"], 30)
        self.assertEqual(events[0]["end"], 60)
        self.assertEqual(events[0]["tags"]["team"], "n/a")

    def test_full_length_csv_contract(self):
        # Built-in CSV verification needs no pandas. Official validation is separate below.
        import csv
        labels = np.resize(np.array(list("HHHAADDXX")), 199319)
        path = self.root / "synthetic.csv"
        write_submission(path, labels, len(labels))
        with path.open() as handle:
            reader = csv.reader(handle)
            self.assertEqual(next(reader), ["frame", "label"])
            count = 0
            for i, row in enumerate(reader):
                self.assertEqual(row, [str(i), labels[i]])
                count += 1
        self.assertEqual(count, 199319)

    def test_official_validator_and_metric_on_synthetic_only(self):
        try:
            from evaluation import possession_metrics as pm
        except ModuleNotFoundError:
            self.skipTest("Official validator requires pandas; install pinned dependencies.")
        truth = np.array(list("H" * 250 + "A" * 20 + "H" * 250 + "D" * 150 + "A" * 250))
        result = infer(truth)
        path = self.root / "synthetic.csv"
        write_submission(path, result, len(truth))
        self.assertIsNone(pm.validate_submission(pm.read_label_csv(path), len(truth)))
        metrics = pm.evaluate(pm.label_codes(truth), pm.label_codes(result), bootstrap_n=0)
        self.assertGreater(metrics["spell_f1_mean"], .9)

    def test_synthetic_cli_never_resolves_real_assets(self):
        try:
            import pandas  # noqa: F401
        except ModuleNotFoundError:
            self.skipTest("CLI integration requires pinned pandas.")
        from .__main__ import main
        with patch("games.asset_paths", side_effect=AssertionError("Real paths forbidden")):
            with contextlib.redirect_stdout(io.StringIO()):
                code = main(["--synthetic", "--out", str(self.root / "synthetic.csv")])
        self.assertEqual(code, 0)


if __name__ == "__main__":
    unittest.main()
