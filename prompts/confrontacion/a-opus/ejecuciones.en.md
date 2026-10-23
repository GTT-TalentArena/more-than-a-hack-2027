# Runs · candidate A

> 🇪🇸 English translation of [ejecuciones.md](ejecuciones.md). The Spanish original is the protocol record and is left unchanged.

Aggregate results only (A7). A maximum of 5 evaluations on the public window (A8); they are numbered here.

| # | Date | Commit | Command | Aggregate result | Public (A8)? |
|---|---|---|---|---|---|
| 1 | 2026-10-21 | no commit (v1.0, working tree) | `python -m solution.a_opus --out evaluation/results/a_opus.csv` + `validate_submission.py` | Valid, 199,319 rows, 13 s. 162 possessions (mean 17.8 s, median 13.3 s); 115 stoppages (54.7% of scored frames, median 21.4 s); only 48 direct H↔A changes; H live possession 65.0%. Ball-free model: 84.8% / 82.4% on unseen data. 53 of 59 `SET PIECES` windows with a decoded restart | no |
| 2 | 2026-10-21 | no commit (v1.1, working tree) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_1.csv` + `validate_submission.py` (before that, v1.0's `a_opus.csv` renamed to `gtt_comet_v1_0.csv`) | Valid. The aggregate log of v1.1 wasn't returned to the LLM | no |
| 3 | 2026-10-21 | no commit (v1.0 and v1.1) | `python evaluation/run_evaluation.py` (without `--bootstrap`) | Public window (17 possessions). **v1.1:** spellF1 0.4800 · macroF1 0.8318 · 13 possessions (mean 18.6 s vs 14.2 s) · transF1@25 0.1622. **v1.0:** spellF1 0.4414 · macroF1 0.7997 · 12 possessions · transF1@25 0.0556. `baseline_smooth50`: 0.3256 · 0.6207. Difference v1.0 → v1.1 within the noise band (~0.04) | **yes · no. 1 (v1.0) and no. 2 (v1.1)** |
| 4 | 2026-10-21 | no commit (v1.1 + `--log`) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_1.csv --log evaluation/reports/gtt_comet_v1_1_log.txt` | Same SHA-256 as run 2 (`a669fb61…`): reproducible (C1). 184 possessions (mean 18.2 s, median 13.2 s), 108 stoppages (47.2%), 76 direct H↔A changes; ball visible in 91% of live frames and in 24% of `D`; `SET PIECES` windows of ~35 s with the restart at a median of 7 s; λ curve 3/4/5/6/8 → 196/184/173/162/150 possessions. The LLM read the log from the file and the aggregate JSON from run 3 (not the `*_transitions.csv`) | no |

| 5 | 2026-10-22 | no commit (v1.2) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_2.csv --log evaluation/reports/gtt_comet_v1_2_log.txt` (Jimy) | 185 possessions, 114 stoppages (49.1%), 71 H↔A changes; ball-free model 87.9% / 83.8% (peak at lag 0); no ball delay (correction 0); absence: gaps ≥ 2 s = 40.6% of frames, 87.7% of them in `D` → +0.042 nats/frame | no |
| 6 | 2026-10-22 | no commit (v1.2) | `run_evaluation.py --results <v1.2 only> --bootstrap 1000` (run by the LLM; prints aggregates only) | Public window: **spellF1 0.4800** (bootstrap 5–95% 0.293–0.667) · macroF1 0.8331 · transF1@25 0.2162 (mean latency +7.2) · 13 possessions vs 17 · alive/dead F1 0.961 · team accuracy 0.871 | **yes · no. 3 (v1.2)** |

| 7 | 2026-10-22 | no commit (v1.3) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_3.csv --log evaluation/reports/gtt_comet_v1_3_log.txt` (Jimy) | 197 possessions, 114 stoppages (49.0%), 83 H↔A changes. **Only 70 touches detected** (threshold 24.9 m/s²): the acceleration-based detector doesn't fit the smoothed ball of the real ATD. Restarts after a gap: 2 | no |
| 8 | 2026-10-22 | no commit (v1.3) | `run_evaluation.py --results <v1.3 only> --bootstrap 1000` (LLM; aggregates only) | Public window identical to v1.2: **spellF1 0.4800** · macroF1 0.8331 · transF1@25 0.2162 · 13 possessions (v1.3's changes don't touch those 5 minutes) | **yes · no. 4 (v1.3)** |

