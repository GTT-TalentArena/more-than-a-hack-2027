# Running P0 · Generate, validate, evaluate and record

> 🇪🇸 Translated from the Spanish original, [EJECUCION.md](EJECUCION.md). Commands, flags, file names and JSON keys stay as they are: they are part of the interface.

> Issue [#12](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/12). Contract: [CONTRATO_DATOS.en.md](CONTRATO_DATOS.en.md). Verification and closing: [P0.en.md](P0.en.md).

## 1. Where to run from

All commands start from the repo root. On Alejandro's machine:

```powershell
Set-Location "D:\amolines\Documents\AMolines\TArena\more-than-a-hack-2027"
```

Authorised data outside Git, in a folder with `tactical/`. No generator command receives ground truth. The evaluator only uses the public reference.

## 2. Docker: the team's common path

With Docker running and Compose v2:

```powershell
docker compose build
docker compose run --rm evaluar
```

This evaluates the four public baselines without downloading videos or tracking. `baseline_smooth50` should give approximately spellF1 `0.3256` and macroF1 `0.6207`. The tests check the four baselines with a tolerance of `0.0001` against the published rounded figures.

### Test the full circuit without data

```powershell
docker compose run --rm modelo modelo --config configs/smoke_constant.json --repetir
```

It generates a constant D label for the whole video, validates, evaluates, repeats and records. It is a **deliberately useless test model**, not a competition candidate. Its poor score produces a warning, not a technical error.

### Generate the baseline with real local data

Replace this example path with the real authorised folder:

```powershell
$env:DATOS = "D:/data/mtah2027"
docker compose run --rm modelo modelo --config configs/baseline_smooth50.json --repetir
```

`window: 50` means ±50-frame smoothing. The configurable baseline mode reuses the official algorithm, including its limitation of reading absences as D; it is not the P1 solution.

To regenerate all four and compare with the published ones:

```powershell
docker compose run --rm baseline baseline --repetir
```

Byte differences from the published ones give code 4. If only CRLF/LF changes, diagnose it by comparing labels; don't hide the difference. Don't edit the public CSVs to make the test pass.

### Evaluate CSVs delivered by teammates

Store the CSVs only in `salidas/mis-csv/`:

```powershell
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv --bootstrap 1000
```

An invalid CSV makes the whole set fail, even if others are valid. A low metric is recorded. To explicitly enable the old quality check:

```powershell
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv --exigir-referencia
```

Don't use this check to choose the A/B winner: the public window has only 17 possessions. Also respect the evaluation budget of protocol #26.

## 3. Python without Docker

Python 3.11 is recommended to match the image; install the dependencies in a local environment:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r docker/requirements.lock
.\.venv\Scripts\python.exe docker/pipeline.py evaluar
.\.venv\Scripts\python.exe docker/pipeline.py modelo --config configs/smoke_constant.json --repetir
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

There's no need to activate the environment or change PowerShell policies. If `py` doesn't exist, use the path of the installed Python. The delivery was also checked with the local runtime listed in [P0.en.md](P0.en.md); that doesn't replace the pending run in Docker.

With local data:

```powershell
.\.venv\Scripts\python.exe docker/pipeline.py modelo `
  --config configs/baseline_smooth50.json `
  --data-dir "D:/data/mtah2027" --repetir
```

Validate without evaluating:

```powershell
.\.venv\Scripts\python.exe evaluation/validate_submission.py salidas/mis-csv/candidato.csv
```

## 4. Configuration and new models

Configurations are validated strictly; ignored options aren't allowed. Minimal example:

```json
{
  "contract_version": "1.0",
  "model": "baseline",
  "parameters": {"window": 50},
  "seed": 0,
  "evaluation": {"split": "public-5min", "bootstrap": 0}
}
```

Available models: `baseline`, `baseline_hold` (P1), `baseline_dead_ball` (experimental P2 consumer), `temporal_control` (confirmed control and experimental H/A/D decoding), `constant` (tests only) and `module`. P1 uses `configs/baseline_hold.json`; diagnostics, the no-hold variant and limits in [P1_HOLD.en.md](experimentos/P1_HOLD.en.md). P2 uses `configs/baseline_dead_ball.json` and its `_disabled` variant; rules and limits in [P2_DEAD_BALL.en.md](experimentos/P2_DEAD_BALL.en.md). The new consumer uses `configs/temporal_control.json` and its `_no_p2` variant; hypotheses and results in [CONTROL_TEMPORAL.en.md](experimentos/CONTROL_TEMPORAL.en.md). For a candidate that follows the existing brief, configure:

```json
{
  "contract_version": "1.0",
  "model": "module",
  "parameters": {"module": "solution.candidate_a"},
  "seed": 0,
  "evaluation": {"split": "public-5min", "bootstrap": 0}
}
```

The name is an example: the module must exist before you use it. The adapter calls `python -m solution.candidate_a --out <csv>` without changing its interface. The data location is passed through `MTAH_DATA_DIR`. The seed isn't injected: `seed_applied: null` means the candidate must declare it. For baseline/constant `false` is recorded, because they don't need it. Don't claim an option was applied if the module doesn't consume it.

Don't open or merge A/B approaches before the freeze. For new internal models, extend the adapter and its tests; follow the signal contract without changing the official metrics.

## 5. Outputs and reproducibility

Each run creates an exclusive folder under `salidas/` with the UTC date, a UUID and the mode:

| File | Contents |
|---|---|
| `config.json` | Effective configuration in model mode |
| `results/` | Exact copy of the evaluated predictions and the reference |
| `run.json` | Commit, pending changes, environment, configuration, hashes, metrics, duration and status |
| `comparacion.md` | Aggregate summary against smooth50 |
| `scoreboard.csv`, `reports/` | Official reports; they may include restricted detail |
| `*.log` | Generation, evaluation, repetition or error |

`runs.jsonl` is appended under an inter-process lock; the individual `run.json` is the source of truth. The record is also saved on controlled failures and run exceptions. If writing it fails, the process returns an error. There is no guarantee against a power cut or forced termination of the process.

For the baseline, the XML and ATD used are identified by hash. For external modules, the available tactical bundle is recorded; it doesn't claim to know which files their code actually consumed; the candidate must document it. The hash of the official code and of the public GT is also recorded. Paths and manifests are local.

A run with uncommitted changes is exploratory: before publishing final evidence, create the commit and repeat from a clean tree with the same environment and inputs.

## 6. Exit codes

| Code | Meaning |
|---|---|
| 0 | Technically correct run; check the warnings |
| 1 | Wrong configuration, model/evaluator error or record error |
| 2 | Invalid CSV, folder without CSVs or an attempt to impersonate the reference |
| 3 | Mandatory baseline inputs missing |
| 4 | Non-identical reproduction when it was checked |
| 5 | Low public metric, **only with `--exigir-referencia`** |

`$LASTEXITCODE` lets you check the result of the last command in PowerShell. A CLI argument error can exit before a run is created; there is no valid configuration to record yet.

## 7. Interpretation and privacy

spellF1 measures whole possessions; macroF1 classifies per frame. Use the evaluator's counts and durations. The validator without GT can count X as gaps and give different figures: the official temporal metrics fill abstentions according to their rules.

`0.2433` is the baseline's **published** result on the full private match. Don't compare it with the public `0.3256`, and don't consider the milestone reached with a new candidate without official evaluation.

Don't upload `salidas/`, data, frames, signals or predictions to GitHub or to external LLMs. Don't publish full logs or records without review either. Share only code, documentation, synthetic fixtures and permitted aggregate evidence. Check names/paths even in `comparacion.md` before sharing it.
