"""GT-free diagnostics tested solely against generated labels and events."""

import contextlib
import hashlib
import io
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from .aggregate import comparison, event_coherence, fill_abstentions, summarise_prediction
from .io import InputError, write_submission
from .report_io import read_labels, write_summary


def event(midpoint, kind="throw-in", width=1):
    return dict(start=midpoint, end=midpoint + width, code="set pieces", tags={"type": kind})


class AggregateTests(unittest.TestCase):
    def test_half_denominators_quantiles_and_raw_abstention_percent(self):
        labels = np.array(list("HHDDHXHAAA" + "XXXXX" + "DDAAAHHHHH"))
        report = summarise_prediction(labels, [], [(1, 0, 9), (2, 15, 24)], 2)
        full, halves = report["full_match"], report["by_half"]
        self.assertEqual(full["n_possessions"], 5)
        self.assertEqual(full["n_possessions_without_X_fill"], 6)
        self.assertAlmostEqual(full["possessions_per_minute"], 30)
        self.assertAlmostEqual(halves["1"]["possessions_per_minute"], 36)
        self.assertAlmostEqual(halves["2"]["possessions_per_minute"], 24)
        self.assertEqual(full["percent_D"], 20)
        self.assertEqual(full["percent_X"], 5)
        self.assertEqual(full["duration_seconds"]["p50"], 1.5)
        self.assertAlmostEqual(full["duration_seconds"]["p10"], 1.2)
        self.assertAlmostEqual(full["duration_seconds"]["p90"], 2.1)
        self.assertEqual(report["whole_video"]["percent_X"], 24)
        self.assertIsNone(full["smart_tagging"]["all_set_pieces"]["coherent_midpoint_fraction"])

    def test_abstention_fill_matches_official_policy(self):
        from evaluation import possession_metrics as pm
        for text in ("XXXHXXADXX", "XXXX", "DXXH", "HXXH"):
            labels = np.array(list(text))
            codes = pm.label_codes(labels)
            expected = pm.fill_abstentions(codes, [(0, len(codes))])
            self.assertTrue(np.array_equal(pm.label_codes(fill_abstentions(labels)), expected))

    def test_exact_coherence_window_and_types(self):
        labels = np.array(list("DDHHHHHHHH"))
        events = [event(0), event(2, "corner kick"), event(6, "free kick"),
                  event(7, "goal kick"), event(8, "kick off (start)")]
        total, groups = event_coherence(labels, events, 0, 2)
        self.assertEqual(total["n_events"], 5)
        self.assertEqual(total["inside_dead"], 1)
        self.assertEqual(total["just_after_dead"], 2)
        self.assertEqual(total["coherent_midpoint"], 3)
        self.assertEqual(groups["free_kick"]["coherent_midpoint"], 1)
        self.assertEqual(groups["goal_kick"]["coherent_midpoint"], 0)

    def test_interval_uncertainty_is_separate_from_midpoint(self):
        labels = np.array(list("HHDDHHHHHH"))
        total, _ = event_coherence(labels, [event(0, width=3)], 0, 2)
        self.assertEqual(total["coherent_midpoint"], 0)
        self.assertEqual(total["interval_could_be_coherent"], 1)

    def test_all_dead_cannot_claim_detected_restarts(self):
        labels = np.full(30, "D")
        result = summarise_prediction(labels, [event(10)], [(1, 0, 29)], 2)["full_match"]
        self.assertEqual(result["percent_D"], 100)
        self.assertEqual(result["n_possessions"], 0)
        self.assertIsNone(result["duration_seconds"]["p50"])
        tags = result["smart_tagging"]["all_set_pieces"]
        self.assertEqual(tags["coherent_midpoint_fraction"], 1)
        self.assertEqual(tags["near_dead_to_live_boundary_fraction"], 0)

    def test_half_boundary_never_bridges_dead_evidence(self):
        labels = np.array(list("HHDD" + "XX" + "HHHH"))
        report = comparison(labels, labels, [event(6), event(4)], [(1, 0, 3), (2, 6, 9)], 2)
        self.assertEqual(report["event_inventory"]["midpoint_outside_halves"], 1)
        tags = report["b_gpt"]["by_half"]["2"]["smart_tagging"]["all_set_pieces"]
        self.assertEqual(tags["coherent_midpoint_fraction"], 0)
        self.assertEqual(report["b_gpt"], report["baseline_smooth50"])

    def test_unknown_type_counted_without_inventing_coherence(self):
        labels = np.full(10, "H")
        report = comparison(labels, labels, [event(2, "unknown")], [(1, 0, 9)], 2)
        self.assertEqual(report["event_inventory"]["unrecognised_type_in_halves"], 1)
        self.assertEqual(report["event_inventory"]["recognised_in_halves"], 0)

    def test_all_unknown_does_not_become_dead(self):
        labels = np.full(10, "X")
        report = summarise_prediction(labels, [event(2)], [(1, 0, 9)], 2)["full_match"]
        self.assertEqual(report["percent_X"], 100)
        self.assertEqual(report["n_possessions"], 0)
        self.assertEqual(report["smart_tagging"]["all_set_pieces"]["coherent_midpoint_fraction"], 0)


