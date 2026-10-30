# Runs (variant B + Claude)

> 🇪🇸 English translation of [ejecuciones.md](ejecuciones.md).

| # | Date | Commit | Command | Aggregate result | Public (A8)? |
|---|---|---|---|---|---|
| s1 | 2026-10-21 | (this commit) | `python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics` | 37 tests OK (34 from v0 + 3 new); the new main test fails with v0 | No (synthetic) |
| s2 | 2026-10-21 | (this commit) | `python -m solution.b_gpt --synthetic` ×2 | same SHA-256 in both; official validator OK (199,319 rows); ~4.6 s | No (synthetic) |
| 1 | 2026-10-21 | `02bda8f` | `python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv` (Edu, real data) | 347 possessions · mean 11.87 s · median 6.84 s · D 35.19 % · X 0 % (scored halves) · `out_of_play_gap_frames` 6,787 · validator OK · 8.55 s | No |
| 2 | 2026-10-21 | `02bda8f` | the same, with `--out …/b_gpt_claude_r2.csv` | same SHA-256 as #1 (`68f2ed57…`) · 8.46 s | No |
| 3 | 2026-10-21 | `02bda8f` | public evaluation with Docker (`docker/pipeline.py evaluar`, bootstrap 1000) on `b_gpt_claude.csv` | spellF1 **0.3895** · macroF1 0.6620 · 21 possessions · 13.6 s — **identical to v0** on the public window | **Yes, candidate B's #2** |
| 4 | 2026-10-21 | `fedc89e` | the same as #1, with `dead_time_diagnostics` diagnostics (Edu, real data) | same SHA-256 (`68f2ed57…`): the diagnostics do not change labels · gaps without the ball: < 5 s 0.17 min; 5–10 s 53 stretches / 6.23 min (3.41 live); 10–30 s 60 / 17.84 (5.99 live); > 30 s 19 / 18.88 (3.21 live) · slow phases < 1 / 1.5 / 2 m/s: 18.4 / 37.7 / 42.3 min (0.5 / 8.5 / 12.0 live) | No |
| s3 | 2026-10-21 | (this commit) | synthetic tests and `--synthetic` ×2 (v2) | 39 tests OK; the new long-gap test fails with v1; same SHA-256 in both runs; validator OK | No (synthetic) |
| 5 | 2026-10-21 | `6b83b32` | v2 with real data ×2 (Edu) | 345 possessions · mean 9.62 s · median 5.8 s · D 47.76 % · X 0 % · gaps ≥ 10 s labelled live 9.2 → 0.6 min · same SHA-256 in both (`c818b572…`) | No |
| 6 | 2026-10-21 | `6b83b32` | public evaluation with Docker (bootstrap 1000) on v2 | spellF1 **0.3122** [0.185, 0.449] · macroF1 0.6652 · 24 possessions · 10.8 s · code 5 (below smooth50) · D precision 0.589 / recall 0.406 (v1: 0.997 / 0.257) | **Yes, candidate B's #3** |
| s4 | 2026-10-21 | (this commit) | synthetic tests and `--synthetic` ×2 (v3) | 42 tests OK; the one with the ball hidden by a player fails with v2; same SHA-256 in both; validator OK | No (synthetic) |
| 7 | 2026-10-21 | `13ffe9b` | v3 with real data ×2 (Edu) | 340 possessions · mean 11.02 s · median 6.58 s · D 41.05 % · X 0 % · live gaps: 5–10 s 2.62 · 10–30 s 4.07 · > 30 s 0.62 min · same SHA-256 in both (`a5372e72…`) | No |
| 8 | 2026-10-21 | `13ffe9b` | public evaluation with Docker (bootstrap 1000) on v3 | spellF1 **0.3895** · macroF1 **0.6901** [0.470, 0.822] · 21 possessions · 13.4 s · code 0 · D precision 0.998 / recall 0.317 | **Yes, candidate B's #4** |
| s5 | 2026-10-21 | (this commit) | synthetic tests and `--synthetic` (v3 + v4 diagnostics) | 43 tests OK; same synthetic SHA-256 as v3 (`9ec36b1a…`): the diagnostics do not change labels | No (synthetic) |
| 9 | 2026-10-21 | `620823d` | v3 + v4 diagnostics with real data (Edu) | same SHA-256 as v3 (`a5372e72…`) · duels 0.54 min, 18/241 changes next to a duel · still ball live outside the box 0.73 min · gaps at a line that reappear quickly 9.92 min (32) · 70 back-and-forths < 3 s (2.1 min) · 100 D stretches (median 15.6 s) | No |
| s6 | 2026-10-21 | (this commit) | synthetic tests and `--synthetic` ×2 (v4) | 46 tests OK; the new main test fails with v3; same SHA-256 in both; validator OK; 38 back-and-forths merged in the synthetic match | No (synthetic) |
| 10 | 2026-10-21 | `8ae2aa5` | v4 with real data ×2 (Edu) | 220 possessions · mean 17.03 s · median 11.62 s · D 41.05 % (identical to v3) · X 0 % · 60 back-and-forths merged · H↔A changes 241 → 121 · back-and-forths < 3 s 0 · possessions < 2 s 57 → 13 · 100 D stretches unchanged · same SHA-256 in both (`f7d8f604…`) | No |
| 11 | 2026-10-21 | `8ae2aa5` | public evaluation with Docker (bootstrap 1000) on v4 (Edu) | spellF1 **0.4000** [0.213, 0.587] · macroF1 **0.6983** [0.472, 0.836] · 13 possessions · 21.6 s · code 0 · team accuracy 0.873 · D F1 0.481 | **Yes, candidate B's #5** |

