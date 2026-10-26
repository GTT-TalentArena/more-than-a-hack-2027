# Issue #47: an alternative to candidate A, evaluated on other games

Single report for [#47](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/47). This first version fixes
**what external data is eligible** and **how A and the variant will be compared**, before any variant is scored.
Results and the recommendation are added to the same file on Thursday 29 and Friday 30 October.

Rules checked against the **current official repository** (commit `f8f2629`, 23 Oct 2026), not only the copies in
this fork, which are one commit behind:

- No hand labels, events or corrected tracking of the provided game, **for any purpose**, validation included.
- The public 5-minute window is "not for ranking, not training data and not a tuning set". **It is not used to choose
  between A and the variant** (see §3.5).
- External data must be **about other games**, accessible to the organisers and explained in the technical document.
  Hand-labelled data from other games is allowed in any amount.

## 1. External data: eligibility

| Source | What it has | Labels | Licence and access | Contamination with BAR–ATH 2024-25 | Decision |
|---|---|---|---|---|---|
| **DFL / IDSSE open data** (Bassek et al., 2025) | 7 full matches, Bundesliga and 2. Bundesliga 2022/23. TRACAB Gen5 optical tracking at 25 Hz, plus manually coded events | Per frame: `BallStatus` (0 = inactive, 1 = active; inactive when the referee interrupts play) and `BallPossession` (1 = home, 2 = away; "defined by the player in control of the ball") | **CC BY 4.0**, released with the DFL's authorisation. figshare DOI [10.6084/m9.figshare.28196177](https://doi.org/10.6084/m9.figshare.28196177). Loads with `kloppy.sportec.load_open_tracking_data(match_id)` in the pinned `kloppy==3.18.0`; each frame exposes `ball_state` and `ball_owning_team` | None: German league, other season | **Eligible.** Main held-out source |
| **Metrica Sports sample data** | 3 anonymised matches (games 1–2 in CSV, game 3 in EPTS FIFA format, the same format as our ATD) with synchronised events | No per-frame possession: it would have to be derived from the events (team of the controlling event, ball-out and set-piece events), which is an approximation | **No licence file.** The README only asks to "be responsible" and to acknowledge the source | None: anonymised, published in 2019–2021 | **Pending.** Ask the organisers (Metrica itself) before using it. Useful as a second held-out source and to test the EPTS adapter |
| **SkillCorner open data** | 10 A-League matches, broadcast tracking at 10 fps | A per-frame possession field produced by SkillCorner's own algorithm, not by humans | MIT | None | **Not for evaluation**: its labels are another model's output and the camera differs. At most for robustness checks |
| **PFF FC World Cup 2022** | 64 matches, broadcast tracking and events | Events | Terms of use not found; registration form | None | **Not used** unless its terms are confirmed |

Not considered: event-only sources (StatsBomb, Wyscout) because they have no tracking to run A on.

### 1.1 How DFL labels map to ours

| DFL frame | Our label |
|---|---|
| `ball_state` inactive | `D` |
| `ball_state` active, `ball_owning_team` = home | `H` |
| `ball_state` active, `ball_owning_team` = away | `A` |
| missing or outside the two halves | `X` (not scored) |

**This is not the same definition as our ground truth.** Ours comes from Metrica's corrected tracking, DFL's from TRACAB
and the DFL's own possession rule. Absolute scores on DFL are therefore not comparable with the 0.2433 target or with
other teams. The comparison is **paired**: A and the variant on exactly the same frames, labels and evaluator.

### 1.2 Domain gap

DFL tracking is corrected, keeps player identities and has the ball almost always. Our ATD is automatic, has
46 anonymous slots and **no ball in 41% of graded frames** (DATA.md). Each held-out match is therefore evaluated in
two conditions, both fixed now:

- **clean**: DFL tracking as loaded;
- **degraded**: identities replaced by anonymous team slots, and ball positions removed in runs until 41% of each
  half's frames have no ball (DATA.md's figure, the only statistic of the provided game used). Run lengths follow an
  exponential distribution with a 2 s mean (an assumption, not estimated from the provided game). Seed `47`.

The degraded condition is the primary result: it is the closer of the two to the game we are scored on.

## 2. Data split, fixed before training or scoring

