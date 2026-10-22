"""Solo fixtures sintéticos y CSV públicos, nunca datos restringidos."""
import contextlib
import io
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
import pandas as pd

from docker import pipeline
from evaluation import possession_metrics as pm
from starter.load_atd import video_frame_of
from starter import load_smart_tagging
import games

ROOT = Path(__file__).resolve().parents[1]


class ContractTests(unittest.TestCase):
    def test_official_format(self):
        table = pd.DataFrame({"frame": [0, 1, 2, 3], "label": list("HADX")})
        self.assertIsNone(pm.validate_submission(table, 4))
        for frames, labels in [([0, 0], ["H", "A"]), ([1, 2], ["H", "A"]),
                               ([0, 1], ["H", "Z"]), ([0, 1], ["H", None])]:
            with self.subTest(frames=frames, labels=labels):
                self.assertTrue(pm.validate_submission(pd.DataFrame({"frame": frames, "label": labels}), 2))
        self.assertTrue(pm.validate_submission(table, 5))

    def test_alignment_and_coordinates(self):
        from solution.contract import normalized_to_metres, validate_positions, validate_frames
        self.assertEqual(video_frame_of(1), 0)
        self.assertEqual(video_frame_of(26), 25)
        np.testing.assert_allclose(normalized_to_metres([[0.5, 0.5]], (100, 60)), [[50, 30]])
        validate_frames(np.arange(2), 2)
        with self.assertRaises(ValueError):
            validate_frames(np.array([0, 0]), 2)
        validate_positions(np.array([[1., 2.], [np.nan, np.nan]]),
                           np.array([True, False]), np.array([True, False]), np.array([False, False]))
        validate_positions(np.array([[1., 2.]]), np.array([False]), np.array([True]), np.array([True]))
        with self.assertRaises(ValueError):
            validate_positions(np.array([[0., 0.]]), np.array([False]), np.array([False]), np.array([False]))

    def test_config_validation(self):
        from solution.predict import load_config
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "config.json"
            good = {"contract_version": "1.0", "model": "constant", "parameters": {"label": "D"},
                    "seed": 0, "evaluation": {"split": "public-5min", "bootstrap": 0}}
            for change in [{"extra": 1}, {"model": "unknown"}, {"seed": True},
                           {"evaluation": {"split": "private", "bootstrap": 0}},
                           {"parameters": {"label": "Z"}}]:
                value = dict(good, **change)
                path.write_text(json.dumps(value), encoding="utf-8")
                with self.subTest(change=change), self.assertRaises(ValueError):
                    load_config(path)
            path.write_text(json.dumps(good), encoding="utf-8")
            self.assertEqual(load_config(path), good)

    def test_tracking_rejects_duplicate_and_short(self):
        from solution.contract import check_tracking_frames
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.txt"
            path.write_text("1:NaN:NaN\n2:NaN:NaN\n", encoding="utf-8")
            check_tracking_frames(path, 2)
            for content in ("1:NaN:NaN\n1:NaN:NaN\n", "1:NaN:NaN\n", "bad\n"):
                path.write_text(content, encoding="utf-8")
                with self.assertRaises(ValueError):
                    check_tracking_frames(path, 2)

    def test_smart_tagging_half_open(self):
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "synthetic.xml"
            path.write_text("<root><instance><code>synthetic</code><start>1</start><end>2</end>"
                            "</instance></root>", encoding="utf-8")
            with patch.object(load_smart_tagging, "pattern_path", return_value=str(path)):
                event = load_smart_tagging.load()[0]
            self.assertEqual((event["start_frame"], event["end_frame"]), (25, 50))
            self.assertEqual(list(range(event["start_frame"], event["end_frame"]))[-1], 49)

    def test_module_adapter_preserves_brief(self):
        from solution.predict import generate
        config = {"model": "module", "parameters": {"module": "solution.candidate_a"}}
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / "candidate.csv"
            def fake_run(command, **kwargs):
                self.assertEqual(command, [sys.executable, "-m", "solution.candidate_a", "--out", str(output)])
                self.assertTrue(kwargs["check"])
                output.write_text("frame,label\n0,H\n", encoding="utf-8")
            with patch("solution.predict.subprocess.run", side_effect=fake_run):
                generate(config, directory, output)
            with self.assertRaises(FileExistsError):
                generate(config, directory, output)


