# Analysis for v4 (Claude Opus 5.5, effort max · 2026-10-21)

> 🇪🇸 English translation of [analisis-v4.md](analisis-v4.md).

Done without seeing the data: code of `solution/b_gpt/` (v3), the challenge's public documentation
(`CHALLENGE.md`, `DATA.md`, `EVALUATION.md`, `FAQ.md`), literature and the Laws of the Game. The only
match numbers used are aggregates already recorded in `ejecuciones.md`.

## 0. Starting point: where v3 fails

Aggregates of public evaluation #4 (5-min window; GT: H 3,454 · A 2,577 · D 1,469 frames,
17 possessions, 21 segments, i.e. 4 `D` stretches). They are used to **understand** the failures, not
to tune anything:

- **Missed `D`.** `D` precision 0.998 and recall 0.317: what v3 calls `D` almost always is,
  but it misses ≈ 1,000 frames (≈ 40 s) of the 1,469 `D` frames. It detects 2 `D` stretches
  (23 segments − 21 possessions) of the GT's 4.
- **Wrong team.** Team accuracy with the ball live 0.860: ≈ 34 s with the team swapped,
  and 21 possessions versus 17, so there are too many H↔A changes.
- On the full match (without GT): `D` 41 %, 340 possessions.

Note: in v2 we saw that gaps without the ball that reappear moving inside the pitch are mostly
live play. The missing `D` has to be mainly **where the ball is visible**: the
ball rolling out, the one being placed for the restart, the one held by the thrower.

## 1. What the challenge says

- The GT is **mechanical**: `D` where the corrected tracking marks the ball as dead; otherwise, the team
  that this tracking names as owner. A dead ball runs **from the ball going out or the whistle until the
  restart**, even if the automatic tracking sees the ball all the time.
- **Change of possession = an opponent gains controlled possession.** In contested phases or with a loose
  ball, possession stays with the last team. These are not a change: a touch without control, a
  deflection that does not intercept and an aerial duel won without control afterwards.
- The automatic tracking loses the ball through occlusions, crowded areas and balls in the air.

## 2. Literature and Laws of the Game

- **Vidal-Codina et al. (2022)**, event detection with tracking:
  - possession zone of **0.5–1 m** around the player;
  - **duel zone of 1 m** around the ball: with two opponents inside there is a duel, and **the duel
    prevails over possession**;
  - a **possession gain requires contact**, measured as a change of direction or speed
    of the ball inside the zone; if it does not change, the ball only passed nearby;
  - some providers mark the dead ball by leaving it without data.
- **Link and Hoernig (2017)**: individual possession from control phases (sphere of
  influence, distance, speed and acceleration of the ball), with a Bayesian network for the degree of
  control.
- **PathCRF (Kim et al., 2026)**: infers possession **without the ball**, from the players'
  trajectories, with a CRF and Viterbi decoding.
- **Laws of the Game (IFAB)**:
  - kick-off (Law 8), free kicks (13) and goal kick (16) **with the ball stationary**;
  - the ball is in play when it is kicked and **clearly moves** (Law 8);
  - the goalkeeper may hold the ball in their hands for a few seconds (Law 12: 6 s in 2024-25; 8 s
    and a corner from 2025-26).
- **Average duration of stoppages**: throw-in ≈ 13 s, goal kick ≈ 17 s, free kick ≈ 21–23 s,
  corner ≈ 27 s, kick-off ≈ 37–46 s (PMC study). In the Premier League, throw-ins of
  15–18 s (The Analyst).

## 3. Cases v3 does not cover

