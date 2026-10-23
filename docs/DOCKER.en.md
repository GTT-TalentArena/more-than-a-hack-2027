# Docker: run, validate and compare reproducibly

> 🇪🇸 Translated from the Spanish original, [DOCKER.md](DOCKER.md). The commands, flags and output names (`evaluar`, `--repetir`, `salidas/`, `comparacion.md`…) stay in Spanish because they are part of the interface.

The team's common environment (issue [#24](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/24)). With a single command it:

1. **validates** each CSV with the official validator,
2. **scores** it with the official evaluator against the public GT,
3. **compares** it with `baseline_smooth50` (spellF1, macroF1, number and duration of possessions),
4. **records** the run: commit, configuration, versions, SHA-256 hash of each CSV and metrics.

It reimplements no metric: it calls `evaluation/validate_submission.py` and `evaluation/run_evaluation.py`.

> **Data rule (T&C):** the match data never goes into the image or into git. It is mounted read-only from your disk. What you generate in `salidas/` may contain predictions for the whole match: don't upload it or paste it into an LLM. Share only aggregate metrics (the `comparacion.md` table) or the traceback of an error.

## What's there

| file | what it does |
|---|---|
| `Dockerfile` | Python 3.11.17 (image pinned by digest) + `numpy`/`pandas` at exact versions (`docker/requirements.lock`) + git. **No code or data.** |
| `.dockerignore` | The build context only includes `docker/requirements.lock`; everything else stays out. |
| `compose.yaml` | Mounts the repo read-only at `/app`, the data read-only at `/datos` and `./salidas` for the results. Runs as your user, not as root. |
| `docker/pipeline.py` | Common entry point: `evaluar`, `baseline` and a configurable `modelo`. |
| `.github/workflows/docker.yml` | CI: image, public references, P0 tests and error codes. |

Since the code is mounted and not copied, **you don't need to rebuild the image when the code changes**: only when `Dockerfile` or `docker/requirements.lock` change.

## Requirements

- Docker with Compose v2 (`docker compose version`). On Windows and macOS, Docker Desktop.
- For `baseline`: the challenge data downloaded into a folder of yours, outside the repo (for example `~/mtah2027`, with `tactical/` inside).

## Usage

### 1. Build (once)

```bash
docker compose build
```

### 2. Evaluate the public CSVs (no data)

```bash
docker compose run --rm evaluar
```

It scores the four baselines in `evaluation/results/`. `baseline_smooth50` must come out with **spellF1 0.3256** and macroF1 0.6207. If you get another number, the environment is wrong.

### 3. Evaluate your CSVs

Copy your CSVs into a folder inside `salidas/` and point the pipeline at it. `baseline_smooth50` is added as the reference:

```bash
mkdir -p salidas/mis-csv && cp /path/to/GTT.csv salidas/mis-csv/
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv --bootstrap 1000   # with intervals
```

### 4. Regenerate the baseline with the match data (local only)

```bash
DATOS=~/mtah2027 docker compose run --rm baseline                       # Linux / macOS
DATOS=~/mtah2027 docker compose run --rm baseline baseline --repetir    # and check determinism
```

```powershell
$env:DATOS = "D:/data/mtah2027"; docker compose run --rm baseline     # Windows (PowerShell)
```

It regenerates the four baselines and checks:
- that they **match byte for byte** the ones published in `evaluation/results/`;
- with `--repetir`, that **two runs give the same CSV**;

and then evaluates them. Without `DATOS`, the repo's `./data` is used.

## Outputs

Each run creates `salidas/<date>-<mode>/`:

The ID includes microseconds and a random suffix to avoid overwrites. `run.json` is written atomically and `runs.jsonl` is appended under an inter-process lock.

| file | contents |
|---|---|
| `comparacion.md` | table against `baseline_smooth50`: **this is what gets shared** |
| `run.json` | the record of this run |
| `scoreboard.csv`, `reports/` | output of the official evaluator |
| `evaluacion.log`, `baseline.log` | what was printed on screen |
| `results/` | the exact CSVs that were evaluated (private) |