Split by **match**, never by frame. Reserved for evaluation only, never for training, tuning or debugging:

| Role | Matches |
|---|---|
| **Held-out evaluation** | `J03WN1` (VfL Bochum vs Bayer 04 Leverkusen, Bundesliga) · `J03WR9` (Fortuna Düsseldorf vs 1. FC Kaiserslautern, 2. Bundesliga) |
| Training and development | `J03WMX` · `J03WPY` · `J03WOH` · `J03WQQ` · `J03WOY` |

One reserved match from each division. Known limitation: Fortuna Düsseldorf plays all five 2. Bundesliga matches, so
the reserved 2. Bundesliga match shares a team and a stadium with four development matches. `J03WN1` has no such
overlap and is reported separately for that reason.

If Metrica's sample data is cleared (§1), Sample Game 3 joins the held-out set; games 1–2 go to development.

## 3. Comparison protocol

### 3.1 What runs

- **A**: candidate A v1.6, unchanged, at the commit recorded in §5.
- **Variant**: its own module or configuration name, at a commit fixed **on Wednesday 28** before any held-out run.
- Both through the same adapter, the same official metric code (`evaluation/possession_metrics.py`) and the same
  Docker image. The adapter feeds DFL frames to each model in the model's normal input form; it must not change either
  model's logic.

### 3.2 Metrics, per held-out match and condition

1. **spellF1** (primary) and **macroF1** (tie-break), from the official code.
2. **Boundaries and restarts**: transition F1 at 12 and 25 frames, mean absolute latency.
3. **False short possessions**: predicted spells shorter than 1 s with no matching ground-truth spell.
4. **Possession structure**: number of spells and median duration, against the labels.
5. **Runtime** and peak memory for the full provided game (limit: 30 min on CPU).

### 3.3 Uncertainty

Two to three held-out matches are too few for a significance test. We report:

- every match separately, and the **paired difference** (variant − A) per match;
- within each match, a **block bootstrap of the difference** over 5-minute blocks (1,000 draws, seed `0`), so that
  frames are never treated as independent samples.

Wins measured only on synthetic fixtures are reported as provisional, not as evidence of generalisation.

### 3.4 On the provided game (no ground truth)

Full output for both models, validated (199,319 rows, frames 0..199318), with aggregates only: number and median
duration of possessions, share of `D` and `X`. These are plausibility checks, not accuracy. A plausibility flag is
raised if the variant's share of `D` leaves 40–55% or its possession count differs from A's by more than 30%. A flag
does not decide anything; it has to be explained in §4.

### 3.5 The public window

Not used for this decision. Each output is checked with `validate_submission.py` (format only), as the rules allow.
**Neither model is scored on the public ground truth for this comparison.**

### 3.6 Decision rule, fixed now

Recommend **adopting the variant** only if all of these hold:

1. **Eligible and reproducible**: Edu regenerates its CSV twice from a clean checkout, with identical SHA-256 and all
   hashes recorded (§5).
2. **Better on held-out games**: in the degraded condition, spellF1 is higher than A's on **every** held-out match,
   and the bootstrap interval of the mean paired difference excludes zero.
3. **No important regression**: macroF1 does not drop by more than 0.02 on any held-out match, and false short
   possessions do not increase by more than 20%.
4. **Runs in time**: under 30 minutes on CPU for the provided game.

Otherwise **keep A**. "Keep A, no demonstrated improvement" is a valid outcome of #47.

## 4. Results

*To be completed on 29 October.*

## 5. Reproduction record

*To be completed on 29 October: commits, configuration hashes, input hashes (DFL files as downloaded), dependency
versions, commands, durations and hardware, and the two SHA-256 of each CSV.*

## Sources

- Bassek, Rein, Weber and Memmert (2025). *An integrated dataset of spatiotemporal and event data in elite soccer.*
  Scientific Data. [PMC11787359](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/)
- [metrica-sports/sample-data](https://github.com/metrica-sports/sample-data) · [SkillCorner/opendata](https://github.com/SkillCorner/opendata)
- [PFF FC, Enhanced 2022 World Cup dataset](https://www.blog.fc.pff.com/blog/enhanced-2022-world-cup-dataset)
- Official rules: [RULES.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md) ·
  [FAQ.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/FAQ.md)
