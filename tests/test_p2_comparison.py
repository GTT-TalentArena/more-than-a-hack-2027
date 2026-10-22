"""Comparison rejects confounding changes; all records here are invented."""
import json
from pathlib import Path
import tempfile
import unittest

from scripts.summarize_p2 import summarize


class ComparisonTests(unittest.TestCase):
    def records(self, directory, change=None):
        for enabled in (False, True):
            folder = Path(directory) / ("on" if enabled else "off")
            (folder / "reports").mkdir(parents=True)
            record = dict(modelo="baseline_dead_ball", estado="ok", determinista=True,
                commit="synthetic", model_sources={"source": "synthetic-hash"}, entorno={"python": "test"},
                evaluacion={"split": "synthetic"}, seed=0, split="synthetic", id=folder.name,
                config=dict(parameters=dict(enabled=enabled, threshold=.75)),
                inputs=[dict(asset="atd_meta", sha256="meta"), dict(asset="atd_raw", sha256="raw")],
                csv=[dict(nombre="candidato", valido=True, sha256="prediction", metricas={"spellF1": .5})],
                diagnostics=dict(dead_label_frames=12, secret_frame_rows=["never export"]))
            if enabled and change:
                change(record)
            (folder / "run.json").write_text(json.dumps(record), encoding="utf-8")
            (folder / "reports/candidato.json").write_text(json.dumps(dict(alive_dead_f1=.8, frame_rows=[1, 2])), encoding="utf-8")

    def test_exports_allowlisted_aggregates_only(self):
        with tempfile.TemporaryDirectory() as directory:
            self.records(directory)
            result = summarize(Path(directory))
            self.assertTrue(result["controlled_comparison"])
            self.assertEqual(result["variants"]["enabled"]["diagnostics"], dict(dead_label_frames=12))
            self.assertNotIn("frame_rows", json.dumps(result))

    def test_rejects_changed_code_data_or_parameters(self):
        changes = [lambda r: r["model_sources"].update(source="different"),
                   lambda r: r["inputs"][0].update(sha256="different"),
                   lambda r: r["config"]["parameters"].update(threshold=.9)]
        for change in changes:
            with self.subTest(change=change), tempfile.TemporaryDirectory() as directory:
                self.records(directory, change)
                with self.assertRaises(ValueError):
                    summarize(Path(directory))

    def test_rejects_unverified_repetition(self):
        with tempfile.TemporaryDirectory() as directory:
            self.records(directory, lambda r: r.update(determinista=False))
            with self.assertRaises(ValueError):
                summarize(Path(directory))


if __name__ == "__main__":
    unittest.main()