| # | Case | What v3 does | What the challenge, the laws or the literature say | Risk of overfitting |
|---|---|---|---|---|
| 1 | **Duel**: players of both teams ≤ 1 m from the ball | The slightly closer opponent builds up evidence and can change the possession | Challenge: in contested phases the last team keeps it. Literature: the duel prevails, with a 1 m radius | **Low**: rule written in the challenge and a parameter from the literature |
| 2 | **Ball placed** for a restart, visible and still | Only `D` if the players are also almost still (< 1.2 m/s for 2 s); with players moving, it counts as live | Laws 8, 13 and 16: the restart is taken with the ball stationary. In play, outside the goalkeeper's hands, the ball does not stay still for seconds | **Low–medium**: the goalkeeper with the ball in their hands (penalty area) has to be excluded |
| 3 | **Leaving `D` with the ball still stationary** | It can leave `D` if the players run and someone is near the ball | Law 8: in play when kicked and clearly moving | **Low** |
| 4 | **Restart next to the line and ball lost right after** (throw-in or corner already taken) | The gap counts as `D` (`lost_at_line`) even though the ball is already in play | The ball entered the pitch: the restart has been taken | **Low**: removes a possible false `D` |
| 5 | **Ball reappearing next to the line at speed** (winger hugging the touchline) | The gap before counts as `D` (`back_at_line`) | A throw-in or corner reappears in the hands or placed, not at speed | **Low** |
| 6 | **Goalkeeper releasing the ball and playing** (reappears slow and soon moves) | `back_still` marks the gap as `D` | A ball placed for a restart stays still for several seconds | **Low** |
| 7 | **Gaining possession without contact** (the pass goes near an opponent) | Only lowers the weight of fast balls | Literature: requires a change of direction or speed | **Medium**: ball noise makes the change hard to measure; its thresholds are in supplementary material |
| 8 | **Team taking the restart after the ball goes out** (last-touch rule) | Decided by the nearest player after the restart | The opponent of the last player to touch it takes it | **Low**, but with little impact: the player taking it is usually right by the ball |
| 9 | **Aerial ball projected out** over the far touchline (camera perspective) | Counts as out if it goes 0.35 m past the line | A ball in the air projects further from the camera than it really is | **Hypothesis**: check with "out → in in < 1 s" rebounds per side |
| 10 | **Possession during gaps with live play** (≈ 7 min in v3) | Keeps the last team until the ball reappears | PathCRF infers possession from the trajectories | **High**, and high cost: outside v4 |
| 11 | **Penalty** (ball still in the area) | Like case 2, but inside the area | Rare (0–1 per match) | Out of scope |

## 4. Proposals, ordered by how well founded they are

1. **P1 · Duel = the last team keeps it.** With one player from each team ≤ 1 m from the ball,
   the control evidence is cancelled: nobody can gain possession in a duel. Only whoever
   comes out of it with the ball can gain it. Covers case 1.
2. **P2 · Restarts are taken with the ball stationary.**
   - **(a)** A ball seen still for ≥ 2 s is evidence of a stoppage even if the players
     move, except in the penalty area outside the goal area, where the goalkeeper may have it in
     their hands.
   - **(b)** `D` is not left while the ball is still stationary: the stoppage ends when it is kicked.

   Covers cases 2 and 3.
3. **P3 · Line rules with direction** (corrects v3):
   - a ball lost next to the line **moving inwards at > 2 m/s** is a restart already taken:
     live play;
   - a ball that reappears next to the line **at > 2 m/s** is play, not a restart;
   - a ball that reappears still only counts as `D` if it **stays still ≥ 1 s**.

   Covers cases 4, 5 and 6.
4. **P4 · Contact to gain possession** (case 7). Only if the diagnostics show many
   back-and-forth team changes in < 3 s.
5. **P5 · Last-touch rule** (case 8). Low priority.
6. **P6 · Perspective on the far touchline** (case 9). Only if the diagnostic shows it.

Outside v4: inferring possession without the ball (case 10) and penalties (case 11).

## 5. Diagnostics without GT and decision criterion (fixed before seeing them)

They are added to `evidence_totals.v4_diagnostics` of the `.summary.json`. They are only counts and minutes, and
they do not change any label: v3's CSV stays identical.

| Proposal | Diagnostic | Goes into v4 if… |
|---|---|---|
| P1 | `duels` (minutes of duel, H↔A changes ≤ 0.5 s from a duel) and `structure` (back-and-forths < 3 s) | ≥ 20 % of v3's H↔A changes happen ≤ 0.5 s from a duel |
| P2 | `still_ball_by_zone` (minutes with the ball still ≥ 1 s labelled live, by zone) and `dead_exits` (exits from `D` with the ball still and minutes until it moves) | they add up to ≥ 1 min labelled live outside the goalkeeper's zone |
| P3 | `line_gaps` (`D` gaps at a line lost moving inwards fast, reappearing fast or that move in < 1 s) | they add up to ≥ 0.5 min |
| P6 | `out_episodes` (balls going out per side and "out → in" rebounds in < 1 s) | one side has ≥ 3 times more rebounds than the opposite one |
| Reference | `structure.dead_runs` (number and duration of the `D` stretches) | Compare with the literature: ≈ 100–130 stoppages of 13–27 s |

**Public evaluation #5 (the last one).** v4 is only evaluated if its diagnostics show the
intended effect without side effects:
- `D` between 41 % and 49 %;
- no more H↔A changes than v3;
- deterministic.

