# Commit message translations

Some commits in this repository were written in Spanish. History is not rewritten, so their hashes stay valid; this page gives the English version of each one. The same translations are attached to the commits as git notes:

```sh
git fetch origin 'refs/notes/*:refs/notes/*'
git log --notes
```

From now on, all commits, pull requests, reviews and docs are written in English (see `CONTRIBUTING.md`).

Only the Spanish parts are translated; where a squash commit has a Spanish title and an English body, only the title is listed.

| Commit | Author | Original (Spanish) | English |
| :-- | :-- | :-- | :-- |
| `c339296` | jimy | P3: la P2 como evidencia de balón muerto en el candidato A (#14, #15) (#37) | P3: P2 as dead-ball evidence in candidate A (#14, #15) (#37) |
| `de771a8` | jimy | P3/P4: decodificadores alternativos, escenarios de prueba y evidencia por frame (#15, #16) (#35) | P3/P4: alternative decoders, test scenarios and per-frame evidence (#15, #16) (#35) |
| `2335118` | jimy | Candidato A (Claude Opus 5.5): posesión por decodificación exacta H/A/D (#26) (#33) | Candidate A (Claude Opus 5.5): possession by exact H/A/D decoding (#26) (#33) |
| `88f4724` | AlejandroMolines | feat: integrar P1 baseline-hold con diagnóstico y evaluación reproducible (#32)<br>· P1, falta validacion<br>· docs: registrar resultados y limitaciones de P1 | feat: integrate P1 baseline-hold with diagnostics and reproducible evaluation (#32)<br>· P1, validation still pending<br>· docs: record P1 results and limitations |
| `0ef35cd` | amolines | docs: registrar resultados y limitaciones de P1 | docs: record P1 results and limitations |
| `606e641` | amolines | P1, falta validacion | P1, validation still pending |
| `cd62fd5` | AlejandroMolines | feat: implementar pipeline P0 y pruebas (#31)<br>· P0 issue<br>· fix(ci): activar control explícito de calidad y pruebas P0 | feat: implement the P0 pipeline and tests (#31)<br>· P0 issue<br>· fix(ci): enable explicit quality checks and P0 tests |
| `fe76e4c` | amolines | fix(ci): activar control explícito de calidad y pruebas P0 | fix(ci): enable explicit quality checks and P0 tests |
| `65569ce` | Edu Ruiz | feat(docker): código de salida 5 cuando un CSV queda por debajo de smooth50 (#30) | feat(docker): exit code 5 when a CSV falls below smooth50 (#30)<br><br>Tells a low-quality result apart from an error or an invalid CSV: our own valid CSVs with a lower spellF1 than baseline_smooth50 are flagged ⚠️ in the table, recorded in runs.jsonl, and the process exits with 5. The baseline_* files don't count (they are the reference). CI checks this.<br><br>Refs #24 |
| `c50bd23` | Edu Ruiz | feat(docker): entorno común para validar, evaluar y comparar de forma reproducible (#29) | feat(docker): a common environment to validate, evaluate and compare reproducibly (#29)<br><br>· Image with only the environment (Python 3.11.17 pinned by digest, numpy and pandas at exact versions, git); code and data are mounted read-only and the build context only includes the lock file.<br>· docker/pipeline.py: validates and scores with the official scripts, compares against baseline_smooth50 and records commit, hashes and metrics in salidas/runs.jsonl. Baseline mode: regenerates the baselines, compares them with the published ones and checks determinism (--repetir). Distinct exit codes for an invalid CSV, missing data and a non-reproducible result.<br>· CI: builds the image, evaluates the public CSVs and requires an invalid CSV to fail.<br>· Guide in docs/DOCKER.md.<br><br>Refs #24 |
| `65ee063` | Edu Ruiz | ci: no avisar en Discord de ejecuciones lanzadas desde forks (#25) | ci: don't notify Discord about runs triggered from forks (#25) |
| `7671eb9` | Edu Ruiz | ci: no avisar en Discord de ejecuciones lanzadas desde forks | ci: don't notify Discord about runs triggered from forks |
| `8b76826` | jimy | docs: estudio del modelo de posesión (#27) | docs: possession model study (#27) |
| `8fac617` | Edu Ruiz | ci: avisos de los workflows en el Discord del equipo (#11) | ci: workflow notifications in the team Discord (#11) |
| `337ed48` | Edu Ruiz | ci: avisos de los workflows en el Discord del equipo | ci: workflow notifications in the team Discord |
| `e222942` | amolines | DOCS/GUIA_PROYECTO | docs: project guide (GUIA_PROYECTO) |
