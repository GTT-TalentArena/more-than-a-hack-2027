"""Generación configurable; nunca lee ground truth."""
import argparse
import json
from pathlib import Path
import re
import subprocess
import sys

import numpy as np

import games
from solution.contract import VERSION, check_tracking_frames
from starter import baseline


def nonnegative_integer(value, name):
    if type(value) is not int or value < 0:
        raise ValueError(name + " debe ser un entero >= 0")


def load_config(path):
    with open(path, encoding="utf-8-sig") as handle:
        config = json.load(handle)
    required = {"contract_version", "model", "parameters", "seed", "evaluation"}
    if not isinstance(config, dict) or set(config) != required:
        raise ValueError("Configuración: se requieren exactamente " + ", ".join(sorted(required)))
    if config["contract_version"] != VERSION:
        raise ValueError("Versión de contrato no soportada")
    nonnegative_integer(config["seed"], "seed")
    evaluation = config["evaluation"]
    if not isinstance(evaluation, dict) or set(evaluation) != {"split", "bootstrap"}:
        raise ValueError("evaluation requiere split y bootstrap")
    if evaluation["split"] != "public-5min":
        raise ValueError("Solo se permite la evaluación pública")
    nonnegative_integer(evaluation["bootstrap"], "bootstrap")
    parameters = config["parameters"]
    if not isinstance(parameters, dict):
        raise ValueError("parameters debe ser un objeto")
    model = config["model"]
    if model == "baseline":
        if set(parameters) != {"window"}:
            raise ValueError("baseline requiere solo window")
        nonnegative_integer(parameters["window"], "window")
    elif model == "baseline_hold":
        if set(parameters) != {"max_hold_frames"}:
            raise ValueError("baseline_hold requiere solo max_hold_frames")
        nonnegative_integer(parameters["max_hold_frames"], "max_hold_frames")
    elif model == "constant":
        if set(parameters) != {"label"} or parameters["label"] not in ("H", "A", "D", "X"):
            raise ValueError("constant requiere label H/A/D/X")
    elif model == "module":
        module = parameters.get("module")
        if (set(parameters) != {"module"} or not isinstance(module, str)
                or not re.fullmatch(r"solution(?:\.[A-Za-z_]\w*)+", module)):
            raise ValueError("module requiere un módulo Python bajo solution.*")
    else:
        raise ValueError("Modelo no soportado")
    return config


def generate(config, data_dir, output):
    output = Path(output)
    if output.exists():
        raise FileExistsError("No se sobrescriben predicciones existentes")
    output.parent.mkdir(parents=True, exist_ok=True)
    model = config["model"]
    parameters = config["parameters"]
    if model == "module":
        # Contrato de #26: no se añaden flags que los candidatos no aceptan.
        subprocess.run([sys.executable, "-m", parameters["module"], "--out", str(output)],
                       cwd=Path(__file__).resolve().parents[1], check=True)
    else:
        if model == "baseline":
            raw = games.require(["atd_raw"], data_dir=str(data_dir))[0]
            check_tracking_frames(raw, games.source_frames())
            codes = baseline.build(data_dir=str(data_dir))
            labels = baseline.smooth(codes, parameters["window"])
        elif model == "baseline_hold":
            from solution.hold import build
            labels, summary = build(str(data_dir), parameters["max_hold_frames"])
            with output.with_suffix(".diagnostics.json").open("x", encoding="utf-8") as handle:
                json.dump(summary, handle, indent=2, allow_nan=False)
        else:
            labels = np.full(games.source_frames(), parameters["label"], dtype="<U1")
        baseline.write_submission(str(output), labels)
    if not output.is_file():
        raise RuntimeError("El modelo no ha generado su CSV")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", required=True)
    parser.add_argument("--data-dir", default=games.DATA_DIR)
    parser.add_argument("--out", required=True)
    args = parser.parse_args()
    generate(load_config(args.config), args.data_dir, args.out)


if __name__ == "__main__":
    main()
