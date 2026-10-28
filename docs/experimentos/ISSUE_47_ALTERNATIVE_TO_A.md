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

Load with `only_alive=False`: kloppy's default (`True`) drops every dead-ball frame, which would remove `D`
from the evaluation.

**This is not the same definition as our ground truth.** Ours comes from Metrica's corrected tracking, DFL's from TRACAB
and the DFL's own possession rule. Absolute scores on DFL are therefore not comparable with the 0.2433 target or with
other teams. The comparison is **paired**: A and the variant on exactly the same frames, labels and evaluator.

### 1.2 Domain gap and degradation profiles

DFL tracking is corrected, keeps player identities and has the ball almost always. Our ATD is automatic, has
46 anonymous slots and **no ball in 41% of graded frames** (DATA.md), disproportionately in the boxes and in aerial
duels. No simulation reproduces that domain; the profiles below are a **documented proxy**, not proof that they
represent it. All of them are fixed now, before any scoring:

| Profile | Ball | Players |
|---|---|---|
| `clean` | as loaded | as loaded (identities removed, team kept) |
| `gaps-short` | gaps with exponential length, mean 0.5 s | `clean` |
| `gaps-long` | gaps with exponential length, mean 4 s | `clean` |
| `gaps-crowded` | mean 2 s; gap starts drawn with probability proportional to the number of players within 5 m of the ball, a proxy for DATA.md's "boxes and aerial duels" | `clean` |
| `full` | as `gaps-crowded` | tracks cut into segments of exponential length (mean 60 s), each given a new anonymous slot of the same team; Gaussian position noise, σ = 0.10 m for players and 0.20 m for the ball |

How gaps are sampled, for every profile except `clean`:

- per half, independently; frames whose ball is already missing in DFL stay missing and count towards the target;
- draw a start frame and a length, truncate the gap at the end of the half and at 30 s, and mark it missing; repeat
  until **41% of the half's frames** have no ball; the last gap is shortened so the half lands on 41% exactly;
- alive and dead frames are equally eligible, because the challenge ATD loses the ball in both;
- seeds `47`, `48`, `49` for every degraded profile.

Each corrupted observation is generated **once** per match, profile and seed, hashed, and fed **identically** to A
and to the variant. Results are reported for every profile and seed, `clean` included. A gain on one profile or seed
is not enough on its own (§3.6).

### 1.3 Inputs and targets

`BallPossession` and `BallStatus` are **evaluation targets only**. The adapter passes the models positions, speeds and
the team of each slot, nothing else: neither target field nor any feature derived from it enters either model. A test
in the adapter checks this: removing or shuffling both target fields must leave the inference inputs byte-identical
(same hash).

The **scoring mask** comes from the ground truth and the period metadata: a frame is scored when it has a label and
lies inside a half. It never depends on the degraded observation: hiding the ball does not remove a frame from
evaluation.

**Smart Tagging.** A uses the challenge match's automatic Smart Tagging; DFL has no equivalent. The main comparison
gives **both models no tagging at all** (empty tag list). This is a handicap for A that the variant shares if it also
uses tags; it is reported, not corrected. The DFL human-coded events are permitted external data, but turning them
into restart or team signals would be a near-oracle input that the challenge match does not have. **They are not used
in the main comparison.** If anyone proposes an event-assisted condition, it is reported separately and never decides
adoption.

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

**As implemented** ([`heldout/`](../../heldout/README.md)): the adapter writes each degraded match as a bundle in the
challenge's file format (EPTS metadata and raw tracking, and an empty Smart Tagging file), and every model runs through
P0 (`python -m solution.predict`) with its data folder pointed at that bundle, so no model is modified. Each DFL half is
placed at the start of the matching challenge half; the rest of the block has no tracking and is never scored. The
image is `docker/heldout.Dockerfile`: the main image's pinned base and the same numpy and pandas versions, plus kloppy
to read the DFL files.

### 3.2 Metrics, per held-out match and condition

1. **spellF1** (primary) and **macroF1** (tie-break), from the official code.
2. **Boundaries and restarts**: transition F1 at 12 and 25 frames, mean absolute latency.
3. **False short possessions**: predicted H/A spells shorter than 25 frames (1 s) whose best temporal IoU with any
   ground-truth spell **of the same team** is below 0.3 (the lowest official threshold), counted on scored frames
   only. Reported as a **rate per 90 minutes of scored time**, so it is defined even when a model has none.