| 9 | 2026-10-22 | no commit (v1.4) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_4.csv --log evaluation/reports/gtt_comet_v1_4_log.txt` (Jimy) | 203 possessions, 114 stoppages (49.0%), 89 H↔A changes; touches by velocity change at ±6: 422 peaks, 213 assigned (threshold 5.29 m/s): ball smoothed at a ~1 s scale | no |
| 10 | 2026-10-22 | no commit (v1.5) | same with `gtt_comet_v1_5` (Jimy) | 214 possessions (median 10.4 s), 113 stoppages (49.3%), 101 H↔A changes; touch scale chosen ±25, but the 12.09 m/s threshold inflated by aerial balls: 315 assigned | no |
| 11 | 2026-10-22 | no commit (v1.6) | same with `gtt_comet_v1_6` (Jimy) | 219 possessions (median 10.4 s), 113 stoppages (49.3%), 106 H↔A changes; touches at ±25 with a ground-ball reference: threshold 8.83 m/s, 622 assigned (H 424 / A 198) | no |
| 12 | 2026-10-22 | no commit (v1.6) | `run_evaluation.py --results <v1.6 only> --bootstrap 1000` (LLM; aggregates only) | Public window: **spellF1 0.5250** (bootstrap 5–95% 0.338–0.713) · macroF1 0.8391 · transF1@25 0.2564 (mean latency +3.8, median −1) · 15 possessions vs 17 · spellF1@0.7 0.375 · alive/dead F1 0.955 · team accuracy 0.899 | **yes · no. 5 (v1.6)** |
| 13 | 2026-10-22 | `feat/p3-p4-pruebas` (no model changes) | `python docker/pipeline.py evaluar`, without Docker (launched by the LLM; aggregates only) | Code 0. It scored every CSV in `evaluation/results/`: v1.6 0.5250 (hash `ab640ee8…`), and also v1.4 0.5375 and v1.5 0.5250, which hadn't been evaluated. See `desviaciones.md` | **yes · 2 outside the budget (v1.4, v1.5)** |
| 14 | 2026-10-22 | `feat/p3-p4-pruebas` (no model changes) | `docker compose run --rm modelo modelo --config configs/candidate_a.json --repetir` (Jimy, Docker Desktop, WSL2) | Code 0, 16 s per pass. CSV SHA-256 `ab640ee8694f…d6bc5`, **identical to v1.6 on Windows** and between the two passes (`determinista: true`). Linux/WSL2, Python 3.11.17, numpy 2.4.6, pandas 3.0.6. Same aggregate log as run 11. Public window: spellF1 0.5250 · macroF1 0.8391 (repeats no. 5; same CSV). `run.json` leaves `commit: null` because the worktree has no `.git` inside the container | yes · repeats no. 5 on the same CSV |
| 15 | 2026-10-22 | `feat/p3-p2-reinicios` (`cec914d`, P3) | `python -m solution.a_opus.with_p2 --out salidas/a_p2.csv --log salidas/a_p2_log.txt` (Jimy; not evaluated) | Valid, 199,319 rows, 32 s. P2: 59 restarts, **0 `tagged_preparation`**, 2 `initial_kickoff_context`, 64 `observed_exit` (weight 0); `p2` evidence +137/−5 nats. 216 possessions (median 9.9 s), 111 stoppages (49.9%), 105 H↔A changes. CSV `1ef48487…` (different from v1.6's). The LLM read only the aggregate log | no |

**Public evaluations used:** 5 of 5. None left. Later versions can only be validated with the label-free log and
with synthetic data.

**Delivery for the comparison:** the code of runs 11 and 12 (v1.6.0) is that of commit `6456aab`. After that, only
`main` was merged (common infrastructure) and documentation and `configs/candidate_a.json` were added, with no
changes to the model. Reference CSV of v1.6: SHA-256
`ab640ee8694f259697393d822b0a6665a017878b5b29d12715f59ec8a4dbc6d5` (Python 3.11.3, numpy 2.4.6, Windows 11). One is
counted per scored version, even when two were in the same command (a conservative reading of A8). The v1.1 changes
were decided with the label-free log of run no. 1, before scoring anything.
