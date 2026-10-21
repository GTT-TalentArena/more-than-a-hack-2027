"""Punto de entrada del contenedor de GTT: valida, evalúa, compara con baseline_smooth50 y registra.

    evaluar  [--resultados DIR] [--bootstrap N]   puntúa los CSV de DIR (por defecto, los baselines públicos)
    baseline [--repetir] [--bootstrap N]          regenera los baselines desde los datos locales, comprueba
                                                  que coinciden con los publicados y los evalúa

Usa los scripts oficiales (evaluation/validate_submission.py y evaluation/run_evaluation.py): no
reimplementa ninguna métrica. Cada ejecución escribe en <salidas>/<id>/ y añade una línea a
<salidas>/runs.jsonl con el commit, la configuración, el hash de cada CSV y las métricas agregadas.

Códigos de salida: 0 bien · 1 error inesperado · 2 CSV inválido o ausente · 3 faltan los datos del
partido · 4 dos ejecuciones iguales no dan el mismo CSV · 5 algún CSV propio queda por debajo de
baseline_smooth50 (calidad baja; los baseline_* no cuentan, son la referencia).

Guía: docs/DOCKER.md
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
from datetime import datetime, timezone

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import games  # noqa: E402  (constantes y rutas oficiales del reto)

PUBLIC_RESULTS = os.path.join(ROOT, "evaluation", "results")
REFERENCE = "baseline_smooth50"
# En la ventana pública (5 min) el GT tiene 17 posesiones de 14,2 s de media (evaluation/gt/*_meta.json)
SPLIT = "public-5min"

OK, ERROR, INVALID, NO_DATA, NOT_REPRODUCIBLE, LOW_QUALITY = 0, 1, 2, 3, 4, 5


class Stop(Exception):
    """Fallo esperado con su código de salida y un mensaje legible."""

    def __init__(self, code, message):
        super().__init__(message)
        self.code = code


def outputs_dir():
    # En Docker, compose monta ./salidas en /salidas y fija GTT_SALIDAS; fuera, ./salidas del repo
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
    versions = {"python": platform.python_version()}
    for name in ("numpy", "pandas"):
        try:
            versions[name] = __import__(name).__version__
        except ImportError:
            versions[name] = None
    return versions


def run(cmd, log_path):
    """Ejecuta un script oficial mostrando su salida y guardándola en log_path. Devuelve el código."""
    with open(log_path, "w") as log:
        process = subprocess.Popen(cmd, cwd=ROOT, stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        for line in process.stdout:
            sys.stdout.write(line)
            log.write(line)
        return process.wait()


def validate(path):
    """(válido, motivo) según el validador oficial: mismas comprobaciones que el scorer."""
    script = os.path.join(ROOT, "evaluation", "validate_submission.py")
    done = subprocess.run([sys.executable, script, path], cwd=ROOT, capture_output=True, text=True)
    lines = [line.strip() for line in (done.stdout + done.stderr).splitlines() if line.strip()]
    # El validador imprime «FAIL  <fichero>» y en la línea siguiente el motivo concreto
    fail = next((i for i, line in enumerate(lines) if line.startswith("FAIL")), None)
    if fail is not None and fail + 1 < len(lines):
        return False, lines[fail + 1]
    return done.returncode == 0, (lines[-1] if lines and done.returncode != 0 else "")


def metrics(report_path):
    with open(report_path) as handle:
        report = json.load(handle)
    return {
        "spellF1": report["spell_f1_mean"],
        "macroF1": report["macro_f1"],
        "posesiones": report["n_pred_spells"],
        "duracion_media_s": report["mean_spell_duration_s"],
        "posesiones_gt": report["n_gt_spells"],
        "duracion_media_gt_s": report["gt_mean_spell_duration_s"],
    }


def below_reference(entries):
    """CSV propios válidos con menos spellF1 que la referencia. Los baseline_* son la referencia: no cuentan."""
    reference = next((e["metricas"]["spellF1"] for e in entries if e["nombre"] == REFERENCE and e.get("metricas")), None)
    if reference is None:
        return []
    return [e["nombre"] for e in entries
            if e.get("metricas") and not e["nombre"].startswith("baseline_") and e["metricas"]["spellF1"] < reference]


def comparison(entries):
    """Tabla Markdown contra baseline_smooth50, en el mismo split."""
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
            rows.append("| {} | ❌ inválido: {} | | | | | `{}` |".format(e["nombre"], e.get("motivo", ""), e["sha256"][:12]))
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


def evaluate(source_dir, out, bootstrap):
    """Valida y puntúa todos los CSV de source_dir (más la referencia) en out/. Devuelve (entradas, código)."""
    csvs = sorted(glob.glob(os.path.join(source_dir, "*.csv")))
    if not csvs:
        raise Stop(INVALID, "No hay ningún .csv en {}".format(source_dir))

    # Se puntúa una copia: el registro describe exactamente los ficheros evaluados
    results = os.path.join(out, "results")
    os.makedirs(results, exist_ok=True)
    for path in csvs:
        if os.path.abspath(os.path.dirname(path)) != os.path.abspath(results):
            shutil.copy2(path, results)
    if not os.path.exists(os.path.join(results, REFERENCE + ".csv")):
        shutil.copy2(os.path.join(PUBLIC_RESULTS, REFERENCE + ".csv"), results)

    entries = []
    for path in sorted(glob.glob(os.path.join(results, "*.csv"))):
        name = os.path.splitext(os.path.basename(path))[0]
        valid, reason = validate(path)
        entry = {"nombre": name, "sha256": sha256(path), "valido": valid}
        if not valid:
            entry["motivo"] = reason
        entries.append(entry)
        print("{} {:<28} {}".format("✓" if valid else "✗", name, "" if valid else reason))
    print()

    code = run([sys.executable, os.path.join(ROOT, "evaluation", "run_evaluation.py"),
                "--results", results, "--out", out, "--bootstrap", str(bootstrap), "--no-detail"],
               os.path.join(out, "evaluacion.log"))
    for entry in entries:
        report = os.path.join(out, "reports", entry["nombre"] + ".json")
        if entry["valido"] and os.path.exists(report):
            entry["metricas"] = metrics(report)

    table = comparison(entries)
    with open(os.path.join(out, "comparacion.md"), "w") as handle:
        handle.write("# Comparación con {}\n\n{}".format(REFERENCE, table))
    print("\n" + table)

    if not all(e["valido"] for e in entries):
        return entries, INVALID
    if code != 0:
        return entries, ERROR
    low = below_reference(entries)
    if low:
        print("⚠️  Por debajo de {} en spellF1 (calidad baja): {}".format(REFERENCE, ", ".join(low)))
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
    entries, code = evaluate(source, out, args.bootstrap)
    record["csv"] = entries
    record["por_debajo_de_referencia"] = below_reference(entries)
    return code


def cmd_baseline(args, out, record):
    record["config"] = {"bootstrap": args.bootstrap, "repetir": args.repetir}
    try:
        games.require(["atd_meta", "atd_raw"])
    except (IOError, OSError) as err:
        raise Stop(NO_DATA, "Faltan los datos del partido.\n{}\n\nCon Docker, indica la carpeta en DATOS (ver docs/DOCKER.md).".format(err))

    results = os.path.join(out, "results")
    first = regenerate_baseline(results)
    published = {os.path.splitext(os.path.basename(p))[0]: sha256(p) for p in glob.glob(os.path.join(PUBLIC_RESULTS, "baseline_*.csv"))}
    record["coincide_con_publicados"] = {name: first[name] == published.get(name) for name in first}

    code = OK
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


def main():
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0], formatter_class=argparse.RawDescriptionHelpFormatter,
                                     epilog="Códigos de salida: 0 bien · 1 error · 2 CSV inválido · 3 faltan datos · 4 no reproducible · 5 por debajo de smooth50")
    sub = parser.add_subparsers(dest="modo", required=True)
    evaluar = sub.add_parser("evaluar", help="valida y puntúa CSV contra el GT público")
    evaluar.add_argument("--resultados", help="carpeta con los CSV (por defecto, evaluation/results)")
    evaluar.add_argument("--bootstrap", type=int, default=0, help="remuestreos bootstrap por bloques (0 = sin intervalo)")
    baseline = sub.add_parser("baseline", help="regenera los baselines desde los datos locales y los evalúa")
    baseline.add_argument("--repetir", action="store_true", help="lo ejecuta dos veces y comprueba que da el mismo CSV")
    baseline.add_argument("--bootstrap", type=int, default=0, help="remuestreos bootstrap por bloques (0 = sin intervalo)")
    args = parser.parse_args()

    started = time.time()
    now = datetime.now(timezone.utc)
    run_id = "{}-{}".format(now.strftime("%Y%m%dT%H%M%SZ"), args.modo)
    out = os.path.join(outputs_dir(), run_id)
    os.makedirs(out, exist_ok=True)
    record = {"id": run_id, "fecha": now.isoformat(timespec="seconds"), "modo": args.modo, "split": SPLIT,
              **git_info(), "entorno": environment()}
    if record["cambios_sin_commitear"]:
        print("⚠️  Hay cambios sin commitear: este resultado no se podrá reproducir desde un commit.\n")

    try:
        code = (cmd_evaluar if args.modo == "evaluar" else cmd_baseline)(args, out, record)
    except Stop as stop:
        print("\n✗ " + str(stop), file=sys.stderr)
        code = stop.code
        record["error"] = str(stop).splitlines()[0]

    record["duracion_s"] = round(time.time() - started, 1)
    record["codigo_salida"] = code
    with open(os.path.join(out, "run.json"), "w") as handle:
        json.dump(record, handle, indent=2, ensure_ascii=False)
    with open(os.path.join(outputs_dir(), "runs.jsonl"), "a") as handle:
        handle.write(json.dumps(record, ensure_ascii=False) + "\n")
    print("\nResultados en {} · registro en runs.jsonl · código {}".format(os.path.relpath(out, outputs_dir()) if out.startswith(outputs_dir()) else out, code))
    return code


if __name__ == "__main__":
    sys.exit(main())