4. **Possession structure**: number of spells and median duration, against the labels.
5. **Runtime** and peak memory for the full provided game (limit: 30 min on CPU).

### 3.3 Uncertainty

The same construction as the official `bootstrap_spell_f1`, made **paired**:

- **Unit**: whole ground-truth possessions of one match, as the official evaluator resamples them. Possessions are
  never split, so no possession crosses a resampling boundary and nothing is joined artificially.
- **Pairing**: each draw picks the same possessions for A and for the variant; the statistic is
  `spellF1(variant) − spellF1(A)` on that draw, computed as the official code does (matched flags per IoU threshold,
  predicted spell count fixed).
- **Draws and interval**: 1,000 draws, seed `0`, **90% percentile interval** (5th–95th), the official percentiles.
- **Combining matches**: matches have **equal weight**. In each draw, every held-out match is resampled independently
  and the statistic is the mean of the per-match differences.
- **Point estimates** are the full-match spellF1 values from the official code, not the bootstrap mean.

With two held-out matches this interval describes uncertainty **conditional on those two matches**. Even if it
excludes zero, it is not evidence of generalisation to unseen matches. The report keeps the two claims apart.

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

The thresholds below are **internal team acceptance criteria** proposed by Edu, not official challenge requirements.
They are agreed in PR #48 before any held-out scoring, and do not change afterwards.

Recommend **adopting the variant** only if all of these hold:

1. **Eligible and reproducible**: Edu regenerates its CSV for the provided game twice from a clean checkout, with
   identical SHA-256 and all hashes recorded (§5).
2. **Better on held-out matches, robustly**:
   - averaged over the degraded profiles and seeds, the variant's spellF1 is higher than A's on **each** held-out
     match;
   - it is higher on **at least 3 of the 4** degraded profiles (each profile averaged over its three seeds);
   - for the `full` profile, the 90% interval of the mean paired difference (§3.3) excludes zero for every seed.
3. **No important regression**, per held-out match on the degraded profiles averaged as in 2:
   - macroF1 drops by no more than **0.02**;
   - the false-short-possession rate is at most **1.2 × A's rate + 1 per 90 min** (the additive term keeps the rule
     defined when A's rate is zero).
4. **Runs in time**: under **30 minutes** for the provided game on the reference hardware: AMD Ryzen 5 3600
   (6 cores, 12 threads), 31 GB RAM, inside the project's Docker image. Recorded together with the GitHub runner time.

Otherwise **keep A**. "Keep A, no demonstrated improvement" is a valid outcome of #47.

The share-of-`D` and possession-count flags of §3.4 stay **advisory**: agreeing with A's aggregates is not an
accuracy target. Results on `clean` are reported but do not decide.

### 3.7 Football acceptance scenarios

Owner: Pablo (@PabloCordoba3). Specification dated **28 October 2026**, before running these new scenarios.
These are proposed synthetic acceptance checks for the football review in #47. They complement the external
comparison in sections 1-3.6; they do not change its split, metrics or adoption rule. Review with Jimy and Edu is
pending. The scenarios below are specifications, not new passing test results.

#### Inputs and expected outputs

All trajectories, contacts, events and reference labels must be invented independently of the challenge game.
Use 25 fps, metres, explicit observation masks and half-open intervals, following the
[data contract](../CONTRATO_DATOS.en.md). Read pitch dimensions and full-output alignment from `games.py`.
Local fixture offsets below are relative to the beginning of an invented sequence, never match frame numbers.
`H50` means 50 consecutive H frames; `gap50` means 50 missing ball observations, not 50 X reference labels.

Every executable fixture must record its ID, observation arrays, team metadata, periods, optional automatic-style
events, expected labels and boundary observability. Geometry must distinguish a controlled reception or pass from
mere proximity. An aerial situation is represented by its observable 2D evidence and missingness; no ball height
or referee decision is inferred from an unavailable input. References and latent synthetic event times go only to
assertions or the evaluator, never to model inputs or event-window boundaries copied from those references.