class PipelineTests(unittest.TestCase):
    def execute(self, directory, *args):
        env = dict(os.environ, GTT_SALIDAS=str(Path(directory) / "salidas"),
                   PYTHONUTF8="1", PYTHONIOENCODING="utf-8", PYTHONDONTWRITEBYTECODE="1")
        result = subprocess.run([sys.executable, "docker/pipeline.py", *args], cwd=ROOT,
                                env=env, capture_output=True, text=True, encoding="utf-8")
        records = list((Path(directory) / "salidas").glob("*/run.json"))
        return result, [json.loads(p.read_text(encoding="utf-8")) for p in records]

    def test_public_references(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.execute(directory, "evaluar")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertEqual(len(records), 1)
            record = records[0]
            self.assertEqual(len(record["csv"]), 4)
            expected = {"baseline_raw": (0.0378, 0.5972), "baseline_smooth25": (0.2868, 0.6200),
                        "baseline_smooth50": (0.3256, 0.6207), "baseline_smooth125": (0.4242, 0.5812)}
            for entry in record["csv"]:
                spell, macro = expected[entry["nombre"]]
                self.assertAlmostEqual(entry["metricas"]["spellF1"], spell, delta=0.0001)
                self.assertAlmostEqual(entry["metricas"]["macroF1"], macro, delta=0.0001)
            self.assertIn("ground_truth_sha256", record["evaluacion"])
            self.assertEqual(record["estado"], "ok")

    def test_invalid_and_empty_fail_and_record(self):
        for empty in (False, True):
            with self.subTest(empty=empty), tempfile.TemporaryDirectory() as directory:
                source = Path(directory) / "csv"
                source.mkdir()
                if not empty:
                    (source / "bad.csv").write_text("frame,label\n0,H\n", encoding="utf-8")
                result, records = self.execute(directory, "evaluar", "--resultados", str(source))
                self.assertEqual(result.returncode, 2, result.stderr)
                self.assertEqual(records[0]["codigo_salida"], 2)

    def test_model_end_to_end_and_repeat(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.execute(directory, "modelo", "--config", "configs/smoke_constant.json", "--repetir")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            record = records[0]
            self.assertTrue(record["determinista"])
            self.assertFalse(record["seed_applied"])
            self.assertEqual(record["modelo"], "constant")
            self.assertIn("candidato", record["por_debajo_de_referencia"])
            folder = Path(directory) / "salidas" / record["id"]
            self.assertEqual(pipeline.sha256(folder / "config.json"), record["config_sha256"])
            self.assertEqual(pipeline.sha256(folder / "results/candidato.csv"),
                             next(e["sha256"] for e in record["csv"] if e["nombre"] == "candidato"))
            result, _ = self.execute(directory, "modelo", "--config", "configs/smoke_constant.json", "--exigir-referencia")
            self.assertEqual(result.returncode, 5, result.stdout + result.stderr)

    def test_missing_data_and_bad_config_recorded(self):
        with tempfile.TemporaryDirectory() as directory:
            result, records = self.execute(directory, "modelo", "--config", "configs/baseline_smooth50.json",
                                           "--data-dir", str(Path(directory) / "missing"))
            self.assertEqual(result.returncode, 3, result.stdout + result.stderr)
            self.assertIn("error", records[0])
        with tempfile.TemporaryDirectory() as directory:
            path = Path(directory) / "invalid.json"
            path.write_text('{"model":"unknown"}', encoding="utf-8")
            result, records = self.execute(directory, "modelo", "--config", str(path))
            self.assertEqual(result.returncode, 1)
            self.assertIn("error", records[0])

    def test_baseline_with_synthetic_tracking(self):
        with tempfile.TemporaryDirectory() as directory:
            tactical = Path(directory) / "tactical"
            tactical.mkdir()
            (tactical / "BAR-ATH_tactical_atd.xml").write_text(
                '<root><Team id="h"><Name>Synthetic H</Name></Team>'
                '<Team id="a"><Name>Synthetic A</Name></Team>'
                '<Player teamId="h"/><Player teamId="a"/></root>', encoding="utf-8")
            raw = tactical / "BAR-ATH_tactical_atd.txt"
            with raw.open("w", encoding="utf-8") as handle:
                for frame in range(1, games.source_frames() + 1):
                    ball = "0.1,0.5,0" if (frame // 250) % 2 == 0 else "0.9,0.5,0"
                    handle.write(f"{frame}:0.1,0.5,0;0.9,0.5,0:{ball}\n")
            result, records = self.execute(directory, "modelo", "--config", "configs/baseline_smooth50.json",
                                           "--data-dir", directory, "--repetir")
            self.assertEqual(result.returncode, 0, result.stdout + result.stderr)
            self.assertTrue(records[0]["determinista"])
            self.assertEqual(len(records[0]["inputs"]), 2)
    def test_unique_runs_and_concurrent_index(self):
        with tempfile.TemporaryDirectory() as directory:
            env = dict(os.environ, GTT_SALIDAS=directory, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
            command = [sys.executable, "docker/pipeline.py", "evaluar", "--resultados", directory + "/empty"]
            processes = [subprocess.Popen(command, cwd=ROOT, env=env, stdout=subprocess.PIPE,
                                          stderr=subprocess.PIPE) for _ in range(2)]
            for process in processes:
                process.communicate(timeout=60)
                self.assertEqual(process.returncode, 2)
            self.assertEqual(len(list(Path(directory).glob("*/run.json"))), 2)
            index = [json.loads(line) for line in (Path(directory) / "runs.jsonl").read_text(encoding="utf-8").splitlines()]
            self.assertEqual(len({r["id"] for r in index}), 2)

    def test_unexpected_error_is_recorded(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"GTT_SALIDAS": directory}):
            with patch.object(pipeline, "cmd_evaluar", side_effect=RuntimeError("synthetic failure")):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = pipeline.main(["evaluar"])
            self.assertEqual(code, 1)
            record_path = next(Path(directory).glob("*/run.json"))
            self.assertIn("synthetic failure", json.loads(record_path.read_text(encoding="utf-8"))["error"])

    def test_nonzero_evaluator_and_missing_report(self):
        for return_code in (0, 1):
            with self.subTest(return_code=return_code), tempfile.TemporaryDirectory() as directory:
                with patch.object(pipeline, "run", return_value=return_code), contextlib.redirect_stdout(io.StringIO()):
                    entries, code = pipeline.evaluate(pipeline.PUBLIC_RESULTS, directory, 0)
                self.assertEqual(code, 1)
                self.assertTrue(entries)

    def test_generator_failure_recorded(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"GTT_SALIDAS": directory}):
            with patch.object(pipeline, "run", return_value=1):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    code = pipeline.main(["modelo", "--config", "configs/smoke_constant.json"])
            self.assertEqual(code, 1)
            record = json.loads(next(Path(directory).glob("*/run.json")).read_text(encoding="utf-8"))
            self.assertIn("generador", record["error"])

    def test_reference_name_cannot_be_spoofed(self):
        with tempfile.TemporaryDirectory() as directory:
            source = Path(directory) / "csv"
            source.mkdir()
            (source / "baseline_smooth50.csv").write_text("frame,label\n0,H\n", encoding="utf-8")
            result, records = self.execute(directory, "evaluar", "--resultados", str(source))
            self.assertEqual(result.returncode, 2)
            self.assertIn("reservado", records[0]["error"])

    def test_record_write_failure_is_not_success(self):
        with tempfile.TemporaryDirectory() as directory, patch.dict(os.environ, {"GTT_SALIDAS": directory}):
            with patch.object(pipeline, "atomic_json", side_effect=OSError("synthetic write failure")):
                with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
                    self.assertEqual(pipeline.main(["evaluar", "--resultados", directory + "/empty"]), 1)


if __name__ == "__main__":
    unittest.main()
