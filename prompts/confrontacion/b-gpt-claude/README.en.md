# Variant B + Claude (v1)

> 🇪🇸 English translation of [README.md](README.md). The Spanish files in this folder are the protocol record and are left unchanged; each one has an `.en.md` translation next to it.

| field | value |
|---|---|
| What it is | Candidate B v0 (tag `b-gpt-v0`, commit `1c96afa`: Codex only, ChatGPT-6 Astra high) **plus improvements written by Claude** |
| Branch | `cand/b-gpt-claude`, taken from the tag `b-gpt-v0` |
| Operator | Edu (`hxst1`) |
| Tool | Claude Code |
| Model | Claude Opus 5.5 (`claude-opus-5-5`, 1M context). Effort **medium** until 22:18 on 2026-10-21 (v1–v3); **max** from 22:18 (v4) |
| Approval | Alejandro (neutral judge, A1), on WhatsApp on 2026-10-21 at 21:33: "Sounds good · Very good idea" |
| Submission command | `python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv` |
| Package | `solution/b_gpt/` (same package; the change is described in its README, section "Variant v1") |

Versions of the variant: **v1** (`02bda8f`, ball lost after leaving the pitch = stoppage) and **v2** (long gaps without the ball = stoppage). Details in the package README.

Goal: compare three results in round 1 — **A** (Opus), **B v0** (GPT only) and **B + Claude** — and measure whether one AI improves what the other did. v0 is kept intact in its tag.

Same restrictions as the rest of the protocol (A5–A8): Claude has not seen the match data or any CSV of real labels; only code, documentation and synthetic data. Edu runs it locally and sends back only aggregates.

Analysis of v4: [analisis-v4.md](analisis-v4.md) ([English](analisis-v4.en.md)) · Iterations: [iteraciones.md](iteraciones.md) ([English](iteraciones.en.md))

**Result of the comparison (22 Oct):** Alejandro chose candidate A. On the public window, A v1.6: spellF1 0.5250 · macroF1 0.8391; B v4: 0.4000 · 0.6983. Results per version: [resultados.csv](resultados.csv).

Record: [prompts.md](prompts.md) ([English](prompts.en.md)) · [horas.md](horas.md) ([English](horas.en.md)) · [ejecuciones.md](ejecuciones.md) ([English](ejecuciones.en.md)) · [desviaciones.md](desviaciones.md) ([English](desviaciones.en.md))