class SafeIOTests(unittest.TestCase):
    def test_parser_hides_bad_values(self):
        with tempfile.TemporaryDirectory(prefix="b-gpt-synthetic-") as temp:
            path = Path(temp) / "synthetic.csv"
            path.write_text("frame,label\n0,SECRET_SYNTHETIC\n")
            capture = io.StringIO()
            with contextlib.redirect_stdout(capture), contextlib.redirect_stderr(capture):
                with self.assertRaises(InputError) as raised:
                    read_labels(path, 1)
            self.assertNotIn("SECRET_SYNTHETIC", str(raised.exception))
            self.assertEqual(capture.getvalue(), "")

    def test_atomic_summary_preserves_only_when_requested(self):
        with tempfile.TemporaryDirectory(prefix="b-gpt-synthetic-") as temp:
            path = Path(temp) / "synthetic.summary.json"
            path.write_text('{"candidate":"old","config":{"x":1}}')
            write_summary(path, {"test_count": 2})
            self.assertEqual(json.loads(path.read_text())["config"], {"x": 1})
            write_summary(path, {"test_count": 3}, metadata={"candidate": "b_gpt"})
            actual = json.loads(path.read_text())
            self.assertNotIn("config", actual)
            self.assertEqual(actual["full_match_diagnostics"]["test_count"], 3)

    def test_two_full_runs_identical_csv_and_aggregate_only_stdout(self):
        from .__main__ import main
        from evaluation import possession_metrics as pm
        with tempfile.TemporaryDirectory(prefix="b-gpt-synthetic-full-") as temp:
            hashes = []
            # The synthetic branch must not even resolve a real data path.
            with patch("games.asset_paths", side_effect=AssertionError("Real data forbidden")):
                for iteration in range(2):
                    path = Path(temp) / f"synthetic-{iteration}.csv"
                    capture = io.StringIO()
                    with contextlib.redirect_stdout(capture):
                        self.assertEqual(main(["--synthetic", "--out", str(path)]), 0)
                    self.assertEqual(len(capture.getvalue().splitlines()), 1)
                    printed = json.loads(capture.getvalue())
                    self.assertEqual(set(printed), {"n_possessions", "mean_duration_seconds",
                                                   "median_duration_seconds", "percent_D", "percent_X"})
                    self.assertTrue(all(isinstance(x, (int, float)) for x in printed.values()))
                    self.assertIsNone(pm.validate_submission(pm.read_label_csv(path), 199319))
                    hashes.append(hashlib.sha256(path.read_bytes()).hexdigest())
                    report = json.loads(path.with_suffix(".summary.json").read_text())
                    diagnostics = report["full_match_diagnostics"]
                    self.assertIn("baseline_smooth50", diagnostics)
                    self.assertEqual(set(diagnostics["b_gpt"]["by_half"]), {"1", "2"})
            self.assertEqual(hashes[0], hashes[1])

    def test_local_cli_only_opens_declared_synthetic_inputs(self):
        import games
        from .__main__ import main
        from .synthetic import from_labels
        from unittest.mock import Mock
        with tempfile.TemporaryDirectory(prefix="b-gpt-synthetic-local-") as temp:
            root = Path(temp)
            n = 120
            truth = np.array(list("H" * 40 + "D" * 40 + "A" * 40))
            baseline = root / "baseline.csv"
            write_submission(baseline, truth, n)
            tags = root / "tags.xml"
            tags.write_text('<root><instance><start>3.0</start><end>3.4</end>'
                            '<code>SET PIECES</code><label><group>Type</group>'
                            '<text>Throw-in</text></label></instance></root>')
            paths = {"smart_tagging": str(tags), "atd_meta": str(root / "meta.xml"),
                     "atd_raw": str(root / "raw.txt")}
            resolve = Mock(return_value=paths)
            tracking = from_labels(truth, missing=False)
            config = dict(n_video_frames=n, fps=25, pitch=(105.3, 68))
            with patch.dict(games.GAMES, {games.GAME: config}), \
                    patch("games.half_video_blocks", return_value=[(1, 0, 119)]), \
                    patch("games.asset_paths", resolve), \
                    patch("solution.b_gpt.__main__.read_tracking", return_value=(tracking, ("Barcelona", "Athletic Club"))), \
                    contextlib.redirect_stdout(io.StringIO()):
                self.assertEqual(main(["--out", str(root / "result.csv"),
                                       "--baseline", str(baseline), "--data-dir", str(root)]), 0)
            resolve.assert_called_once_with(game=games.GAME, data_dir=str(root), source="tactical")


if __name__ == "__main__":
    unittest.main()
