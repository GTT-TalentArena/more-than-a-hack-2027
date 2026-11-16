"""Issue #20: fixed synthetic phase-tag ablations of the shipped DFL candidate.

Accepts only a new report path. No match inputs, reserved data, training or model
selection is supported. Exit zero means the audit ran, not that all issue criteria
are accepted or that phases improve real-match accuracy.
"""
import argparse
from contextlib import redirect_stdout
import copy
import hashlib
import io
import json
from pathlib import Path
import subprocess
import tempfile
import warnings
from unittest.mock import patch
import xml.etree.ElementTree as ET

import numpy as np

import games
from evaluation import possession_metrics as pm
from solution.a_dfl import __version__
from solution.a_dfl.model import installed
from solution.a_opus import ballfree, config, evidence, pipeline, synth, tags
from solution.a_opus.atd import HOME
from starter import load_smart_tagging
from tools.football_acceptance import source_identity

SEEDS = (20, 21, 22)
CONDITIONS = ("original", "missing-file", "empty-file", "opposing-phases",
              "repeated-phases", "phase-shift--25", "phase-shift-+25")


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def mutate_xml(original, condition):
    """Change phase observations only; preserve restart events in phase conditions."""
    if condition == "missing-file":
        return None
    tree = ET.fromstring(original)
    parent = tree.find("ALL_INSTANCES")
    if condition == "empty-file":
        parent.clear()
    for event in list(parent):
        if not tags.prior_polarity((event.findtext("code") or "").strip().lower()):
            continue
        if condition in ("opposing-phases", "repeated-phases"):
            extra = copy.deepcopy(event)
            if condition == "opposing-phases":
                for label in extra.findall("label"):
                    if label.findtext("group") == "Team":
                        value = label.find("text")
                        value.text = synth.TAG_NAMES[1] if value.text == synth.TAG_NAMES[0] else synth.TAG_NAMES[0]
            parent.append(extra)
            if condition == "repeated-phases":
                parent.append(copy.deepcopy(event))
        elif condition.startswith("phase-shift-"):
            shift_s = int(condition.removeprefix("phase-shift-")) / games.GAMES[games.GAME]["fps"]
            for key in ("start", "end"):
                event.find(key).text = str(float(event.findtext(key)) + shift_s)
    return ET.tostring(tree, encoding="utf-8", xml_declaration=True)


def input_identity(paths):
    return {key: sha(path) if Path(path).exists() else None for key, path in paths.items()}


def run_candidate(directory, out, enabled, truth):
    calibration = {}
    original = pipeline.calibrate_tag_codes

    def observe(*args, **kwargs):
        result = original(*args, **kwargs)
        calibration.update(result)
        return result

    overrides = ["tag.enabled={}".format(enabled)]
    with installed(), patch.object(ballfree, "fit_logistic", side_effect=AssertionError("Training forbidden")), \
            patch.object(pipeline, "calibrate_tag_codes", side_effect=observe), warnings.catch_warnings():
        warnings.simplefilter("ignore", RuntimeWarning)
        pipeline.run(str(out), str(directory), overrides=overrides, log=lambda *args: None)
    table = pm.read_label_csv(str(out))
    error = pm.validate_submission(table, games.source_frames())
    if error is not None:
        raise ValueError(error)
    predicted = pm.label_codes(table)
    score = pm.evaluate(truth, predicted, bootstrap_n=0)
    record = {"tag_enabled": enabled, "csv_sha256": sha(out), "rows": len(table),
              "configuration_sha256": hashlib.sha256(json.dumps(config.build(overrides), sort_keys=True).encode()).hexdigest(),
              "spellF1": score["spell_f1_mean"], "macroF1": score["macro_f1"],
              "predicted_possessions": score["n_pred_spells"], "reference_possessions": score["n_gt_spells"],
              "calibration": calibration}
    return predicted, record


def format_diagnostics():
    """Characterise existing edge behaviour without modifying the frozen parser."""
    records = {}
    cfg = config.build()
    raw = '<file><ALL_INSTANCES><instance><code>{}</code><start>0.4</start><end>{}</end>' \
          '<label><group>Team</group><text>Barcelona</text></label></instance></ALL_INSTANCES></file>'
    with tempfile.TemporaryDirectory(prefix="issue20-format-") as temp:
        path = Path(temp) / "invented.xml"
        with patch.object(load_smart_tagging, "pattern_path", return_value=str(path)):
            path.write_text(raw.format("BUILD  UP", "0.8"), encoding="utf-8")
            loaded, _ = tags.load(games.GAME, temp, (synth.HOME_NAME, synth.AWAY_NAME))
            records["interior_whitespace"] = {"normalised_code": loaded[0]["code"],
                "phase_polarity": tags.prior_polarity(loaded[0]["code"])}
            path.write_text(raw.format("BUILD UP", "0.4"), encoding="utf-8")
            loaded, _ = tags.load(games.GAME, temp, (synth.HOME_NAME, synth.AWAY_NAME))
            records["zero_length_interval"] = {"loaded_start": loaded[0]["start"], "loaded_end": loaded[0]["end"]}
            path.write_text("<broken", encoding="utf-8")
            try:
                tags.load(games.GAME, temp, (synth.HOME_NAME, synth.AWAY_NAME))
            except ET.ParseError:
                records["malformed_xml"] = "ParseError propagates; missing-file fallback does not cover malformed XML"

    ctx = {"n": 40, "first": 0, "confident": np.ones(40, bool),
           "c_home": np.r_[np.ones(20), np.zeros(20)], "c_away": np.r_[np.zeros(20), np.ones(20)]}
    event = dict(code="build up", side=HOME, start=0, end=40, type="")
    single = pipeline.calibrate_tag_codes([event], [ctx], cfg)
    repeated = pipeline.calibrate_tag_codes([event] * 3, [ctx], cfg)
    records["duplicate_calibration_coverage"] = {
        "unique_confident_frames": 40, "single": single["build up"], "tripled": repeated["build up"],
        "max_signal_change": float(np.max(np.abs(evidence.tag_team_llr(ctx, [event], single, cfg)
                                                  - evidence.tag_team_llr(ctx, [event] * 3, repeated, cfg))))}
    return records


