"""GTT container entry point: validates, evaluates, compares with baseline_smooth50 and records.

    evaluar  [--resultados DIR] [--bootstrap N]   scores the CSVs in DIR (by default, the public baselines)
    baseline [--repetir] [--bootstrap N]          regenerates the baselines from local data, checks that
                                                  they match the published ones and evaluates them
    modelo --config JSON [--data-dir DIR]       generates, validates, evaluates and records a model

Uses the official scripts (evaluation/validate_submission.py and evaluation/run_evaluation.py): it
reimplements no metric. Each run writes to <salidas>/<id>/ and appends a line to
<salidas>/runs.jsonl with the commit, the configuration, the hash of each CSV and the aggregate metrics.

Exit codes: 0 ok · 1 unexpected error · 2 invalid or missing CSV · 3 match data missing ·
4 reproduction differs · 5 low quality, only with --exigir-referencia.
By default a low score is recorded as a warning, not as a technical error.

(The subcommands, flags and output names stay in Spanish: they are part of the interface.)

Guide: docs/DOCKER.md
"""

import argparse
import glob
import hashlib
import json
import os
import platform
import shutil
import subprocess
import sys
import time
import traceback
from contextlib import contextmanager
from datetime import datetime, timezone
from uuid import uuid4

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import games  # noqa: E402  (official challenge constants and paths)
from solution.predict import load_config, nonnegative_integer  # noqa: E402

PUBLIC_RESULTS = os.path.join(ROOT, "evaluation", "results")
REFERENCE = "baseline_smooth50"
# In the public window (5 min) the GT has 17 possessions of 14.2 s on average (evaluation/gt/*_meta.json)
SPLIT = "public-5min"

OK, ERROR, INVALID, NO_DATA, NOT_REPRODUCIBLE, LOW_QUALITY = 0, 1, 2, 3, 4, 5