And one line per run in `salidas/runs.jsonl`:

```json
{"id": "20261021T164236Z-evaluar", "modo": "evaluar", "split": "public-5min",
 "commit": "b151c03…", "cambios_sin_commitear": false,
 "entorno": {"python": "3.11.17", "numpy": "2.4.6", "pandas": "3.0.6"},
 "config": {"resultados": "evaluation/results", "bootstrap": 0},
 "csv": [{"nombre": "baseline_smooth50", "sha256": "6d4e04b8…", "valido": true,
          "metricas": {"spellF1": 0.3256, "macroF1": 0.6207, "posesiones": 26, "duracion_media_s": 10.8, …}}],
 "duracion_s": 4.4, "codigo_salida": 0}
```

(Keys: `modo` = mode, `cambios_sin_commitear` = uncommitted changes, `entorno` = environment, `nombre` = name, `valido` = valid, `metricas` = metrics, `posesiones` = possessions, `duracion_media_s` = mean duration in seconds, `duracion_s` = duration, `codigo_salida` = exit code.)

`baseline` adds `coincide_con_publicados` (matches the published ones) and, with `--repetir`, `determinista` (deterministic). If there are uncommitted changes, the pipeline warns about it and records it: that result can't be reproduced from a commit.

## How to read the numbers

- **Split:** everything here is the **5-min public window** (17 possessions, 14.2 s on average). The milestone's **0.2433** is the full match, which only the organisers score: don't compare numbers from different splits.
- **`X`:** the evaluator fills each `X` with the last non-X label of the same half before counting possessions. Inside a possession it costs nothing; at a possession change it drags the old label along.
- **Noise:** in the public window, one missed possession moves spellF1 by about 6 points. Before believing an improvement, run with `--bootstrap 1000`.
- The public window is for checking **format and alignment**, not for choosing a model (see `docs/GUIA_PROYECTO.en.md`).

## Exit codes

| code | meaning |
|---|---|
| 0 | all good |
| 1 | unexpected error (traceback on screen and in the `.log` files) |
| 2 | some CSV is invalid, or there is no CSV |
| 3 | the match data is missing |
| 4 | the repetition or the exact comparison with the published baseline doesn't match |
| 5 | a valid candidate below smooth50, **only with `--exigir-referencia`**; by default it's a warning, not a technical failure |

An invalid CSV is **not** skipped silently: it appears marked ❌ in the table, with its reason, and the process exits with 2. If there are both invalid CSVs and CSVs below the reference, 2 wins.

## Common problems

- **`permission denied` in `salidas/` (Linux):** the container uses UID/GID 1000. If `id -u` gives you another number: `GTT_UID=$(id -u) GTT_GID=$(id -g) docker compose run --rm evaluar` (or export them in your `.zshrc`/`.bashrc`). Not needed on macOS and Windows.
- **`Faltan los datos del partido` (match data missing):** check that `DATOS` points to the folder containing `tactical/`, with an absolute path (`~/…` works when written like that on the command line itself).
- **Windows:** use paths with `/` in `DATOS`, and share the drive in Docker Desktop (Settings → Resources → File sharing).
- **Changing dependencies:** edit `requirements.txt`, regenerate `docker/requirements.lock` with the command in its header, and `docker compose build`.

## P0: configurable models and tests

```bash
docker compose run --rm modelo modelo --config configs/smoke_constant.json --repetir
docker compose run --rm --entrypoint python evaluar -m unittest discover -s tests -v
```

The constant configuration is only a technical test without data. For a baseline with real inputs, use `configs/baseline_smooth50.json` and set `DATOS`. See [EJECUCION.en.md](EJECUCION.en.md) for the contract for new models, records and privacy limits.

The reference is identified by the hash of the public file, not just by the name prefix. A low public metric doesn't select the winner; code 5 is an optional check. Candidates A/B keep their agreed interface.

Pending for #22: consider a final image with the code pinned to a commit, and verify it from a clean install.
