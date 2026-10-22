"""Verify the controlled comparison and export only allowlisted aggregate metrics."""
import argparse
import json
from pathlib import Path


def summarize(outputs, model="baseline_dead_ball"):
    if model not in ("baseline_dead_ball", "temporal_control"):
        raise ValueError("Unsupported comparison model")
    enabled_key = "p2_enabled" if model == "temporal_control" else "enabled"
    records = []
    for path in sorted(outputs.glob("*/run.json")):
        record = json.loads(path.read_text(encoding="utf-8"))
        if record.get("modelo") == model and record.get("estado") == "ok":
            records.append((record, path.parent))
    variants = {}
    for record, folder in records:
        enabled = record["config"]["parameters"][enabled_key]
        if type(enabled) is not bool:
            raise ValueError("P2 activation must be boolean")
        variants[enabled] = (record, folder)
    if set(variants) != {False, True}:
        raise ValueError("Missing successful enabled/disabled P2 runs")
    off, on = variants[False][0], variants[True][0]
    if not off.get("model_sources") or not on.get("model_sources"):
        raise ValueError("Missing source hashes")
    for key in ("commit", "model_sources", "entorno", "evaluacion", "seed", "split"):
        if off.get(key) != on.get(key):
            raise ValueError("Comparison differs in " + key)
    configs = [json.loads(json.dumps(r["config"])) for r in (off, on)]
    for config in configs:
        del config["parameters"][enabled_key]
    if configs[0] != configs[1]:
        raise ValueError("Parameters differ beyond enabled")
    # Enabled also reads Smart Tagging; the shared ATD inputs must match exactly.
    inputs = [{i["asset"]: i for i in r["inputs"]} for r in (off, on)]
    if any(k not in inputs[0] or k not in inputs[1] or inputs[0][k] != inputs[1][k]
           for k in ("atd_meta", "atd_raw")):
        raise ValueError("Tracking inputs differ")
    result = dict(model=model, split=on["split"], controlled_comparison=True, variants={})
    for enabled, (record, folder) in variants.items():
        if record.get("determinista") is not True:
            raise ValueError("Repetition has not passed")
        candidate = next(e for e in record["csv"] if e["nombre"] == "candidato")
        if not candidate["valido"]:
            raise ValueError("Invalid candidate CSV")
        report = json.loads((folder / "reports/candidato.json").read_text(encoding="utf-8"))
        diagnostics = record["diagnostics"]
        result["variants"]["enabled" if enabled else "disabled"] = dict(
            run_id=record["id"], sha256=candidate["sha256"], deterministic=True,
            metrics=dict({k: candidate["metricas"][k] for k in
                          ("spellF1", "macroF1", "posesiones", "duracion_media_s", "posesiones_gt",
                           "duracion_media_gt_s", "fragmentacion", "abstenciones_en_frames_puntuados")
                          if k in candidate["metricas"]}, alive_dead_f1=report["alive_dead_f1"],
                         spellF1_interval_5_95=[report.get("spell_bootstrap_low"), report.get("spell_bootstrap_high")],
                         macroF1_interval_5_95=[report.get("bootstrap_low"), report.get("bootstrap_high")]),
            diagnostics={k: diagnostics[k] for k in
                         ("initial_kickoffs_refined", "second_half_pre_kickoff_dead_fraction",
                          "dead_label_frames", "abstention_frames", "restart_candidates",
                          "interruption_candidates", "conflicts", "control_evidence_frames",
                          "control_coverage_in_periods", "state_changes") if k in diagnostics})
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--outputs", type=Path, default=Path("salidas"))
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", choices=("baseline_dead_ball", "temporal_control"), default="baseline_dead_ball")
    args = parser.parse_args()
    result = summarize(args.outputs, args.model)
    with args.out.open("x", encoding="utf-8") as handle:
        json.dump(result, handle, indent=2, allow_nan=False)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