def audit():
    rows = []
    for seed in SEEDS:
        with tempfile.TemporaryDirectory(prefix="issue20-synthetic-") as temp:
            directory = Path(temp)
            with redirect_stdout(io.StringIO()):
                synth.main(["--out-dir", temp, "--seed", str(seed), "--minutes", "3"])
            reference = directory / "synthetic_gt.csv"
            truth_sha = sha(reference)
            truth = pm.label_codes(pm.read_label_csv(str(reference)))
            reference.unlink()  # Evaluator-only reference is absent from inference inputs.
            assets = games.asset_paths(data_dir=temp)
            paths = {key: Path(assets[key]) for key in ("atd_meta", "atd_raw", "smart_tagging")}
            xml_path = paths["smart_tagging"]
            original_xml = xml_path.read_bytes()
            original_input = input_identity(paths)
            for condition in CONDITIONS:
                changed = mutate_xml(original_xml, condition)
                if changed is None:
                    xml_path.unlink(missing_ok=True)
                else:
                    xml_path.write_bytes(changed)
                identity = input_identity(paths)
                loaded, note = tags.load(games.GAME, temp, (synth.HOME_NAME, synth.AWAY_NAME))
                outputs, runs = [], []
                for enabled in (0, 1):
                    before = input_identity(paths)
                    predicted, record = run_candidate(directory, directory / "predicted.csv", enabled, truth)
                    if input_identity(paths) != before or before != identity:
                        raise RuntimeError("Paired inference changed its inputs")
                    if condition == "original":
                        _, repeat = run_candidate(directory, directory / "repeated.csv", enabled, truth)
                        record["repeat_sha256"] = repeat["csv_sha256"]
                        if record["csv_sha256"] != repeat["csv_sha256"]:
                            raise RuntimeError("Synthetic CSV did not reproduce")
                    outputs.append(predicted)
                    runs.append(record)
                scored = truth != 3
                row = {"seed": seed, "condition": condition, "input_sha256": identity,
                       "original_tracking_sha256": {key: original_input[key] for key in ("atd_meta", "atd_raw")},
                       "reference_sha256": truth_sha, "scored_frames": int(scored.sum()),
                       "phase_events": sum(bool(tags.prior_polarity(event["code"])) for event in loaded),
                       "setpiece_events": sum(event["code"] == "set pieces" for event in loaded),
                       "missing_file_reported": note is not None, "runs": runs,
                       "delta_spellF1": runs[1]["spellF1"] - runs[0]["spellF1"],
                       "delta_macroF1": runs[1]["macroF1"] - runs[0]["macroF1"],
                       "changed_scored_frames": int(np.sum((outputs[0] != outputs[1]) & scored))}
                if condition in ("missing-file", "empty-file") and not np.array_equal(*outputs):
                    raise RuntimeError("Absent tags unexpectedly changed phase-toggle output")
                rows.append(row)
                print("seed {} / {}: delta spellF1 {:+.6f}, changed scored frames {}".format(
                    seed, condition, row["delta_spellF1"], row["changed_scored_frames"]), flush=True)
    return rows


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("The report destination must be new")
    diagnostics = format_diagnostics()
    rows = audit()
    root = Path(__file__).resolve().parents[1]
    sources = [Path(__file__), root / "tests/test_smart_tagging.py", root / "starter/load_smart_tagging.py"]
    sources += sorted((root / "solution/a_dfl").glob("*.py"))
    report = {"scope": "synthetic phase-prior development audit; no adoption decision", "seeds": list(SEEDS),
              "conditions": list(CONDITIONS), "minutes_per_half": 3, "model": "candidate_a_dfl",
              "version": __version__, "identity": source_identity(),
              "extra_source_sha256": {path.relative_to(root).as_posix(): sha(path) for path in sources},
              "protocol_sha256_before_results": sha(root / "docs/experimentos/ISSUE_20_SMART_TAGGING.md"),
              "ablation": {"only_configuration_difference": "tag.enabled", "dead.setpiece_enabled": 1, "p2.enabled": 0},
              "format_diagnostics": diagnostics, "rows": rows,
              "limitations": ["Generated phase events are correlated with the invented reference, not independently labelled.",
                              "No challenge inputs or public/private challenge GT; no reserved DFL inference or tuning.",
                              "Other per-match calibrations are inherited; phase-off retains set-piece evidence."]}
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, allow_nan=False)
    print("Recorded 21 paired conditions and six deterministic repeat checks; inspect limitations and parser diagnostics.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
