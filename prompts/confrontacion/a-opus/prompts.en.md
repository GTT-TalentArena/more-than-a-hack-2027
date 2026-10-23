# Prompts · candidate A

> 🇪🇸 English translation of [prompts.md](prompts.md). The Spanish original is the protocol record and is left unchanged. The prompt texts were written in Spanish; they are translated here, and the original wording is in the Spanish file.

One section per prompt, in order. The text is copied as is and the answer is summarised: what the model decided and
which files it changed, with the commit.

## 001 · 2026-10-21 ~18:00 · common brief

Text: [`../BRIEF.md`](../BRIEF.md) (English: [`../BRIEF.en.md`](../BRIEF.en.md)), unchanged.

Answer (summary). The model read the documentation, the code in `starter/` and `evaluation/` and the study, without
opening any match data or the public GT. It built `solution/a_opus/` (version 1.0.0):

- **Method.** Per-frame evidence and exact H/A/D decoding (Viterbi with a switching cost λ = 5 nats and stoppages
  of at least 2 s).
  - Team: control zone with a relative-speed gate; without the ball the evidence is zero, not `D`.
  - Tie-breaks: a change of team, as late as possible; a stoppage, as early as possible.
  - Dead ball: out of bounds, ball going out, still ball, kick, collective speed, kick-off formation and Smart
    Tagging `SET PIECES`.
  - Label-free self-calibration: control radius, still-ball threshold, speed mixture, polarity of the Smart Tagging
    codes and a ball-free team model cross-validated by half.
- **Tests.** Synthetic generator in the real formats (`synth.py`) and tests (`tests.py`): the decoder matches brute
  force.
- **Synthetic result** (3 matches): spellF1 0.69–0.77 vs 0.31–0.33 for the baseline on the same data. Takes ~10 s
  and is deterministic.
- **Files:** `solution/a_opus/*`. Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 002 · 2026-10-21 · it doesn't work in the terminal

Text: "it doesn't work for me in the terminal. check the outputs and the failed runs in the terminal please."