class Stop(Exception):
    """Expected failure with its exit code and a readable message."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def outputs_dir():
    # In Docker, compose mounts ./salidas at /salidas and sets GTT_SALIDAS; outside it, the repo's ./salidas
    return os.environ.get("GTT_SALIDAS") or os.path.join(ROOT, "salidas")


def sha256(path):
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def git_info():
    def git(*args):
        return subprocess.run(["git", "-C", ROOT] + list(args), capture_output=True, text=True, check=True).stdout.strip()

    try:
        return {"commit": git("rev-parse", "HEAD"), "cambios_sin_commitear": bool(git("status", "--porcelain"))}
    except (OSError, subprocess.CalledProcessError):
        return {"commit": None, "cambios_sin_commitear": None}


def environment():
    versions = {"python": platform.python_version(), "platform": platform.platform(),
                "requirements_sha256": sha256(os.path.join(ROOT, "docker", "requirements.lock"))}
    for name in ("numpy", "pandas"):
        try:
            versions[name] = __import__(name).__version__
        except ImportError:
            versions[name] = None
    return versions


def run(cmd, log_path, env=None):
    """Runs an official script, showing its output and saving it to log_path. Returns the exit code."""
    child_env = dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8")
    if env:
        child_env.update(env)
    with open(log_path, "w", encoding="utf-8") as log:
        process = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, encoding="utf-8", env=child_env)
        for line in process.stdout:
            sys.stdout.write(line)
            log.write(line)
        return process.wait()


def validate(path):
    """(valid, reason) according to the official validator: the same checks as the scorer."""
    script = os.path.join(ROOT, "evaluation", "validate_submission.py")
    done = subprocess.run([sys.executable, script, path], cwd=ROOT, capture_output=True, text=True,
                          encoding="utf-8", env=dict(os.environ, PYTHONUTF8="1", PYTHONIOENCODING="utf-8"))
    lines = [line.strip() for line in (done.stdout + done.stderr).splitlines() if line.strip()]
    # The validator prints "FAIL  <file>" and the specific reason on the next line
    fail = next((i for i, line in enumerate(lines) if line.startswith("FAIL")), None)
    if fail is not None and fail + 1 < len(lines):
        return False, lines[fail + 1]
    return done.returncode == 0, (lines[-1] if lines and done.returncode != 0 else "")


def metrics(report_path):
    with open(report_path, encoding="utf-8") as handle:
        report = json.load(handle)
    return {
        "spellF1": report["spell_f1_mean"],
        "macroF1": report["macro_f1"],
        "posesiones": report["n_pred_spells"],
        "duracion_media_s": report["mean_spell_duration_s"],
        "posesiones_gt": report["n_gt_spells"],
        "duracion_media_gt_s": report["gt_mean_spell_duration_s"],
        "fragmentacion": report["fragmentation"],
        "abstenciones_en_frames_puntuados": report["n_abstain_on_graded"],
    }


def below_reference(entries):
    """Our own CSVs below the reference; only the published hashes identify references."""
    reference = next((e["metricas"]["spellF1"] for e in entries if e["nombre"] == REFERENCE and e.get("metricas")), None)
    if reference is None:
        return []
    return [e["nombre"] for e in entries
            if e.get("metricas") and not e.get("referencia", False) and e["metricas"]["spellF1"] < reference]


def comparison(entries):
    """Markdown table against baseline_smooth50, on the same split."""
    reference = next((e["metricas"] for e in entries if e["nombre"] == REFERENCE and e.get("metricas")), None)
    gt = next((e["metricas"] for e in entries if e.get("metricas")), None)
    rows = [
        "| CSV | spellF1 | Δ vs smooth50 | macroF1 | posesiones | duración media (s) | sha256 |",
        "|---|---|---|---|---|---|---|",
    ]
    low = set(below_reference(entries))
    for e in entries:
        m = e.get("metricas")
        if not m:
            rows.append("| {} | Sin métricas: {} | | | | | `{}` |".format(e["nombre"], e.get("motivo", "error de evaluación"), e["sha256"][:12]))
            continue
        delta = "{:+.4f}".format(m["spellF1"] - reference["spellF1"]) if reference else "—"
        if e["nombre"] in low:
            delta += " ⚠️"
        rows.append("| {} | {:.4f} | {} | {:.4f} | {} | {:.1f} | `{}` |".format(
            e["nombre"], m["spellF1"], delta, m["macroF1"], m["posesiones"], m["duracion_media_s"], e["sha256"][:12]))
    notes = [
        "",
        "- **Split:** ventana pública de 5 min ({}). No es comparable con el 0,2433 del partido completo.".format(SPLIT),
    ]
    if gt:
        notes.append("- **GT de la ventana:** {} posesiones, {:.1f} s de media.".format(gt["posesiones_gt"], gt["duracion_media_gt_s"]))
    notes += [
        "- **X:** el evaluador oficial rellena cada `X` con la última etiqueta no-X de la misma parte (forward-fill)"
        " antes de contar posesiones; un `X` en un frame puntuado cuenta como fallo en macroF1.",
        "- Diferencias de spellF1 por debajo de ~0,06 en esta ventana son una sola posesión: usa `--bootstrap 1000`.",
    ]
    return "\n".join(rows + notes) + "\n"


def evaluate(source_dir, out, bootstrap, require_reference=False):
    """Validates and scores every CSV in source_dir (plus the reference) into out/. Returns (entries, code)."""
    csvs = sorted(glob.glob(os.path.join(source_dir, "*.csv")))
    if not csvs:
        raise Stop(INVALID, "No hay ningún .csv en {}".format(source_dir))

    # A copy is scored: the record describes exactly the files evaluated
    results = os.path.join(out, "results")
    os.makedirs(results, exist_ok=True)
    for path in csvs:
        name = os.path.basename(path)
        published = os.path.join(PUBLIC_RESULTS, name)
        if name == REFERENCE + ".csv" and sha256(path) != sha256(published):
            raise Stop(INVALID, "El nombre baseline_smooth50 está reservado a la referencia publicada")
        if os.path.abspath(os.path.dirname(path)) != os.path.abspath(results):
            shutil.copy2(path, results)
    if not os.path.exists(os.path.join(results, REFERENCE + ".csv")):
        shutil.copy2(os.path.join(PUBLIC_RESULTS, REFERENCE + ".csv"), results)

    entries = []
    for path in sorted(glob.glob(os.path.join(results, "*.csv"))):
        name = os.path.splitext(os.path.basename(path))[0]
        valid, reason = validate(path)
        published = os.path.join(PUBLIC_RESULTS, name + ".csv")
        entry = {"nombre": name, "sha256": sha256(path), "valido": valid,
                 "referencia": os.path.isfile(published) and sha256(path) == sha256(published)}
        if not valid:
            entry["motivo"] = reason
        entries.append(entry)
        print("{} {:<28} {}".format("✓" if valid else "✗", name, "" if valid else reason))
    print()

    code = run([sys.executable, os.path.join(ROOT, "evaluation", "run_evaluation.py"),
                "--gt", "public", "--results", results, "--out", out, "--bootstrap", str(bootstrap), "--no-detail"],
               os.path.join(out, "evaluacion.log"))
    for entry in entries:
        report = os.path.join(out, "reports", entry["nombre"] + ".json")
        if entry["valido"] and os.path.exists(report):
            entry["metricas"] = metrics(report)

    table = comparison(entries)
    with open(os.path.join(out, "comparacion.md"), "w", encoding="utf-8") as handle:
        handle.write("# Comparación con {}\n\n{}".format(REFERENCE, table))
    print("\n" + table)

    if not all(e["valido"] for e in entries):
        return entries, INVALID
    if code != 0 or any(not e.get("metricas") for e in entries):
        return entries, ERROR
    low = below_reference(entries)
    if low:
        print("⚠️  Por debajo de {} en spellF1 (calidad baja): {}".format(REFERENCE, ", ".join(low)))
        if require_reference:
            return entries, LOW_QUALITY
    return entries, OK


def regenerate_baseline(out):
    """Ejecuta starter/baseline.py en out/. Devuelve {nombre: sha256}."""
    os.makedirs(out, exist_ok=True)
    code = run([sys.executable, os.path.join(ROOT, "starter", "baseline.py"), "--out", out], os.path.join(out, "baseline.log"))
    if code != 0:
        raise Stop(ERROR, "starter/baseline.py terminó con código {} (ver {}/baseline.log)".format(code, out))
    return {os.path.splitext(os.path.basename(p))[0]: sha256(p) for p in sorted(glob.glob(os.path.join(out, "*.csv")))}


def cmd_evaluar(args, out, record):
    source = args.resultados or PUBLIC_RESULTS
    record["config"] = {"resultados": os.path.relpath(source, ROOT) if source.startswith(ROOT) else source, "bootstrap": args.bootstrap}
    entries, code = evaluate(source, out, args.bootstrap, args.exigir_referencia)
    record["csv"] = entries
    record["por_debajo_de_referencia"] = below_reference(entries)
    return code


def cmd_baseline(args, out, record):
    record["config"] = {"bootstrap": args.bootstrap, "repetir": args.repetir}
    record.update(modelo="baseline_all", seed=None, seed_applied=False)
    try:
        games.require(["atd_meta", "atd_raw"])
        record["inputs"] = input_manifest(games.DATA_DIR, ["atd_meta", "atd_raw"])
    except (IOError, OSError) as err:
        raise Stop(NO_DATA, "Faltan los datos del partido.\n{}\n\nCon Docker, indica la carpeta en DATOS (ver docs/DOCKER.md).".format(err))

    results = os.path.join(out, "results")
    first = regenerate_baseline(results)
    published = {os.path.splitext(os.path.basename(p))[0]: sha256(p) for p in glob.glob(os.path.join(PUBLIC_RESULTS, "baseline_*.csv"))}
    record["coincide_con_publicados"] = {name: first[name] == published.get(name) for name in first}

    code = OK if all(record["coincide_con_publicados"].values()) else NOT_REPRODUCIBLE
    if args.repetir:
        second = regenerate_baseline(os.path.join(out, "repeticion"))
        record["determinista"] = first == second
        if first != second:
            code = NOT_REPRODUCIBLE

    entries, eval_code = evaluate(results, out, args.bootstrap)
    record["csv"] = entries

    print("Reproducción del baseline publicado:")
    for name, same in sorted(record["coincide_con_publicados"].items()):
        print("  {} {}".format("✓ idéntico a" if same else "✗ distinto de", "evaluation/results/{}.csv".format(name)))
    if args.repetir:
        print("Determinismo (dos ejecuciones): {}".format("✓ mismos hashes" if record["determinista"] else "✗ hashes distintos"))
    return code if code != OK else eval_code


def input_manifest(data_dir, required):
    """Identifies the files used without reading GT or publishing data; it stays in the local record."""
    if not required:
        return []
    paths = games.require(required, data_dir=data_dir)
    return [{"asset": name, "sha256": sha256(path), "bytes": os.path.getsize(path)}
            for name, path in zip(required, paths)]


def cmd_modelo(args, out, record):
    config = load_config(args.config)
    config_path = os.path.join(out, "config.json")
    atomic_json(config_path, config)
    record.update(config=config, config_sha256=sha256(config_path), modelo=config["model"],
                  seed=config["seed"], seed_applied=False if config["model"] != "module" else None)
    required = ["atd_meta", "atd_raw"] if config["model"] in ("baseline", "baseline_hold", "baseline_dead_ball", "temporal_control") else []
    if config["model"] == "baseline_dead_ball" and config["parameters"]["enabled"]:
        required.append("smart_tagging")
    if config["model"] == "temporal_control" and config["parameters"]["p2_enabled"]:
        required.append("smart_tagging")
    if config["model"] == "baseline_dead_ball":
        record["model_sources"] = {name: sha256(os.path.join(ROOT, name)) for name in
                                   ("solution/dead_ball.py", "solution/hold.py", "solution/predict.py", "games.py")}
    if config["model"] == "temporal_control":
        record["model_sources"] = {name: sha256(os.path.join(ROOT, name)) for name in
            ("solution/temporal_control.py", "solution/dead_ball.py", "solution/hold.py",
             "solution/predict.py", "solution/contract.py", "starter/load_smart_tagging.py", "games.py")}
    if config["model"] == "module":
        # It isn't possible to deduce which sources an external candidate uses; identify the available
        # bundle and make explicit that what it actually reads depends on its implementation.
        required = [name for name, path in games.asset_paths(data_dir=args.data_dir).items()
                    if os.path.isfile(path)]
        record["inputs_scope"] = "available-bundle; candidate must document consumed assets"
    try:
        record["inputs"] = input_manifest(args.data_dir, required)
    except (OSError, IOError) as error:
        raise Stop(NO_DATA, str(error)) from error
    results = os.path.join(out, "results")
    os.makedirs(results)
    def generate(destination, log):
        code = run([sys.executable, "-m", "solution.predict", "--config", config_path,
                    "--data-dir", args.data_dir, "--out", destination], log,
                   env={"MTAH_DATA_DIR": args.data_dir})
        if code:
            raise Stop(ERROR, "Falló el generador; consultar generacion.log")
    output = os.path.join(results, "candidato.csv")
    generate(output, os.path.join(out, "generacion.log"))
    diagnostics = os.path.splitext(output)[0] + ".diagnostics.json"
    if os.path.isfile(diagnostics):
        with open(diagnostics, encoding="utf-8") as handle:
            record["diagnostics"] = json.load(handle)
    if args.repetir:
        repeated = os.path.join(out, "repeticion", "candidato.csv")
        generate(repeated, os.path.join(out, "repeticion.log"))
        record["determinista"] = sha256(output) == sha256(repeated)
    entries, code = evaluate(results, out, config["evaluation"]["bootstrap"], args.exigir_referencia)
    record["csv"] = entries
    record["por_debajo_de_referencia"] = below_reference(entries)
    if record.get("determinista") is False:
        return NOT_REPRODUCIBLE
    return code


def atomic_json(path, value):
    temporary = str(path) + "." + uuid4().hex + ".tmp"
    try:
        with open(temporary, "x", encoding="utf-8") as handle:
            json.dump(value, handle, indent=2, ensure_ascii=False, allow_nan=False)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


@contextmanager
def index_lock(directory):
    """Inter-process lock; run.json remains the source of truth."""
    with open(os.path.join(directory, ".runs.lock"), "a+b") as handle:
        handle.seek(0, os.SEEK_END)
        if handle.tell() == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        if os.name == "nt":
            import msvcrt
            msvcrt.locking(handle.fileno(), msvcrt.LK_LOCK, 1)
        else:
            import fcntl
            fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Codes: 0 ok · 1 error · 2 invalid CSV · 3 missing data · 4 not reproducible · 5 optional quality check")
    sub = parser.add_subparsers(dest="modo", required=True)
    evaluar = sub.add_parser("evaluar", help="validates and scores CSVs against the public GT")
    evaluar.add_argument("--resultados", help="folder with the CSVs (by default, evaluation/results)")
    evaluar.add_argument("--bootstrap", type=int, default=0, help="block bootstrap resamples (0 = no interval)")
    evaluar.add_argument("--exigir-referencia", action="store_true", help="fail with 5 if the public score gets worse; it doesn't select models")
    baseline = sub.add_parser("baseline", help="regenerates the baselines from local data and evaluates them")
    baseline.add_argument("--repetir", action="store_true", help="runs it twice and checks that it gives the same CSV")
    baseline.add_argument("--bootstrap", type=int, default=0, help="block bootstrap resamples (0 = no interval)")
    modelo = sub.add_parser("modelo", help="generates from a configuration, validates, evaluates and records")
    modelo.add_argument("--config", required=True)
    modelo.add_argument("--data-dir", default=games.DATA_DIR)
    modelo.add_argument("--repetir", action="store_true")
    modelo.add_argument("--exigir-referencia", action="store_true")
    args = parser.parse_args(argv)

    started = time.time()
    now = datetime.now(timezone.utc)
    run_id = "{}-{}-{}".format(now.strftime("%Y%m%dT%H%M%S.%fZ"), uuid4().hex[:12], args.modo)
    out = os.path.abspath(os.path.join(outputs_dir(), run_id))
    os.makedirs(out, exist_ok=False)
    record = {"id": run_id, "fecha": now.isoformat(timespec="seconds"), "modo": args.modo, "split": SPLIT,
              **git_info(), "entorno": environment(), "schema_version": "1.0", "contract_version": "1.0",
              "modelo": "precomputed", "seed": None, "seed_applied": None}
    if record["cambios_sin_commitear"]:
        print("⚠️  Hay cambios sin commitear: este resultado no se podrá reproducir desde un commit.\n")

    try:
        gt_path = os.path.join(ROOT, "evaluation", "gt", games.GAME + "_possession_gt_public.csv")
        record["evaluacion"] = {"split": SPLIT, "ground_truth_sha256": sha256(gt_path),
                               "scripts": {name: sha256(os.path.join(ROOT, "evaluation", name))
                                           for name in ("run_evaluation.py", "possession_metrics.py", "validate_submission.py")}}
        if args.modo != "modelo":
            nonnegative_integer(args.bootstrap, "bootstrap")
        else:
            args.data_dir = os.path.abspath(args.data_dir)
        commands = {"evaluar": cmd_evaluar, "baseline": cmd_baseline, "modelo": cmd_modelo}
        code = commands[args.modo](args, out, record)
    except Stop as stop:
        print("\n✗ " + str(stop), file=sys.stderr)
        code = stop.code
        record["error"] = str(stop).splitlines()[0]
    except Exception as error:
        code = ERROR
        record["error"] = "{}: {}".format(type(error).__name__, error)
        print(record["error"], file=sys.stderr)
        with open(os.path.join(out, "error.log"), "w", encoding="utf-8") as handle:
            traceback.print_exc(file=handle)

    record["duracion_s"] = round(time.time() - started, 1)
    record["codigo_salida"] = code
    record["fecha_fin"] = datetime.now(timezone.utc).isoformat()
    record["estado"] = "ok" if code == OK else "error"
    try:
        atomic_json(os.path.join(out, "run.json"), record)
        with index_lock(os.path.dirname(out)):
            with open(os.path.join(os.path.dirname(out), "runs.jsonl"), "a", encoding="utf-8") as handle:
                handle.write(json.dumps(record, ensure_ascii=False, allow_nan=False) + "\n")
    except (OSError, ValueError) as error:
        print("No se pudo guardar el registro: {}".format(error), file=sys.stderr)
        return ERROR
    print("\nResultados en {} · registro en runs.jsonl · código {}".format(os.path.relpath(out, outputs_dir()) if out.startswith(outputs_dir()) else out, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
