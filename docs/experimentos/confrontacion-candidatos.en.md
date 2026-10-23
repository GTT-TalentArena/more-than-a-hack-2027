# Candidate face-off: protocol (#26, section 1)

> 🇪🇸 Translated from the Spanish original, [confrontacion-candidatos.md](confrontacion-candidatos.md). The Spanish original is the agreed text; this translation is for reference.

> Agreed on 21 Oct 2026 on a call by Jimy (candidate A), Edu (candidate B) and Alejandro (neutral evaluator).
> The common brief is in [`prompts/confrontacion/BRIEF.md`](../../prompts/confrontacion/BRIEF.md) (English translation: [`BRIEF.en.md`](../../prompts/confrontacion/BRIEF.en.md)).
>
> It was written by the author of candidate A with Opus, and reviewed on the call by the other two. Any later
> change is recorded as a deviation in section D.

Two independent candidates estimate H/A/D/X for the challenge match: **A**, developed by Jimy with Claude
Opus 5.5, and **B**, developed by Edu with ChatGPT-6 Astra. This document sets the rules **before writing
code** and the criteria **before seeing any score**.

---

## A. Agreements

| # | Topic | Agreement |
|---|---|---|
| A1 | **Neutral evaluator** | Alejandro; Nico as backup |
| A2 | **Round 1 calendar** | Brief frozen on **22 Oct** · candidates frozen on **29 Oct 23:59** · comparison on **30–31 Oct** · decision for #17 on **1 Nov** |
| A3 | **Time per candidate** | **8 h of active time** each, logged in an hours record. Anything over is noted as a deviation |
| A4 | **Tool** | Each uses their provider's best agentic tool: Claude Code + Opus 5.5 (effort max) and ChatGPT-6 Astra with its coding agent. Model, version and reasoning settings are declared |
| A5 | **How much the human intervenes** | **The LLM writes all the code.** The human gives instructions, runs things locally and returns permitted results (A7). They may fix trivial things by hand (paths, typos), but must note them |
| A6 | **Common inputs** | `main` as it stands on 22 Oct: the challenge kit (`starter/`, `games.py`, `evaluation/`, docs), the study `docs/ESTUDIO_POSESION.md` and the brief. Both may use tracking, homography, Smart Tagging and the tactical video, processed locally |
| A7 | **What may go back to the LLM** | Tracebacks without data, aggregate metrics (public spellF1/macroF1, number and duration of possessions, percentages) and descriptions in words. **Never**: rows, frames, extracts or screenshots (the challenge T&C, see `FAQ.md`) |
| A8 | **Use of the public window** | It may be scored to check that everything works, with a **maximum of 5 public evaluations** per candidate, all recorded. Hyperparameters are not chosen with it |
| A9 | **External data** (Sportec/DFL…) | Allowed for both if declared and the licence is checked |
| A10 | **Separation** | Branches `cand/a-opus` and `cand/b-gpt`; nobody looks at the other's branch or comments on their approach until the freeze. They aren't merged into `main` until the comparison is over |
| A11 | **Delivery of each candidate** | `solution/<cand>/` with a command `python -m solution.<cand> --out <csv>`, pinned `requirements` and < 30 min on a laptop without a GPU. It must generate 199,319 rows and pass `validate_submission.py` |
| A12 | **Decision criterion** | Section C |

---

## B. Common brief

In [`prompts/confrontacion/BRIEF.md`](../../prompts/confrontacion/BRIEF.md). It is the first message to both
candidates, unchanged.

---

## C. Comparison criteria

Fixed before seeing any score. The neutral evaluator applies them, in this order:

1. **Eligibility.** The evaluator reproduces the CSV from the frozen branch (same hash in two runs), the CSV
   passes validation and the time and constraints were respected. If a candidate isn't eligible, the fallback is
   the other one or `baseline_smooth50`.
2. **Plausibility.** The number of possessions, median duration and percentage of `D` and of `X` on the full
   match are compared with the reference ones (the baseline and what the study says). A candidate with twice as
   many possessions as a reasonable figure has its spellF1 capped by construction.
3. **Blind review of disagreements (main criterion).** The intervals where A and B differ are grouped. A fixed
   sample of **40 intervals** is drawn, stratified by type (team, team/D, boundaries). Pablo reviews them on the
   local video **without knowing which candidate is which** and marks which one is right (or neither, or
   ambiguous). The one that is right significantly more often wins (sign test, p < 0.1). The review is only for
   evaluation: no label in the CSV is corrected, and it is declared in the technical document.
4. **Public window.** spellF1 and macroF1 with `--bootstrap 1000`. It only counts if the intervals **don't**
   overlap. If they overlap, it doesn't break the tie.
5. **If nothing decides** → inconclusive result. For #17, the simpler and more robust one is taken (fewer
   parameters, easier to reproduce), and the combination is left for round 2.

---

## D. Record

Each author keeps it and delivers it when freezing their candidate:

- `prompts/confrontacion/<cand>/`: all the prompts in order, dated. The answers, summarised or linked.
- Hours record: start and end of each session, active time and what was done.
- Runs: commit, command, aggregate result and whether it was one of the A8 public evaluations.
- Deviations from the protocol.

None of this includes match data or frame-by-frame derivatives.