Comparison with v0 (b-gpt record): 354 → 347 possessions, D 33.41 % → 35.19 %, mean 11.95 → 11.87 s. Without GT: it does not say whether it is more accurate.

Public quota shared with candidate B (Alejandro's decision, 21:45): **5 of 5 used** in total (#1 v0, #2 v1, #3 v2, #4 v3, #5 v4). There are no public evaluations left.

Reading fixed before evaluating: spellF1 differences < ~0.06 are one possession in this window. Result: v1 **cannot be told apart** from v0 on the public window (the change does not act in those 5 min); its possible effect is in the rest of the match and only the blind review can assess it.

Reading of #3 with the criterion fixed beforehand: **mixed** result (spellF1 drops > 0.06 but macroF1 does not drop). The hypothesis is partly right (a lot of D is missing) but not all long gaps are stoppages.

Reading of #4 with the criterion fixed beforehand ("clear improvement: spellF1 ≥ 0.3895 without lowering macroF1"): **it is met**; v3 becomes the variant's version.

Check of v4 before evaluation #5 (expectations fixed in analisis-v4.md §6): D identical (41.05 %), possessions 340 → 220 and H↔A changes 241 → 121 within what was expected, 0 back-and-forths < 3 s, deterministic. **All are met**: v4 may use public evaluation #5.

**Public evaluation #5 postponed (2026-10-21, ~22:45).** It is candidate B's last one and is kept for the version that gets frozen. It waits for the protocol's cut-off for shared inputs (A6: `main` on 22 October) in case teammates' studies published in `main` justify a v5. Nothing from candidate A's branch is consulted (A10). If there are no relevant shared studies, v4 is evaluated as it is, with the criterion already fixed.

**Evaluation #5 (v4).** Edu decided to run it on 21 October itself, without waiting for the shared-input cut-off of 22 October that had been proposed. The protocol allows it: it was the fifth of the 5. Fixed criterion (spellF1 ≥ 0.3895 and macroF1 ≥ 0.6901): **it is met**, and v4 is the final version of the variant. The improvements over v3 are within the window's noise, and v4 gives fewer possessions than the GT (13 versus 17); see iteraciones.md ([English](iteraciones.en.md)). Any later change can no longer be checked with the public window and, after the 29 October freeze, counts as a new round.