| ID | Invented situation and available evidence | Expected behaviour and failure criterion |
|---|---|---|
| FA01 | H controls for 50 frames, A makes a controlled reception and keeps the ball for 30 frames (1.2 s), then H controls for 50. Close ball-player motion supports each control period. | Preserve `H50 A30 H50`. Removing A because it is short, inventing D or adding another possession fails. |
| FA02 | H controls, A deflects the ball with two nearby observations, then 12 loose-ball frames lead back to H. Contrast with FA01 using contact and subsequent motion, not duration alone. | One H possession throughout. The deflection is not controlled possession; an A spell or D cut fails. |
| FA03 | After H control, both teams contest an aerial/loose ball for 40 frames, with ambiguous proximity and no subsequent A control; H then receives. | Retain H through the contest. A simple aerial touch cannot create an A spell or a stoppage. |
| FA04 | H controls for 50 frames, the ball is hidden for 50 while players remain observed, then H control returns for 50. There is no exit or restart evidence. | One H possession, no D. Missing ball coordinates must remain unavailable rather than become zero positions or dead-ball evidence. |
| FA05 | H controls for 50 frames, the ball is hidden for 50 with no discriminating team evidence, then A has 50 frames of clear control. | Exactly one H-to-A change and no D; A must be established by the first independently confirmed A control. The true change time inside the gap is unidentifiable: report its uncertainty instead of requiring an exact hidden frame. |
| FA06 | H controls for 50 frames, a sustained observed exit supports a 75-frame stoppage before a throw-in/corner, then a contextual restart leads to 50 frames of H control. Use separate preparation/stoppage evidence for a free-kick variant. | `H50 D75 H50` on a clean fixture. The two H spells remain separate; merging them or extending D past the supported restart fails. Cover throw-in, free-kick and corner contexts separately. |
| FA07 | A placed ball and an automatic-style restart window accompany preparation, gradual acceleration and subsequent clear H control. Include unsmoothed motion and a centred 25-frame smoothing variant. | One D-to-H boundary. Preparation is not live control merely because a player is nearest, and the entire tag window is not D. Report error against the invented physical restart separately from the detector's movement-confirmation time. |
| FA08 | At the start of an invented second half, preparation near the centre precedes a supported kick-off. Repeat with tag edges shifted by -25, 0 and +25 frames and with unrelated earlier movement away from the centre. | With sufficient observable support, D precedes the restart and the first supported owner follows it. Record missed/early/late restarts for each shift; unrelated movement must not release D. No exception may depend on a published challenge kick-off frame. |
| FA09 | End one half with H control, leave an unscored interval, then start another half with A control or with no observations/context. Change the preceding half while holding fitted parameters and second-half evidence fixed for this reset check. | No cross-half possession, derivative, confirmation or held state. Outside blocks is X. The second-half decoding is unchanged by the previous half's final state; the signal module leaves unsupported initial evidence invalid. Record any final-decoder prior or abstention policy separately. |
| FA10 | An initial kick-off window exists but the ball is missing throughout it; alternatively, remove the window and all other stoppage/control evidence. | P2 may emit its documented pre-window context but cannot claim a confirmed restart or label the whole window D solely from that tag. With no supporting evidence its signals remain invalid. A complete model's inferred labels do not count as observed restart evidence. |

Run every applicable scenario with H and A exchanged, updating team metadata and expected labels consistently.
Also translate the local sequence within a half and permute same-team slots: expected football behaviour must not
depend on a privileged team, an absolute offset or stable slot identity. Respect the half boundaries when translating.

#### Assertions and interpretation

Check two levels separately:

1. **Signal and decoder checks:** controlled synthetic evidence verifies contact versus control, invalid masks,
   tie handling, exact boundary dating and resets. These isolate a component; they do not establish that the
   component can recover that evidence from noisy positions.
2. **Geometry-to-output checks:** invented tracking and optional imperfect events pass through the normal model
   path. Reference labels are kept separate. Compare A and the named variant on the same observations, recording
   each model/configuration identity; do not alter A to satisfy a scenario.

