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

Verification on 28 October: the organisers approved the declared IDSSE use in
[official issue #16](https://github.com/metrica-sports/more-than-a-hack-2027/issues/16), answered and closed on
26 October. Their conditions include attribution, access/reproducibility and choosing thresholds on other games.
This supports the source choice; it does not certify this team's separate historical development process.
Section 3.10 records the access, reader and split checks, plus the remaining confirmations for Edu.

### 1.1 How DFL labels map to ours

| DFL frame | Our label |
|---|---|
| `ball_state` inactive | `D` |
| `ball_state` active, `ball_owning_team` = home | `H` |
| `ball_state` active, `ball_owning_team` = away | `A` |
| missing or outside the two halves | `X` (not scored) |

Load with `only_alive=False`: kloppy's default (`True`) drops every dead-ball frame, which would remove `D`
from the evaluation.

The X row describes an unknown **exposed by the reader**, not a guarantee that kloppy preserves every unknown
raw field. The installed 3.18.0 Sportec reader maps any possession value other than 1 to away, and any status
value other than 1 to dead, including its missing-field defaults. Its raw-field assumptions must be checked on
development files before accepting converted targets; section 3.10 distinguishes the synthetic adapter check
from a real-file conversion audit.

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

The executable cases are in [`tools/football_acceptance.py`](../../tools/football_acceptance.py), with assertions in
[`tests/test_issue47_football_scenarios.py`](../../tests/test_issue47_football_scenarios.py). Section 3.8 records their
initial execution. Jimy still reviews whether the evidence represents football control; Edu confirms evaluation
separation and reporting. The fixtures and results support the first Pablo checklist item, pending team review.

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

### 3.8 Synthetic implementation and starting results

Pablo's local step 3, **28 October 2026**, on branch `codex/issue-47-football-validation`. The specification is
committed as `b205cf4`; the implementation and initial results were evaluated as working-tree changes and later
committed locally as `4c741b0`. Candidate A, P2,
temporal control, the official metrics and their configurations are unchanged. No improvement variant has been
provided to this runner, so these results do not compare A with Jimy's future variant or decide adoption.

The generator implements FA01-FA10 as **17 concrete worlds**, including three restart types, two smoothing
conditions, three kick-off tag shifts and supported/unsupported starts. Each runs unchanged, with teams exchanged,
with a 17-frame unscored offset and with same-team slots permuted: **68 geometry-to-output runs**. The shifted
kick-off cases actually occur in period 2 after an invented first half and break. No reserved synthetic family
or external match was used. Observation/bundle identity tests verify that changing reference labels does not
change model inputs.

Compact runs write EPTS XML/TXT and imperfect synthetic tags to a temporary input folder, then call A's normal
pipeline with its default configuration and self-calibration. Only `games.source_frames`, the half blocks and the
bundle length are replaced within the compact test scope. The resulting CSV is validated against that compact
length; it is not presented as a competition submission. A separate full-length smoke run uses the unchanged
`games.py` timeline: **199,319 valid rows**, repeated with identical SHA-256. It checks format/determinism, not
whether the scenario's football targets hold in a full-length match. All temporary bundles and predictions are
removed after checking them.

Docker environment: Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6, existing `gtt-mtah:local` image. The combined
shared/heldout-harness regression suite passed **135 tests**; candidate A's original **11 synthetic checks** also
passed. The new suite contains **20 tests** for fixture integrity, honest failure/abstention reporting, observable
boundary brackets, contact versus control, P2, half isolation and deterministic geometry-to-CSV execution.
Passing these software/component tests does not mean A passes every football acceptance target.

| A geometry-to-output cases | Pass | Fail | Diagnostic only |
|---|---:|---:|---:|
| FA01: short recovery | 0 | 4 | 0 |
| FA02-FA04: deflection, contest and same-team occlusion | 12 | 0 | 0 |
| FA05: different team after a gap | 0 | 4 | 0 |
| FA06: same-team stoppage/restart, three types | 0 | 12 | 0 |
| FA07-FA10: gradual restart, kick-off shifts, reset and unsupported evidence | 0 | 0 | 36 |
| Total | 12 | 20 | 36 |

The full pipeline can emit D over live reference frames in these short, simplified worlds even though supplied
team evidence passes the isolated decoder checks. The fixtures greatly simplify collective movement and offer
little data for label-free calibration. Keep those unmet targets as findings; do not attribute them to a specific
component or extrapolate them to real-match accuracy. Two team-swap mismatches occur in unsupported conditions
(FA09 without second-half ball evidence and FA10 without tags/ball): these flag A's team tie/prior behaviour,
not demonstrated cross-half state leakage. No slot-permutation or offset mismatch was observed.

The report retains raw X counts, false D frames, topology and signed boundary errors. Restart diagnostics use
one-to-one, same-team matching within **25 frames**, the one-second tolerance already reported in section 3.2;
missed and spurious restarts remain explicit. Hidden-gap timing uses its observable bracket rather than an exact
latent transition. Diagnostic cases are never counted as passes.

Reproduce from the repository root with a **new** report path:

```powershell
docker compose run --rm --pull never --entrypoint python evaluar -m unittest discover -s tests -p test_issue47_football_scenarios.py -v
docker compose run --rm --pull never --entrypoint python evaluar -m tools.football_acceptance --out /salidas/issue47-football/new-report.json --check --full-size-smoke
```

`--check` exits **1** when strict targets or symmetry checks fail, as in this baseline run; creating a report is
not a model-quality pass. Without it, zero only confirms successful report generation. Existing report paths are
rejected. Local evidence is `salidas/issue47-step3/report-delivery.json`, with commit/tree state, source/config/
observation/CSV hashes and environment, plus the accompanying test/report logs. The source hash identifies the
uncommitted implementation; it does not turn the preceding documentation commit into a code-reproduction commit.
Jimy/Edu review, a named improvement variant and independent evaluation remain pending for the later steps.

### 3.9 Football rule review

Pablo's local step 4, 28 October 2026. The available checkout contains A and P2; no separately named #47 variant
has been supplied for this review. These findings are a baseline handoff for Jimy, not his approval or a review of
undelivered code. The following questions and synthetic probes are fixed before collecting the new diagnostics:

1. Does A require motion compatible with control, or simply select the nearest player? Relate its distance kernel,
   relative-speed gate, touch contribution and switching cost to FA01-FA05. Inspect actual control and team evidence
   on the existing invented inputs rather than treating the decoder-only tests as complete control validation.
2. Which live/dead evidence is present when the full pipeline emits D in a live synthetic case? Observe A's
   individual dead-ball terms and its aggregate calibration diagnostics without changing any returned evidence,
   configuration or labels. Verify that observing the terms preserves the normal CSV byte for byte.
3. Can P2 refine the initial kick-off when supporting motion is inside the automatic window? Reuse FA08's three
   tag shifts. Then use its middle shift for four additional development probes: window ends at the true motion
   start, window includes only two moving frames, a five-frame missing-ball run covers the motion start, and a
   longer missing-ball run hides it until the ball has left the three-metre centre zone. Keep the physical
   trajectory/reference fixed; alter only the declared observation/window condition.
4. Does the same general restart rule handle smoothed acceleration and an unobserved boundary? Keep separate the
   first physical movement, first supported sustained movement and confirmation time. A missed or late boundary
   remains a finding; no published challenge frame or post-result threshold is introduced.

The initial trace found nonzero team evidence but zero dead-ball terms in FA01. A follow-up mathematical probe
was then specified and replayed the already published decoder fixture with dead evidence 0 and -0.1 (the latter is the existing
decoder-test value), to distinguish a scoring effect from missing control. This is supplied-evidence analysis,
not a modified candidate, parameter search or proposed adoption.

#### Control and live/dead findings

| Review | Existing mechanism and observed evidence | Football interpretation and question for Jimy |
|---|---|---|
| Contact versus control | A's `control_scores` combines a distance kernel with relative ball-player velocity; `proximity_llr` compares teams and discounts interpolated/isolated observations. `touch_llr` adds a bounded contribution. The supplied-evidence decoder retains a 1.2 s recovery while rejecting a deflection and a neutral duel. | A does more than choose the nearest player, but these are control proxies, not proof of a deliberate reception/pass. Ask Jimy to show the same physical cases through his declared variant, including a controlled short recovery and a touch without control. |
| The live/D decision can dominate otherwise usable control | On FA01, all 130 live-reference frames have nonzero team evidence and 126 have control strength at least 0.6. Every captured dead-ball term is zero, yet the full pipeline emits D throughout. The collective-speed fit and learned ball-free weight are off on this small world; they do not explain positive D evidence here. | Do not describe this result as missing control or a failed speed-model fit. Review how the variant distinguishes live play when dead-ball evidence is neutral. Closeness alone cannot settle this, because a player preparing a restart is also close to the ball. |
| Neutral D has a structural scoring effect | The normal pipeline gives H/A scores `team/2`, `-team/2` and D score `dead + abs(team)/2`. At dead = 0, D equals the best live emission at each frame. In the supplied 130-frame recovery probe, all-D scores 26 versus 20 for `H50 A30 H50`, which pays two H/A changes. The existing test's dead = -0.1 yields the live sequence. | This explains a route to all-D in the toy world; it does not establish real-match frequency or justify a blanket negative D prior. Ask Jimy which independent, reliable live signals address this trade-off without turning preparation into live play. |
| Missing observations versus available control | FA05 has 100 original ball observations but 150 frames of available control: A bridges its exactly two-second gap. Those 50 extra frames are imputed, not additional measurements. | Keep original coverage, interpolation and inferred ownership separate. A straight-line bridge may miss a real recovery; the transition inside this gap is not observable at an exact frame. Ask how the variant dates such changes and exposes uncertainty. |
| Boundary dating and short possessions | A has a switching cost, not a universal minimum H/A duration. `date_team_changes` can backdate a change through supported control but stops at unsupported frames. D separately has a 50-frame minimum. | Do not equate rejecting flicker with deleting every short recovery. Check short true possessions and false team/D cuts separately, and review late control confirmation without assuming it dates the true first contact. |

Source anchors: [`control_scores`, `proximity_llr`, `touch_llr`, `dead_components`](../../solution/a_opus/evidence.py),
[`viterbi`, `date_team_changes`](../../solution/a_opus/decode.py),
[`pipeline.run`](../../solution/a_opus/pipeline.py) and [default configuration](../../solution/a_opus/config.py).
The review observer returns every original evidence array unchanged; all **17 observed prediction CSVs** match
separate ordinary runs byte for byte. It reads evaluator-only references after inference to summarise the output.

#### Initial kick-off and gradual restart findings

P2's initial-kick-off branch searches for three consecutive observations of movement at at least 2 m/s, within
the automatic event and with the motion start (or preceding observation) within 3 m of the pitch centre.
It does not require prior stillness, and it resets for each half. The general stillness-to-motion search is a
different branch; its one-second margin does not extend the initial-kick-off search beyond the event window.
These are the existing rules in [`dead_ball.detect`](../../solution/dead_ball.py), unchanged by this review.

| Invented condition | P2 result | Interpretation |
|---|---|---|
| FA08 event shifted -25, 0 or +25 frames, with enough central motion still visible inside the window | Confirms the period-2 restart at the invented physical onset in all three cases | Demonstrates these supported examples, not the unresolved real second-half boundary |
| Window ends at the onset, or contains only the first two moving frames | No confirmed restart | The half-open window/three-frame support requirement prevents confirmation; pre-window D context is retained and the remaining interval can stay unknown |
| Five missing frames cover the onset | Confirms five frames late, +0.20 s | No velocity is computed across the missing observations; later movement provides a later anchor, not a recovered observation of the hidden kick |
| Ball reappears after leaving the three-metre central zone | No confirmed restart | The centre requirement and lost onset limit recall; do not invent the missing boundary or introduce a fixture-specific frame correction |
| FA07 gradual acceleration, then its 25-frame smoothed version | General preparation confirms +4 and +6 frames after the invented first movement (+0.16 / +0.24 s) | Sustained threshold-level motion and the first physical movement are distinct; confirmation delay is not eliminated by recovering a preparation candidate |
| FA10 tag without ball observations, or no tag/evidence | No confirmed restart | A contextual window alone is not an observed resumption; preserve unknown signal validity |

P2 is **off by default in A**. Successful detector checks therefore do not demonstrate that A consumes those
signals or that enabling them would improve A. Its separate native set-piece evidence remains sensitive to the
tag window in these short worlds. Any proposed broader kick-off search or different live/dead rule needs a named
variant, an advance hypothesis and the existing independent comparison; this review changes none of them.

#### Reproduction and review handoff

```powershell
docker compose run --rm --pull never --entrypoint python evaluar -m unittest discover -s tests -p '*football*.py' -v
docker compose run --rm --pull never --entrypoint python evaluar -m tools.football_rule_review --out /salidas/issue47-football/new-rule-review.json
```

Docker: **24 tests pass** (the 20 acceptance tests and four rule-review checks), Python 3.11.17 / NumPy 2.4.6 /
pandas 3.0.6. [`football_rule_review.py`](../../tools/football_rule_review.py) accepts only a new output path and
uses invented inputs; it records source/config/observation hashes and verifies that its observer preserves A's
CSV. Local evidence: `salidas/issue47-step4/rule-review-final.json` and `salidas/issue47-step4-tests.log`.
No model parameters were changed; no private/public challenge GT or external reserved match was used to choose a rule.

For Jimy's handoff, provide the exact variant module, configuration and commit; review the five control rows and
the unsupported/late kick-off cases above; and identify any proposed change with its expected benefit, failure
mode and ablation. His confirmation and a variant-specific review remain pending. No message has been sent to
him and no shared issue checkbox has been changed. The local technical review supports Pablo's second checklist
item but does not certify team agreement or resolve the real-match kick-off boundary.

### 3.10 External validation readiness and handoff to Edu

Pablo's local step 5, **28 October 2026**. The existing DFL split and decision protocol remain fixed. The
[official rules](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md) and
[FAQ](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/FAQ.md) were checked again, together with
the positive IDSSE answer in official issue #16. Private team correspondence and Edu's acknowledgement have
not been verified; the current GitHub API refresh of the team comments was rate-limited.

#### Source, labels and access

The [dataset paper](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/) describes seven German 2022/23 games under
CC BY 4.0. BallPossession identifies home/away control; BallStatus distinguishes active/inactive play, including
referee interruptions. This supports the mapping in section 1.1, subject to provider-specific semantics.
The package has **no video footage**. Its event timing and tracking are different representations; a provider
event is not an exact visual contact boundary by default.

From the common Docker image, a metadata request to the pinned Figshare article **28196177, version 1** confirmed
21 files (metadata, events and positions for each of seven games), **2,627,505,889 bytes** in total and the
CC BY 4.0 licence URL. An HTTP **HEAD** for the `J03WMX` development positions file returned 200, with a declared
418,524,833-byte length. This confirms metadata/download-endpoint access from this machine, not completed
downloads or input MD5 verification. No match contents were downloaded, converted, opened or scored.
The metadata includes reserved match names; inspecting that public inventory does not inspect their observations.
Local access evidence: `salidas/issue47-step5/source-access.json`.

The held-out image was built from the existing Dockerfile and lock without changing dependencies. It imports
**kloppy 3.18.0**, NumPy 2.4.6 and pandas 3.0.6. A six-frame invented dataset, with the source reader mocked,
checked the repository adapter's D/H/A/X mapping, `only_alive=False`, Metrica coordinate conversion and retention
of a dead reference when ball coordinates are absent. This verifies adapter branches, not parsing actual DFL XML.

Inspection of the installed Sportec deserializer found the limitation noted in section 1.1: raw missing or
unrecognised possession/status can be silently converted to A/D before `heldout.convert` sees a frame. We have
not measured whether such raw values occur in the actual seven files. **Before freezing the conversion, Edu
must verify raw-field completeness/allowed values on development data and record how unknowns are handled.**
If a reader/adapter correction is needed, identify that change and its synthetic regression before evaluating
reserved matches. The successful mocked-reader check must not be cited as evidence that this assumption holds
in real files. The converter, reader and model code are unchanged in this step.

#### Split and separation checks

| Role | Fixed matches | Readiness |
|---|---|---|
| Development/training | `J03WMX`, `J03WPY`, `J03WOH`, `J03WQQ`, `J03WOY` | Code defaults match section 2; actual downloads/conversion and the raw-reader check remain for Edu |
| Reserved evaluation | `J03WN1`, `J03WR9` | No observations or labels read; direct calls without `--heldout` reject both IDs before the loader is reached |

The held-out Docker service mounts the repository read-only and local outputs; it has no challenge-data mount.
The **17 synthetic harness tests pass in this image**, including target-independent observation generation,
unchanged scoring masks when the ball is hidden, common-input hashes and rejection of incomplete/mixed results.
The adapter/guard probe is recorded in `salidas/issue47-step5/adapter-and-split-check.json`; the tests are in
`salidas/issue47-step5-adapter-and-harness.log`. No real-match comparison or accuracy claim follows from them.

Only positions, derived speeds and slot teams enter a model bundle. BallPossession/BallStatus are evaluator
targets, and DFL event labels are excluded from the main comparison, as fixed in section 1.3. Both models must
receive the same degraded input. The opt-in guard is not an access-control system and cannot establish whether
another team member has already inspected or used reserved data; Edu must confirm that history before the run.

#### Blind review feasibility

**No blind football comparison has been performed.** DFL provides quantitative reference labels and tracking,
but its package contains no licensed video. A 2D replay alone cannot establish an airborne touch, whistle or
every ambiguous control decision. No authorised independent video source has been verified in this step.

If suitable video and labels become available, the proposed handoff is for Edu to fix the source/access terms,
model/configuration commits, sample size/seed and stratification before review. Select disagreements by team,
live/dead and boundaries, with an agreement control sample; anonymise model names and retain the key separately.
Pablo records model 1/model 2/both/neither/ambiguous judgements on those **other games**, without tuning on the
reserved review or editing either output. Aggregate the outcomes after locking the judgements, and keep that
evidence separate from model development. This is a procedure awaiting agreement, not a completed or agreed run.
The challenge game and its local viewer cannot substitute for that independent labelled review.

#### Confirmation checklist for Edu

- [ ] Confirm receipt of the public IDSSE approval and record the required dataset citation in the final technical deliverables.
- [ ] Record the fetched article version, file hashes and successful real-file conversion; verify raw possession/status completeness and the reader's handling of unknowns on development files.
- [ ] Confirm which development games were used and that `J03WN1`/`J03WR9` remain unused for training, tuning, debugging or prior candidate selection.
- [ ] Identify the frozen A/variant commits and configurations, then execute the existing paired protocol once on the reserved games; report all profiles/seeds and incomplete evidence explicitly.
- [ ] Either supply a permitted independent video/reference source and agree the blind procedure in advance, or retain the explicit limitation that no blind video comparison was possible.

No confirmation has been sent on Edu's behalf and no shared checklist has been ticked. This step documents an
accessible permitted source, the fixed split and the local technical checks; team acknowledgement, real-file
conformance and any independent blind comparison remain explicit dependencies.

Environment reproduction (these commands do not fetch or evaluate a match):

```powershell
docker compose build heldout
docker compose run --rm --pull never --entrypoint python heldout -m unittest heldout.tests -v
```

The access probe uses `https://api.figshare.com/v2/articles/28196177/versions/1` and a development-file HEAD only.
Avoid the unqualified `fetch`/`convert` examples during development: those CLIs default to **all seven matches**.
If Edu performs preparation, specify development IDs explicitly; the inference guard alone does not reserve
those earlier preparation stages. Data, arrays, labels and reports stay under ignored `salidas/heldout/`.

## 4. Results

### 4.1 Pablo's local conclusions (29 October)

The local football acceptance and rule review are ready for team review. **There is no A-versus-variant result
or adoption recommendation yet.** No separately identified variant was supplied, no external game was scored
in this work and no independent blind review was performed. Do not treat the software test results below as
evidence that every football target passes or that the issue as a whole is complete.

| Pablo's contribution | Delivered evidence | Remaining dependency |
|---|---|---|
| Invented football acceptance cases | FA01-FA10, 17 worlds, 68 geometry-to-output probes; fixture/reference separation and invariance checks | Run the same declared cases on the frozen variant; retain failures and diagnostic-only cases |
| Control versus contact and restart review | Section 3.9 explains A's control proxies, neutral-D scoring, interpolation and supported/late/unknown P2 boundaries; observing all 17 A runs preserves their CSVs | Jimy's named variant, review and acknowledgement; the real second-half kick-off limitation remains unresolved |
| Independent source and split | Section 3.10 records public IDSSE approval, endpoint access, the existing five/two split and synthetic adapter/guard checks | Edu's acknowledgement, usage history and real-file conformance audit, including raw unknown fields |
| Blind football comparison | Feasibility limitation and conditional procedure recorded before any judgement | Permitted independent video/reference source and advance agreement; otherwise report that this review was not possible |
| Football interpretation in this report | Short recoveries, neutral contact, missing observations, dead-ball preparation and uncertain restart timing are distinguished | Complete the paired quantitative results and review before deciding adoption |

The recorded A baseline remains **12 passes, 20 failures and 36 diagnostic-only probes**, with two team-swap
flags in unsupported conditions. The failures are retained findings on simplified development worlds; they are
not real-match error rates. A's control proxy is richer than nearest-player contact, but usable team evidence
alone does not guarantee live possession when neutral D emissions and switching costs favour an all-D path.
Interpolation cannot observe a hidden recovery, and a late supported restart cannot recover the exact unseen
kick. These are concrete questions for the variant rather than reasons to change a threshold after the result.

The recommendation at this stage is to keep the existing candidate selection unchanged. Identify the variant,
resolve the source/reader and split-history checks, then use the already fixed paired protocol. Retain any
unresolved kick-off or blind-review limitation in the final team conclusion. No shared checklist, remote issue
or adoption decision was changed by this local closeout.

### 4.2 Paired external results

**Pending team execution.** Add A/variant commits, complete profile/seed coverage, paired metrics and uncertainty,
and the football interpretation here after the section 3.10 prerequisites are satisfied. There is currently no
measured gain, degradation or tie to report.

## 5. Reproduction record

### 5.1 Final local regression and evidence integrity (29 October)

All final checks use the existing Docker images and local synthetic fixtures/public software references. The
`evaluar` and `heldout` services do not mount challenge data. Model code, configurations, conversion code and
official metrics are unchanged on this branch relative to its starting commit `fb7412f`.

| Check | Result | Local log |
|---|---|---|
| Shared Python regression suite, including the 24 football tests | **122 tests passed**, 56.470 s | `salidas/issue47-step6-shared-tests.log` |
| Held-out synthetic harness | **17 tests passed**, 19.625 s | `salidas/issue47-step6-heldout-tests.log` |
| Candidate A's original full synthetic checks | **11 checks passed**, including synthetic end-to-end execution | `salidas/issue47-step6-candidate-tests.log` |
| Earlier acceptance/review evidence versus current source | Source/configuration hashes match; all 17 observed CSV identities and all 68 recorded cases accounted for | `salidas/issue47-step6/evidence-audit.json` |

Reproduction commands from the repository root:

```powershell
docker compose run --rm --pull never --entrypoint python evaluar -m unittest discover -s tests -v
docker compose run --rm --pull never --entrypoint python heldout -m unittest heldout.tests -v
docker compose run --rm --pull never --entrypoint python evaluar -m solution.a_opus.tests --full
```

Environment: Python **3.11.17**, NumPy **2.4.6**, pandas **3.0.6**; the held-out image additionally has
kloppy **3.18.0**. The step 3 acceptance report was generated before implementation commit `4c741b0`, and the
step 4 review before this closeout commit. Their recorded dirty-tree state is intentional, not a claim that the
preceding HEAD contains every reviewed file. The final integrity check confirms these unchanged identities:

| Identity | SHA-256 |
|---|---|
| Acceptance runner, A and its recorded dependencies | `af29536413ca5eb7958e2d36e80630966567973b3d210dd9e750ab526ff91d90` |
| Default A configuration | `9ac8279c798b9a38349b4afefacf167fc01545d36dceb391217461ee3dad434f` |
| Football rule-review runner | `7583da4cd436349775986a8e47390e819d2212eaab497997c90dd99b946d96a2` |
| Existing P2 source | `fcb4884e563c60f5db10a8a68cdd35a10186f29dfcc83e5963be8972285b8552` |
| Repeated 199,319-row synthetic full-size CSV | `c6a7751eaa7ab2a78f0854aaf217c21569a986bb897ecd7a515d3456e641857d` |

The final regression does not repeat unchanged 68-probe/full-size evidence; it verifies its source identities
and reruns the shared, harness and original A tests against the final code. Software checks pass while the
baseline football acceptance gate remains failing as documented in section 3.8. Local JSON/log files under
ignored `salidas/` are evidence, not committed match data. The public scripts reproduce invented inputs only.

### 5.2 External comparison reproduction

Pending: frozen model/configuration commits, original DFL file hashes, real conversion conformance, complete
run commands, profile/seed coverage, durations, hardware and prediction hashes for both candidates. Populate
this record with section 4.2; the local synthetic hashes above cannot substitute for it.

## Sources

- Bassek, Rein, Weber and Memmert (2025). *An integrated dataset of spatiotemporal and event data in elite soccer.*
  Scientific Data. [PMC11787359](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/)
- [metrica-sports/sample-data](https://github.com/metrica-sports/sample-data) · [SkillCorner/opendata](https://github.com/SkillCorner/opendata)
- [PFF FC, Enhanced 2022 World Cup dataset](https://www.blog.fc.pff.com/blog/enhanced-2022-world-cup-dataset)
- Official rules: [RULES.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md) ·
  [FAQ.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/FAQ.md)
