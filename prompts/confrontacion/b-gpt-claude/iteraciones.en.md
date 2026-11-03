# Iterations of candidate B (v0 and variant + Claude)

> 🇪🇸 English translation of [iteraciones.md](iteraciones.md).

One row per public evaluation (A8, at most 5, quota shared between v0 and the variant). Requested by Alejandro for the comparison.

| Iteration | Version · commit | Change from the previous one | 1. Public spellF1 [90 % CI] | 2. Public macroF1 | 3. Possessions in window (GT 17) | 4. % D full match | 5. Possessions full match |
|---|---|---|---|---|---|---|---|
| 1 | v0 (Codex only) · `1c96afa` (tag `b-gpt-v0`) | — (first version) | 0.3895 [0.242, 0.537] | 0.6620 | 21 | 33.41 % | 354 |
| 2 | v1 (+ Claude) · `02bda8f` | Ball lost after leaving the pitch = stoppage | 0.3895 [0.242, 0.537] | 0.6620 | 21 | 35.19 % | 347 |
| 3 | v2 (+ Claude) · `6b83b32` | Long gaps without the ball (≥ 5 s, players tracked) = stoppage | 0.3122 [0.185, 0.449] ⚠️ | 0.6652 | 24 | 47.76 % | 345 |
| 4 | v3 (+ Claude) · `13ffe9b` | Only the gaps without the ball that start or end like a restart (ball hidden or in the air = live play) | 0.3895 | **0.6901** [0.470, 0.822] | 21 | 41.05 % | 340 |
| 5 | v4 (+ Claude, effort max) · `8ae2aa5` | A touch is not a change: an opponent stretch < 3 s between two of the same team, with no stoppage, goes back to the team that had the ball | **0.4000** [0.213, 0.587] | **0.6983** [0.472, 0.836] | 13 | 41.05 % | 220 |

References: `baseline_smooth50` on the public window = spellF1 0.3256 [0.214, 0.447] · macroF1 0.6207 · 26 possessions.

**How to read it.**
- 1–3 are the 5-min public window: spellF1 differences below ~0.06 amount to a single possession (noise).
- 4–5 are from the full match and use no GT. The reference for % D is LaLiga's effective playing time (≈ 54 min; Barça 2024/25 ≈ 57.8 min) over ≈ 106 scored minutes, i.e. ≈ 45–49 % D. It is a reference for direction, not a tuning target: the GT marks D from the corrected tracking, which may not match the referee.
- Alejandro's main criterion is the blind video review; this table only shows the evolution.

> Translator's note (29 October 2026): the blind video review was later withdrawn, because the challenge rules forbid human labels on the challenge match, also for validation. See [issue #47](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/47).

**Iteration 3 (v2), mixed result.** On the full match it does what was expected (D 35 → 48 %, within the effective-time range). On the public window, D recall goes up (0.257 → 0.406) but D precision drops (0.997 → 0.589): some of the long gaps are live play according to the GT, they split possessions (21 → 24, GT 17) and spellF1 drops 0.077 (more than one possession). macroF1 holds (0.6620 → 0.6652).

**Iteration 4 (v3), an improvement on v1 by the criterion fixed beforehand.** spellF1 the same (0.3895) and macroF1 +0.028 (0.6620 → 0.6901). In the window: D precision 0.998 (like v1), D recall 0.257 → 0.317, D F1 0.409 → 0.481, the same 21 possessions and 23 segments as v1. On the full match, D 41.05 %. Caution: the intervals overlap and the idea came after evaluation #3 (see deviations).

Breakdown of D on the public window:

| Version | D precision | D recall | D F1 | Segments (GT 21) |
|---|---|---|---|---|
| v1 | 0.997 | 0.257 | 0.409 | 23 |
| v2 | 0.589 | 0.406 | 0.481 | 29 |
| v3 | 0.998 | 0.317 | 0.481 | 23 |

**Iteration 5 (v4): passes the fixed criterion and is the final version of the variant.** spellF1 0.3895 → 0.4000 and macroF1 0.6901 → 0.6983, both improvements below the window's noise. Team accuracy with the ball live 0.860 → 0.873. F1 by IoU threshold: at 0.3–0.4 it goes up (0.474 → 0.533); at 0.5–0.7 it drops slightly (0.474 → 0.467, 0.316 → 0.267, 0.211 → 0.200). Possessions in the window 21 → 13 (GT 17): the 3 s rule removes false changes, but it also merges some real short possessions. It is v4's main uncertainty. It is not tuned (there are no public evaluations left and it would overfit to 17 possessions); it is left for the technical document and the next round.

**Summary of the variant:** v0 (Codex) → v4 (Codex + Claude), spellF1 0.3895 → 0.4000 and macroF1 0.6620 → 0.6983 on the public window (smooth50: 0.3256 / 0.6207). All 5 of candidate B's public evaluations are used.