For clean, observable boundaries (FA01, FA02, FA03, FA04 and FA06), the target is the stated run sequence with
**zero-frame boundary error**; continuous H cases must have no extra spell. This is a strict clean-fixture target,
not an official accuracy requirement or an instruction to tune a model. A model failure is retained as a finding.
For FA05, report the last observed H control, first confirmed A control, predicted transition and its position
relative to that observable bracket. Do not score an arbitrary hidden transition as if it were observable.
For FA07-FA08, report topology, missed/spurious restarts and signed/absolute boundary error in frames and seconds;
use paired differences on the same fixture, without introducing a pass threshold after seeing the outputs.
FA09-FA10 have the explicit reset/validity assertions in their rows rather than an invented exact restart target.
FA09 tests state isolation with calibration fixed. A's documented self-calibration and cross-half ball-free fitting
can legitimately change second-half emissions when first-half observations change; report that separately rather
than treating every such change as state leakage.

Keep raw H/A/D/X output and abstention counts. Report filled temporal metrics separately according to the official
evaluator; forward-filling X must not hide abstentions in a scenario result. Record the short true possession
retained/missed, false team spells and false D cuts as separate outcomes. A higher aggregate score cannot conceal
a failed scenario. These checks inform the football review; only section 3.6 governs the adoption recommendation.

#### Existing evidence and remaining work

The baseline review at `fb7412f` ran in Docker on 28 October 2026: 60 existing P2/restart/temporal/harness tests
and 11 candidate A synthetic checks passed. This is the starting point, not execution of FA01-FA10.

| Existing source | Reusable coverage | Remaining acceptance work |
|---|---|---|
| [`solution/a_opus/tests.py`](../../solution/a_opus/tests.py): `test_p3_control_cases`, `test_p3_p4_scenarios`, `test_p4_first_frames_of_a_half` | Fast pass versus reception, deflection, duel, short recovery, evidence-level gap transition and initial D | Shared fixtures, team mirrors and a distinction between supplied evidence and evidence recovered from tracking |
| [`tests/test_temporal_control.py`](../../tests/test_temporal_control.py) | Missing ball without forced D, control confirmation, short possession, same-team stoppage and half reset | Apply the shared cases to each declared model; preserve uncertainty about transitions hidden in gaps |
| [`tests/test_dead_ball.py`](../../tests/test_dead_ball.py) | Exit/re-entry, initial context, unknown restart, centre requirement and no speed across gaps/halves | Combined shifted-window kick-off cases and supported versus unsupported restart outcomes |
| [`tests/test_smoothed_restarts.py`](../../tests/test_smoothed_restarts.py) | Gradual acceleration, search limits, event/half boundaries, zones and smoothed trajectories | Separate physical restart error from confirmation timing; the general preparation fix does not resolve the separate initial-kick-off rule |
| [`heldout/tests.py`](../../heldout/tests.py) | Target separation, deterministic degradation, common inputs and complete/current result identities | Keep external evaluation under Edu's frozen protocol; synthetic acceptance is not independent real-match validation |

The next implementation step is `tests/test_issue47_football_scenarios.py`, reusing existing helpers where useful.
No new executable fixtures, model changes or external evaluations are included in this specification step.
Jimy reviews whether the evidence represents football control; Edu confirms evaluation separation and reporting.
The first Pablo checklist item remains incomplete until executable cases and their results are linked.

#### Development and reserved evaluation

FA01-FA10 and all concrete examples published here are **development scenarios**. Their descriptions and reference
outcomes are available to the implementer; they cannot provide an independent held-out claim. Edu must agree and
record any reserved synthetic families, parameters, seeds and sampling procedure before the variant is frozen,
keep their generated cases/results out of model development, and run the frozen pair once under that procedure.
A different seed of the same published generator alone does not establish independence. No reserved synthetic
set has been agreed or evaluated in this step, and the DFL split in section 2 remains unchanged.

Record an outcome per scenario and symmetry/offset/noise condition: model identity, fixture version, expected
behaviour, raw-label result, boundary observability/error, regression and interpretation. Do not retune against
reserved results; a continuation needs new unused evidence and an agreed protocol. Missing authorised video or
reference labels must be recorded as a limitation of any proposed blind review. The challenge viewer supports
qualitative understanding only: no human labels, correctness votes or frame-specific corrections on BAR-ATH.

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