Answer (summary). The model read the terminal panel: there were only two failed commands, with no match data.
- `python -m .\solution\a_opus\` failed because `-m` takes a module name, not a path.
- `python -m solution.a_opus` failed because the global `python` (`C:\Python311`) has neither numpy nor pip. The
  main repo's venv does have the pinned versions.

Changes:
- `__main__.py` gives a clear message if numpy is missing.
- `main()` says where it looked for the data if it can't find it (code 2).
- The README has a recipe for Windows.

Commands given: the venv ones with `MTAH_DATA_DIR`. Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 003 · 2026-10-21 · log of the first real run

Text: the aggregate log of run 1 (see `ejecuciones.md`) and the output of `validate_submission.py`, pasted as is.

Answer (summary). The model diagnosed the log:
- **Confirmed:** the reading, the teams (Smart Tagging matches DATA.md), the orientation (H = Barça at 65%) and
  the ball-free model (83% on unseen data).
- **New:** the ATD ball is smoothed and has no short gaps, its third channel is speed, and the Smart Tagging phases
  come in pairs.
- **Code bugs:** the kick after a still ball was never detected, and long `SET PIECES` windows stretched the
  stoppage into play.
- **Main symptom:** only 48 direct H↔A changes. 54.7% of `D` is plausible: three public hints put `D` at ~45–54%
  of the full match.

v1.1:
- The two bugs fixed.
- Paired phases counted once.
- Speed no longer votes `D` with the ball in play.
- λ_HA from 5 to 4.
- Label-free checks in the log (`diagnostics.py`).

Synthetic v1.1: 0.723 / 0.781 / 0.753. Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 004 · 2026-10-21 · what's needed for the next improvement

Text: "tell me exactly what you need. let's get on with another improvement as soon as I know what you need"

Answer (summary). The model asked for two things, already computed in runs 2 and 3 and without spending another
public evaluation:
- the `[a_opus]` lines of the v1.1 log, above all the label-free checks;
- the aggregate detail block of `gtt_comet_v1_1` on the public window (or
  `evaluation/reports/gtt_comet_v1_1.json`).

It was made explicit what isn't passed on: the transition CSVs (they contain frames), the submission and the data.
The public detail is only for understanding the type of error, not for choosing parameters. No code changes.

## 005 · 2026-10-21 · rerun with the log in a file

Text: "the terminal got wiped. give it to me and I'll run it again. I'll pass you all the output, or put the output
you need directly in a path you can access. no improvements yet. first give me that and then we go all in, because
edu has already spent his 5 evaluations"

Answer (summary):
- `--log <path>` is added (a UTF-8 copy of the aggregate log). The CSV doesn't change: same SHA-256 on synthetic data.
- The model read the existing aggregate report `evaluation/reports/gtt_comet_v1_1.json`, without opening the
  `*_transitions.csv` and without spending another public evaluation.
- It saved the hash of the current `gtt_comet_v1_1.csv` to check that the rerun reproduces it byte for byte (C1).
- Command given: v1.1 with `--log evaluation\reports\gtt_comet_v1_1_log.txt`. Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 006 · 2026-10-21/22 · attacking the boundaries with the study

Text: "go for that then. you have the possession theory we studied to apply. it's in docs/ESTUDIO_POSESION I think.
if anything there helps as an improvement, go ahead. done. go all in."

Answer (summary):
- **Rerun and log.** The model read the v1.1 log from the file and checked that the rerun reproduces the CSV byte
  for byte (C1).
- **Diagnosis.** The label-free log answers L4 of the study: the ball is visible in 91% of live frames and in 24%
  of `D`. The public window (already scored) shows boundaries shifted by more than 1 s.
- **v1.2**, applying the study:
  - stoppage evidence from a long absence of the ball (3.3, point 3, and L4), with two passes and a hard EM step;
  - ball-free model with shifted windows to remove its lag (3.3, point 4, and P6);
  - team change dated at the first touch (3.2, 4.6, P5);
  - estimation and correction of the ball–players lag by speed.
- **Tried and discarded** (documented in the README): evidence per gap by length, a visibility Markov chain and a
  position-based lag estimator.
- **Results.** Synthetic v1.2: 0.728 / 0.789 / 0.755. New tests for dating at the first touch.
  Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 007 · 2026-10-22 · evaluate and improve until the 5 evaluations are spent

Text: "got it? evaluate and improve. we need to get to the 5 evaluations today. the team needs them. save results
for the chart and go hard."

Answer (summary):
- **Reading the v1.2 log.** No ball lag; ball-free model at 87.9 / 83.8% with the peak at 0; long absence = 87.7%
  `D`.
- **Public evaluation no. 3.** Run by the model, on v1.2 only and with aggregate-only output: spellF1 0.4800,
  macroF1 0.8331, transF1@25 0.216.
- **Table for the chart.** `prompts/confrontacion/a-opus/resultados.csv`: one row per version, with the public
  metrics, the label-free aggregates of the full match and the synthetic mean.
- **v1.3:** touches (study 3.1 and P3), λ = 3 and restart after a long gap (3.4). Synthetic 0.761 / 0.810 /
  0.774. Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 008 · 2026-10-22 · v1.3 log

Text: "done, the v1.3 log is in evaluation\reports\gtt_comet_v1_3_log.txt"

Answer (summary):
- **Reading the log.** Only 70 touches in the whole match: the acceleration-based detector doesn't fit the smoothed
  ball of the real ATD.
- **Public evaluation no. 4** (v1.3 only, aggregate output): identical to v1.2 (0.4800).
- **Table for the chart:** v1.3 row added.
- **v1.4:**
  - touch detector by net velocity change;
  - threshold from free flight with nobody within 4 m in the window;
  - assignment by minimum distance within ±3 frames;
  - log with the counts of each filter;
  - generator with `--ball-style real` to reproduce the smoothed ball.
- **Results.** Synthetic: noisy 0.775, real style 0.785. Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 009 · 2026-10-22 · v1.4 log

Text: "done, the v1.4 log is in evaluation\reports\gtt_comet_v1_4_log.txt"

Answer (summary). The log is healthy except for the touches: 422 peaks and 213 assigned. It fits a ball smoothed at
~1 s. The model didn't spend evaluation no. 5 and asked whether to spend it on v1.4 or prepare a v1.5.

## 010 · 2026-10-22 · the best possible candidate against B

Text: "it's not thaaaat urgent. improve everything you can to get the best candidate against edu's."

Answer (summary):
- **New test bench:** synthetic data with strong smoothing (`--smooth-half 12`), which reproduces the signature of
  the real ball.
- **v1.5:**
  - touches at the scale chosen per match (±6/12/25, label-free);
  - ball-free model also with the ball visible but no clear control, at half weight.
- **Tried and switched off** (no improvement): dating changes without a speed gate and dating restarts by
  half-rise.
- **Discarded:** λ 2–2.5, touch at 2.5 nats and a 0.2 m margin.
- **Results.** Synthetic: noisy 0.784 (v1.4: 0.775), smoothed 0.786 (v1.4: 0.774). Evaluation no. 5 reserved.
  Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 011 · 2026-10-22 · table for Molines and assessment of v1.5

Text: "molines wants me to send him these results from the image. you already have the 1.5 log. evaluate and if you
think it's a good candidate, tell me and I'll share it. no rush, we can still do a couple of iterations if you
want." (With a screenshot of the requested table format. Only the column headers from the screenshot were used.)

Answer (summary):
- **v1.5 log healthy:** 214 possessions, 49.3% `D`, 101 direct changes. But the touches were still weak: aerial
  balls in the threshold reference.
- **v1.6:** threshold with a ground-ball reference. Neutral on synthetic data and aimed at the real failure.
- **Evaluation no. 5:** reserved for v1.6 if its log comes out healthy.
- **Table:** prepared in Molines' format with the 4 evaluations done. Commit: no commit of its own (intermediate version); the final code is in `6456aab`.

## 012 · 2026-10-22 · v1.6 log and evaluation no. 5

Text: "done, the v1.6 log is in evaluation\reports\gtt_comet_v1_6_log.txt; if it's healthy, spend no. 5 on it"

Answer (summary):
- **Healthy log:** 219 possessions, 113 stoppages (49.3%), 106 direct changes and 622 touches assigned (twice as
  many as v1.5).
- **Public evaluation no. 5** (v1.6 only, aggregate output): spellF1 0.5250 (bootstrap 0.338–0.713), macroF1
  0.8391, 15 possessions vs 17, spellF1@0.7 0.375 and team accuracy 0.899. It's the best of the five, but its
  interval overlaps with the earlier ones.
- **Wrap-up:** full table in `resultados.csv` and in Molines' format. The 5 evaluations are used up.
  Commit: `6456aab` (v1.6); the PR, in entry 013.

## 013 · 2026-10-22 · commit, push and PR for Molines

Text: "commit and push, let's leave the PR ready for Molines. check what else needs ticking in the issues now that
this is done, check the entries in the logs. I'll announce it's uploaded as soon as I send you this prompt"

Answer (summary):
- **Records reviewed:** `desviaciones.md`, which was empty, is completed.
- **Commit of v1.6** on `cand/a-opus`.
- **Merge of `main`** (Docker, P0 contract, P1; no conflicts) and `configs/candidate_a.json` for the common path
  `docker compose run --rm modelo`.
- **Push and PR** for Alejandro, not to be merged until the comparison is over (A10).
- **Issues:** list of what can be ticked in #26, #17, #15, #16 and #18 with this delivery.

Result: commits `6456aab`, `14af225` (merge of `main`), `488a5c3` and `8b86676` pushed to `cand/a-opus`; PR #33
opened with Alejandro as reviewer.

## 014 · 2026-10-22 · issues

Text: "Yes: tick in #15, #16 and #18 the boxes candidate A covers, and leave a comment in #26 and #17 with A's part
and the link to PR #33."

Answer (summary):
- **#15:** 8 boxes ticked. 3 left: Nico's signals, exporting the per-frame evidence and the battery of explicit cases.
- **#16:** 8 ticked. 4 left: voting vs hysteresis, their test cases, comparison through #12 and demonstration with
  examples.
- **#18:** all 9.
- **Comments in #26 and #17:** A's part, the reference hash, the public metrics with their interval and the warning
  that it isn't a private result.

## 015–017 · 2026-10-22 · plan after the delivery and P3/P4 work

Texts: the team chat (A chosen; order P2 → P3 → P4 → 0.2433), "what can we get going on until then?" and "let's go
with whatever you can do. I'll let them know. we'll close more checks and take work off the pile."

Answer (summary). Branch `feat/p3-p4-pruebas` from `main`, without changing the model or its CSV:
- alternative decoders (hysteresis and voting) and `compare_decoders`, for #16;
- explicit scenario tests for P3 and P4;
- `--evidence` export with the names from the P0 contract §6.

## 018–023 · 2026-10-22 · Docker, hours and P3 with P2

Texts: "let's go with docker then", "docker's installed but I can't run step 2", "check the terminal", "put down
hours … 3h and 3h", "post the comment … in #26 and #17" and "pablo has done his part. let's get on with that".

Answer (summary):
- **Docker:** the problem was the folder (no `compose.yaml`). Run from the worktree, the CSV is identical to v1.6's
  and deterministic. Recorded in `ejecuciones.md` (13 and 14) and commented in #26 and #17.
- **Hours:** 6 h of 8 in `horas.md`, as Jimy's estimate.
- **P3 with P2 (#14):** branch `feat/p3-p2-reinicios`. `p2.py` uses the candidates from Pablo's detector as `D`
  evidence, off by default (`with_p2` for the variant). On synthetic data it changes nothing: Pablo's rule finds no
  preparations with the smoothed ball, and with a 1 s margin it doesn't improve A either. It isn't adopted without a
  real run with a label-free log.