Criterion already fixed: if v4 does not reach **spellF1 ≥ 0.3895 and macroF1 ≥ 0.6901**, v3 is frozen.
Passing that threshold only rules out a regression: with 17 possessions, it does not prove an improvement.

## 6. Result of the diagnostics and decision (Edu's run with v3, without GT)

Same SHA-256 as v3 (`a5372e72…`): the diagnostics do not change labels.

| Proposal | Result | Criterion | Decision |
|---|---|---|---|
| P1 · Duels | 18 of 241 H↔A changes ≤ 0.5 s from a duel (7.5 %); 0.54 min of duel with the ball visible | ≥ 20 % | **Does not go in** |
| P2 · Still ball | 0.73 min labelled live with the ball still outside the goalkeeper's zone + 0.05 min of exits from `D` before the kick = 0.78 min | ≥ 1 min | **Does not go in** |
| P3 · Lines | lost moving inwards fast 0.12 min; reappearing next to the line fast 9.92 min (32 gaps); still ball that moves in < 1 s 0 min | ≥ 0.5 min | **Meets it, but is not applied** (deviation, see below) |
| P4 · Back-and-forths | 70 back-and-forths of < 3 s (1.8 s on average), 140 of the 241 H↔A changes (58 %) | "many" | **Goes in** (as a minimum duration of the change, see below) |
| P6 · Perspective | rebounds per touchline 4 versus 1 | ≥ 3× | **Meets the ratio, but is not applied**: 4 events, effect ≤ 5 s |
| Reference | 100 `D` stretches, median 15.6 s, mean 26.1 s, p90 56 s | literature: ≈ 100–130 stoppages of 13–27 s | v3's stoppage structure is plausible |

**Why P3 is not applied.** The criterion measured how many minutes would change, not whether they were false `D`.
The data point the opposite way to the hypothesis: the 32 gaps that reappear fast next to the
line last 18.6 s on average, as long as a throw-in or a corner, and there are as many as those
restarts in a match. Also, over the whole match the ball is only seen still for 2.6 min. Most
likely the tracking does not see the ball while it is held or placed for the restart, and
picks it up again when it is taken, already moving. Applying P3 would turn ≈ 10 min of probably
correct `D` into live play.

**Why P4 is implemented as a minimum duration and not as "contact".** With the ball visible
there are hardly any duels (0.54 min): the ball disappears precisely at the contacts, so measuring changes of
direction or speed is not reliable. The challenge itself offers another control signal ("a player
retains the ball for a few seconds"). So a change of possession is required to last ≥ `min_change_s`
= 3 s, the same threshold the diagnostic was defined with before seeing the data. It only affects
back-and-forths with no stoppage in between: stretches next to a stoppage are not touched.

**Expectation for v4, fixed before running it.** `D` identical to v3's (41.05 %), fewer
H↔A changes and fewer possessions (the 70 flickers add up to 140 changes), no back-and-forth of < 3 s
and deterministic. If it is met, it spends public evaluation #5 with the fixed criterion (spellF1 ≥
0.3895 and macroF1 ≥ 0.6901; otherwise, v3 is frozen).

## Sources

- Vidal-Codina, Evans, El Fakir, Billingham (2022). *Automatic event detection in football using tracking data*. Sports Engineering. https://arxiv.org/abs/2202.00804
- Link, Hoernig (2017). *Individual ball possession in soccer*. PLOS ONE. https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225
- Kim et al. (2026). *PathCRF: Ball-Free Soccer Event Detection via Possession Path Inference from Player Trajectories*. https://arxiv.org/abs/2602.12080
- IFAB, Laws of the Game (The FA's reproduction): Law 8 https://www.thefa.com/football-rules-governance/lawsandrules/laws/football-11-11/law-8---the-start-and-restart-of-play · Law 13 https://www.thefa.com/football-rules-governance/lawsandrules/laws/football-11-11/law-13---free-kicks · Law 16 https://www.thefa.com/football-rules-governance/lawsandrules/laws/football-11-11/law-16---the-goal-kick
- Goalkeeper 8-second rule (IFAB, 2025): https://www.tntsports.co.uk/football/what-is-the-eight-second-goalkeeper-rule-how-long-can-goalkeepers-hold-the-ball-when-will-the-rule-come-into-place_sto20086781/story.shtml
- Duration of stoppages: https://pmc.ncbi.nlm.nih.gov/articles/PMC10442814/table/T3 · https://theanalyst.com/articles/premier-league-rules-throw-ins-goal-kicks-ball-in-play
