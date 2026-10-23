# Study: the possession model

> 🇪🇸 Translated from the Spanish original, [ESTUDIO_POSESION.md](ESTUDIO_POSESION.md).

> **More than a Hack 2027 · phase 1** · study before coding · 20 October 2026
>
> **Sources:** the challenge's public documentation and code (`CHALLENGE.md`, `EVALUATION.md`, `DATA.md`,
> `FAQ.md`, `RULES.md`, `OVERVIEW.md`, `evaluation/possession_metrics.py`, `starter/`) and published literature,
> linked in [section 8](#8-sources).
>
> **Match data:** none was opened. Not `data/`, not `evaluation/gt/*.csv`, not `evaluation/results/*.csv`. The
> match figures that appear here are the ones the challenge documents publish. Whatever requires looking at data is
> left as a local experiment in [section 7](#7-local-experiments-for-the-team). The simulations in
> [section 2](#2-how-the-metric-scores) use **synthetic** sequences and the official scorer; the script is in the
> [appendix](#appendix-synthetic-simulation-of-the-scorer).

---

## Summary

1. **`spellF1` counts possessions, not frames.** Each structural error (a flicker, a false `D` gap inside a
   possession, a real short possession we don't see) costs on the order of **1–1.4 / N**, where N is the number of
   real possessions. With N of a few hundred, each error is worth **≈0.3–0.4 points**. On top of that, the number of
   predicted possessions sets a hard ceiling: if we predict twice as many as there are, `spellF1 ≤ 0.67`.
2. **Not seeing the ball isn't a dead ball.** The baseline writes `D` when it doesn't see the ball, and the ball is
   missing in 41% of scored frames. Each false `D` inside a possession splits it in two. Separating "I can't see it"
   from "it's dead" is the cheapest improvement we have.
3. **The ground truth has many very short possessions.** It follows from the delay table in `EVALUATION.md`: a
   uniform delay of 8 frames can only cost 0.11 if **about 10% of possessions last under 1–2 s**
   ([2.5](#25-an-inference-the-gt-has-many-short-possessions)). That's why smoothing more isn't free: the filter
   that erases flicker also erases real possessions, and both cost almost the same.
4. **Boundaries are scored almost to the frame.** One frame of delay is free, 3 frames cost ~2 points, 8 frames
   ~11 and 1 s ~35 (`EVALUATION.md`). A smoothing that shifts boundaries loses a lot even if it gets the number of
   possessions right.
5. **`X` means "repeat my previous label".** Inside a possession it's harmless; at a possession change it's a delay.
   Explicitly writing the label that is being kept gives the same `spellF1` and a better `macroF1`.
6. **What we propose:** going from "nearest player in each frame + voting window" to a **`D` detector**, **control
   events with a keep-the-last-team rule**, **temporal decoding (HMM/Viterbi with a switching cost)** and **boundary
   refinement** to the frame of the touch.
7. **State of the art:** there are rule-based methods (Link and Hoernig 2017; Vidal-Codina et al. 2022), learned
   possession and dead-ball models (Borghesi et al. 2023, with a TCN), and models that work **without the ball**
   from the players (Kim et al. 2023; PathCRF, Kim et al. 2026, with a CRF and Viterbi). Temporal action
   segmentation knows the same problem under the name *over-segmentation*, and its F1@k metric is practically
   `spellF1`.
8. **There is external data with the same semantics as our GT.** The open Sportec/DFL dataset (7 matches,
   CC-BY 4.0) provides `BallPossession` and `BallStatus` for the ball. It lets us choose parameters without touching
   the public window, which has only 17 possessions.

---

## 1. H/A/D/X rules

### 1.1 What counts as possession

`CHALLENGE.md` defines it like this:

- **With the ball in play, there is always a team in possession.** There are no "contested", "transition" or
  "unknown" states: every scored frame is `H`, `A` or `D`.
- **Possession change:** it happens when a player from the opposing team gains **controlled** possession.
- **Loose or contested ball:** possession stays with **the last team that had it**. It is, literally, a hysteresis
  rule: it doesn't change until the other team has control.
- **They don't count as a change:** a touch without control, a deflection of a pass that doesn't intercept it and
  an aerial duel won without subsequent control.
- **"Control" signals the challenge suggests:** the player keeping the ball for a few seconds, or the team stringing
  together more than two passes.
- **After every restart there is a clear owner.** The problem is detecting when it changes afterwards.
- **A possession is a maximal run of the same team with the ball alive.** `H H H A A` is two possessions.
  `H H D D H H` is also two, separated by a stoppage, even though it's the same team.

### 1.2 How the ground truth was built (and what it implies)

According to `CHALLENGE.md`, the GT **comes from corrected tracking**, not from someone watching video or from
event data. The derivation is mechanical: a frame is `D` where the corrected tracking marks the ball as dead and,
elsewhere, it carries the team that tracking marks as owner. **It isn't smoothed, interpolated or touched up by
hand.**

This has three consequences:

1. What we need to imitate is the **"team owning the ball" of a corrected tracking**, not the intuitive idea of
   possession. It is the same kind of field professional feeds carry. The open DFL dataset, for example, has
   `BallPossession` (1 = home, 2 = away) and `BallStatus` (0 = stopped, 1 = in play) for the ball, and kloppy
   turns them into `ball_owning_team` and `ball_state`
   ([Bassek et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/);
   [kloppy deserializer](https://github.com/PySport/kloppy/blob/master/kloppy/infra/serializers/tracking/sportec/deserializer.py)).
2. **The GT wasn't smoothed.** If the owner changes for an instant, there's a short possession in the GT.
   [Section 2.5](#25-an-inference-the-gt-has-many-short-possessions) indicates that those possessions exist and
   aren't rare.
3. **The reference is the public window.** The challenge says that if our reading of the definition clashes with
   the 5 public minutes, the GT wins. We need to look locally at how the doubtful cases (rebounds, clearances,
   duels) are labelled before fixing rules ([experiment L5](#7-local-experiments-for-the-team)).

### 1.3 When it's `D`

- `D` = **the ball isn't in play**, as marked by the corrected tracking: out of the pitch, foul whistled,
  substitution, goal, before each restart...
- **Who owns a dead ball isn't asked.** The corrected tracking names a team even with the ball stopped (the one
  about to restart, or the last to touch it), but the GT discards it: with a dead ball, `D`.
- **A documented trap (`FAQ.md`):** the second half is scored from frame 110,808, but the kick-off is at 113,742.
  Those 2,934 frames are scored and are all `D`. The first half, on the other hand, is scored from the kick-off
  itself (frame 11,185).
- **Weight of `D`:** in the public window there are 1,469 `D` frames out of 7,500 (~20%, `DATA.md`). Since each
  stoppage separates possessions, **the edges of `D` are possession edges**. A `D` we don't detect merges two
  possessions; a `D` we invent splits one in two.

### 1.4 When `X` pays off

The scorer (`fill_abstentions` in `possession_metrics.py`) treats `X` differently depending on the metric:

| where | `macroF1` | `spellF1` (ranking) |
|---|---|---|
| **unscored** frame (before the match, half-time, after) | doesn't count | doesn't count |
| scored frame, **inside a possession** | miss | **free**: filled with the last label of that half |
| scored frame, **at a possession change** | miss | **expensive**: the old label is dragged = delay |
| scored frame, **at the start of a half** | miss | filled backwards with the first label |

**Practical rule:**

- Outside the scored stretches, `X`.
- Inside a possession with the ball lost, **explicitly write the label being kept**. For `spellF1` it's identical
  to `X` (the scorer does the same filling), and for `macroF1`, which breaks ties, it scores if it's right. `X` only
  makes sense if the alternative would be inventing a change.
- At a possession change, **always guess**. In the appendix simulation, putting `X` in the second after each change
  costs between 13 and 41 points of `spellF1` depending on how many short possessions there are.
- **Never use `D` as "I don't know".** `D` does split possessions. That's exactly the baseline's error (section 3.3).

### 1.5 Scored frames and the public window

| stretch | video frames | scored |
|---|---|---|
| first half | 11,185 – 90,651 | yes |
| half-time | 90,652 – 110,807 | no |
| second half (includes 2,934 `D` frames before the kick-off) | 110,808 – 190,197 | yes |
| public window (GT in the repo) | 11,185 – 18,684 | 17 possessions, mean 14.2 s |

In total there are 158,857 scored frames. The ATD starts at `frame_id = 1`, so `video_frame = frame_id − 1`
(`DATA.md`).

---

## 2. How the metric scores

### 2.1 `macroF1`: the per-frame view

It's the unweighted mean of the F1 of `H`, `A` and `D` over the scored frames. An `X` counts as a miss. The
practical floor is ~0.16 and differences below ~0.01 are noise. **It is almost blind to structure:** the vast
majority of frames are in the middle of a possession, where nothing happens.

### 2.2 `spellF1`: the per-possession view (the one the ranking uses)

This is how the code computes it (`possession_metrics.py`, `spell_scores`):

1. The prediction's `X` are filled (forwards within each half).
2. **Each half separately** is cut into runs of constant label. No possession crosses half-time.
3. The **possessions** are the runs of `H` or `A`. `D` runs aren't possessions, but they **separate**.
4. For each pair (real possession, predicted possession) **of the same team** that overlap, the temporal IoU is
   computed: intersection / union.
5. They are matched **one to one**, from highest to lowest IoU (greedy). No real possession is credited twice.
6. For each IoU threshold (0.3, 0.4, 0.5, 0.6 and 0.7), `F1 = 2·TP / (n_pred + n_real)` is computed. `spellF1` is
   the mean of those five F1.

It's the same idea as the **segmental F1@k** of temporal action segmentation
([Lea et al. 2017](https://arxiv.org/abs/1611.05267)). There, if several detections fall inside the same real
action, only one counts as a hit and the rest as false positives. The metric was designed precisely to penalise
**over-segmentation**.

**A ceiling worth keeping in mind.** Since `TP ≤ min(n_pred, n_real)`:

```
spellF1 ≤ 2·min(r, 1) / (1 + r),   with r = n_pred / n_real
```

| r = predicted / real possessions | 0.5 | 0.8 | 1 | 1.25 | 1.5 | 2 | 3 | 5 |
|---|---|---|---|---|---|---|---|---|
| `spellF1` ceiling | 0.67 | 0.89 | 1 | 0.89 | 0.80 | 0.67 | 0.50 | 0.33 |

`validate_submission.py` prints our number of possessions. In the public window, the real one is 17. For the full
match it isn't published, although a linear extrapolation of the public window gives an order of **300–400** (it's
an extrapolation, not a figure).

### 2.3 Which errors it punishes and how much

Costs measured with the official scorer on a synthetic sequence of 100 possessions of 10 s
([appendix](#appendix-synthetic-simulation-of-the-scorer)). For another N, the cost scales as 1/N:

| error | what happens to the structure | cost in `spellF1` |
|---|---|---|
| 1-frame flicker of the other team **in the middle** of a possession | 1 real possession → 3 predicted | **≈ 1.4 / N** |
| flicker near a boundary | +1 spurious possession | ≈ 1.0 / N |
| `D` gap in the middle of a possession (e.g. from not seeing the ball) | 1 → 2 | ≈ 1.1 / N |
| **missing** a real 1 s possession between two of the same opponent | 3 real → 1 predicted | **≈ 1.2 / N** |
| detecting that 1 s possession, but 5 frames late | none | ≈ 0.2 / N |
| delaying every boundary by 8 frames, if all possessions last 10 s | none | 0 |

There are three conclusions:

- **Structural errors all cost about the same, on the order of 1/N.** It doesn't matter whether it's a flicker, a
  false `D` or a missed short possession. With N ≈ 350, each one is worth ≈ 0.3–0.4 points, and 50 such errors are
  ~15–20 points.
- **That's why minimum duration or smoothing has no obvious optimum.** A filter gains ≈ 1.4/N for each flicker it
  erases and loses ≈ 1.2/N for each real possession it erases. The right threshold is the one where, for that
  duration, there are as many false possessions as real ones. It has to be **measured**, not assumed.
- **Delay only hurts on short possessions.** With long possessions, 8 frames of delay are free. On the real GT they
  cost 11 points, which tells us something about the GT (2.5).

### 2.4 Why flicker sinks `spellF1`

Example: a real `H` possession of 10 s (250 frames). At frame 125, the cloud of players makes an opponent the
nearest to the ball for a single frame:

```
real:      HHHHHHHHHH...HHHHHHHHHHHHHHHHHHHHHHHHHHHH          1 possession
predicted: HHHHHHHHHH...HHHH A HHHHHHHHHHHHHHHHHHHHHHH        3 possessions: H(125) A(1) H(124)
```

- At IoU ≤ 0.5, the first half (IoU = 125/250 = 0.5) matches the real one. The second half and the `A` are false
  positives.
- At IoU 0.6 and 0.7, none matches: the real possession is lost and all three predicted are false.

One frame out of 250 changes 0.4% of the frames (nothing for `macroF1`), but it destroys one possession and creates
two false ones. The unsmoothed baseline does this hundreds of times. That's why `baseline_raw` has `macroF1` 0.65
and `spellF1` 0.05: with "several times more possessions than the match" (`FAQ.md`), the ceiling from the table in
2.2 is already 0.5 or less, before counting a single miss.

### 2.5 An inference: the GT has many short possessions

`EVALUATION.md` publishes the `spellF1` of a perfect but delayed prediction: 1 frame → 1.0000; 3 → 0.9818;
8 → 0.8933; 1 s → 0.6539.

With a uniform delay δ, each possession keeps its length L, and its IoU with the real one is `(L − δ) / (L + δ)`.
It matches at threshold t only if `L ≥ δ·(1 + t)/(1 − t)`:

| delay δ | minimum L to match at IoU 0.3 | at IoU 0.7 | published `spellF1` | possessions that don't match (mean) |
|---|---|---|---|---|
| 8 frames | 15 frames (0.6 s) | 45 frames (1.8 s) | 0.8933 | ~11% |
| 25 frames (1 s) | 46 frames (1.9 s) | 142 frames (5.7 s) | 0.6539 | ~35% |

Since the number of possessions doesn't change, `F1 ≈ TP/N`, so losing 0.107 means that, on average over the five
thresholds, ~11% of possessions don't match. That's only possible if **about 10% of the GT's possessions last less
than ~1–2 s**, and if **on the order of a third last less than ~2–6 s**.

The simulation confirms it: with a "normal" synthetic distribution (lognormal with a median of ~9 s), 8 frames of
delay only cost 0.017. To get close to the published 0.893, you have to add between 20% and 40% of "lightning"
possessions of 0.3–2 s (appendix, section 0).

**Caveats:** `EVALUATION.md` doesn't say whether that table was computed on the full match or on the public window,
and the deduction is approximate (it assumes the number of predicted and real possessions coincide). It has to be
checked locally with the public GT ([L2](#7-local-experiments-for-the-team)). If it's confirmed, **it changes
the design**: minimum durations of several seconds can't be imposed, and boundary precision weighs a lot. It also
partly clashes with "a touch without control doesn't count": we'll have to see on video what those short
possessions are.

### 2.6 Noise, the public window and diagnostics

- **Noise:** on the full match, `spellF1` differences below ~0.04 are noise. On the public window it's much worse:
  17 possessions, and **one badly resolved possession moves it by about 6 points**. The challenge itself shows it:
  on the public window `smooth125` wins (0.42 vs 0.33) and on the full match `smooth50` wins (0.2433 vs 0.2242).
- **Bootstrap:** `python evaluation/run_evaluation.py --bootstrap 1000` resamples possessions and gives intervals.
  If they overlap, the difference isn't demonstrated.
- **Diagnostics the scorer already computes**, worth always looking at: `n_pred_spells` vs `n_gt_spells`, the mean
  duration, `alive_dead_f1` (alive/dead only), `team_acc_both_alive` (team only, when both say alive), the precision
  and recall of transitions at ±12 and ±25 frames (a recall of ~1 with a precision of ~0 is flicker) and
  `evaluation/reports/<name>_transitions.csv`, which lists each change as `matched`, `missed` or `spurious` with its
  frame, so you can go and look at it on the video.

---

## 3. Possession changes

### 3.1 Signals for detecting a change

| signal | what it captures | where it fails |
|---|---|---|
| **nearest player** to the ball (baseline) | who is next to the ball | on passes (the ball goes near opponents), aerial balls (we have no height), duels and balls between two players. It changes team as soon as the ball is halfway |
| **possession zone**: ball within R of a player | possible contact | R depends on the provider: Vidal-Codina et al. use 0.5 m or 1 m; databallpy, 1.5 m by default. It has to be calibrated to our noise |
| **change in the ball's kinematics** (direction or speed) with a player in the zone | **real touch**: reception, pass, deflection | requires a reliable ball speed. With the ball visible only at times, the derivative is noisy |
| **ball slowing down next to a player** (reception) | **control** | — |
| **ball acceleration peak** (≥ 4 m/s² in Link and Hoernig 2017) | kick, start of a pass | tracking noise |
| **duel**: opponents within ~1 m of the ball | contested situation → don't decide | — |
| **control confirmation**: the ball stays in the zone for k frames, or the next touch is by the same team | tells control apart from a rebound or deflection (what the challenge asks for) | introduces delay if the change is dated at the confirmation instead of the first touch |
| **collective context**: who presses, where the blocks run, each team's shape | possession without seeing the ball | harder; it's what "ball-free" models learn (section 5) |
| **Smart Tagging**: `ATTACKING TRANSITION` and `DEFENSIVE TRANSITION` (24 + 24), phases with a team | change candidate and team prior | they are phase windows, not instants. At kick-offs they open ~3.5 s before. It's automatic, with false positives and negatives |

A note on how phases are labelled. If we understand the definitions in `OVERVIEW.md` correctly, the `Team` tag is
the team **performing** the phase. So Barcelona's `BUILD UP`, `PROGRESSION` and `CREATING CHANCES` are evidence of
`H`, but Barcelona's `DEFENDING IN …` is evidence of `A`. This must be checked locally before using it.

### 3.2 Proposed scheme: control events + keep the last team

It's the challenge's rule turned into an algorithm, and the same structure as the rule-based method of
[Vidal-Codina et al.](https://arxiv.org/abs/2202.00804) (possession zone, duel zone, gain by change of direction or
speed):

```
state = team restarting after each D
for each live-play frame:
    if the ball is visible and there is a TOUCH (player within R and a change in the ball's direction/speed):
        if there are opponents within R_duel: duel -> don't decide yet
        if the touching team != state and control is CONFIRMED
           (k frames in the zone, or the next touch by the same team):
            change of state DATED AT THE FIRST TOUCH, not at the confirmation
    otherwise: the state is kept (loose, contested or invisible ball)
```

**The date of the change matters.** Confirming control by waiting k frames is fine, but the change is written
backwards, at the frame of the first touch. Since the processing is offline, we can use the future. Otherwise we
introduce a systematic delay of k frames, and 8 frames already cost ~11 points (2.5).

### 3.3 When the ball isn't visible (41% of scored frames)

It's the core of the problem (`DATA.md`): it's missing in 64,643 of 158,857 scored frames, **and disproportionately
at the moments that matter**: crowded boxes, duels, aerial balls.

**What the baseline does today:** if there's no ball, `D`. With the ±50 window, a gap of more than ~4 s is still
`D`. So every long gap inside a possession splits it in two (≈ 1.1/N each time, section 2.3), and every real `D`
with the ball visible stays as possession. It's the baseline's clearest weakness, and its own docstring
acknowledges it.

**Proposed strategy, by type of gap:**

1. **Short gap (≲ 1 s) with the same team on both sides:** keep the label. If needed, interpolate the ball's
   position (linearly or with simple physics).
2. **Gap with different teams on each side:** the change happens inside the gap. It has to be placed at the most
   likely instant: the opponent who gets closest to the interpolated trajectory, or the change in collective
   behaviour. **Never leave it as `X`**, because it would drag the old label to the end of the gap.
3. **Long gap:** decide between "the possession continues" and "dead ball" with stoppage evidence (3.4), not from
   the absence alone.
4. **Ball-free models:** the literature shows that team possession can be inferred from the players alone. PathCRF
   reports 92.4% per-frame accuracy on team possession, on clean DFL data
   ([Kim et al. 2026](https://arxiv.org/abs/2602.12080)). Ball Radar infers the ball's owner and trajectory from the
   players ([Kim et al. 2023](https://arxiv.org/abs/2306.08206)). In basketball it was done back in 2015
   ([Wei et al.](https://openaccess.thecvf.com/content_iccv_2015_workshops/w21/html/Wei_Predicting_Ball_Ownership_ICCV_2015_paper.html)).
   It's the way to handle long gaps with live play.

**A question that has to be answered locally:** does the automatic ATD stop giving the ball when it's dead? Some
providers signal a dead ball that way: Vidal-Codina et al. describe it for Track160 and Hawk-Eye. If in our data the
absence correlates with `D`, a **long** absence is evidence of a stoppage. If not, it isn't
([L4](#7-local-experiments-for-the-team)).

### 3.4 Detecting `D` (because its edges are possession edges)

Candidate signals, all to be validated:

- **Ball outside the pitch rectangle** (normalised coordinates < 0 or > 1, with a margin), especially just before it
  disappears.
- **Collective stillness:** the players' mean speed drops and stays low for a few seconds (the ATD gives each
  player's speed).
- **Still ball** at a restart point: corner, touchline, six-yard box, penalty spot, centre of the pitch.
- **Restart formations:** kick-off (each team in its own half), corner, goal kick...
  [Vidal-Codina et al.](https://arxiv.org/abs/2202.00804) detect the restart type from position patterns during the
  stoppage.
- **Smart Tagging `SET PIECES`:** 59 restarts with a type. The team is missing (`N/A`) on all throw-ins.
- **End of the stoppage = restart:** a peak in the ball's acceleration from standstill. The team of the first touch
  is the initial owner ("after every restart there is a clear owner").
- The second-half stretch before the kick-off (2,934 frames) should come **from a kick-off detector**, not be
  written by hand. `RULES.md` requires the labels to come from an algorithm.

---

## 4. Temporal continuity: techniques

Two premises for everything that follows:

1. The processing is **offline**: each frame can look at the future. There's no reason to use causal filters that
   introduce delay.
2. From section 2, the ideal smoothing **erases flicker without erasing real short possessions or moving
   boundaries**. No blind filter achieves that: it takes evidence, such as the touch or the control.

### 4.1 Majority-vote window (the baseline)

It's `smooth()` in `starter/baseline.py`: a centred vote of ±w frames between `H` and `A`, ignoring frames without
the ball. If the window sees no ball, `D`. On a tie, `H`.

- **Pros:** trivial and symmetric (centred, no systematic delay).
- **Cons:** it erases any possession shorter than ~w frames. Boundaries fall where the vote crosses 50%, which
  shifts if the ball is missing unevenly on each side. It ignores confidence. A single w for everything. It mixes
  "I can't see it" with `D`.
- **Parameter:** w. The published data already shows the dilemma: ±50 gives 0.2433, ±125 gives 0.2242 and ±25 gives
  0.1996 on the full match.

### 4.2 Median or mode filter and morphology

On categorical labels, the "median" is the mode in the window, almost the same as 4.1. The morphological alternative
(opening and closing on each class's mask) is exactly **removing runs shorter than k frames**: it's the minimum
duration of 4.3.

- **Pros:** explicit control over what gets erased, and a different k per class (`D` vs `H`/`A`).
- **Cons:** the order of operations changes the result and it's still blind to evidence.

### 4.3 Minimum possession duration

Runs shorter than k are merged with their neighbours. If both neighbours are the same team, it's absorbed. If not,
it's cut at the point of greatest evidence.

- **Ceiling cost**, applied to a **perfect** prediction (simulation, appendix, section 3):

  | minimum duration | 1 s | 2 s | 3 s | 5 s |
  |---|---|---|---|---|
  | synthetic GT without lightning possessions | 0.997 | 0.961 | 0.915 | 0.764 |
  | synthetic GT with 20% lightning | 0.958 | 0.856 | 0.805 | 0.714 |

  If section 2.5 is right, a minimum duration of 2–3 s **takes 15–20 points off us even if everything else were
  perfect**. A minimum duration of a few frames (0.2–0.5 s) can pay off against pure flicker.
- **Parameters:** k per class. `D` probably allows a larger minimum than possessions, because a stoppage rarely
  lasts less than a couple of seconds (to be checked).

### 4.4 Hysteresis (state machine)

The current state is kept and only changes when the evidence for the other state exceeds an entry threshold θ_on
for k frames (or a cumulative sum, CUSUM-style). Going back requires another threshold, θ_off. It's the "a loose
ball stays with the last team" rule put into code.

- **Pros:** interpretable, cheap and faithful to the challenge's definition. It tells touch apart from control.
- **Cons:** if applied causally, **it adds a delay of k frames**. The change has to be **backdated** to the start of
  the evidence. It has several thresholds that interact and have to be set per type of transition (`H↔A`,
  alive→`D`, `D`→alive).
- **Parameters:** θ_on, θ_off, k and the backdating rule.

### 4.5 HMM with Viterbi and a switching cost, HSMM and CRF

Three hidden states are modelled, {`H`, `A`, `D`}. Each frame provides a score per state (the *emission*: the log
probability of what was observed in that state). Each change of state has a cost (the *transition*). Viterbi finds
**the globally optimal sequence**:

```
minimise  Σ_t −log p(observation_t | state_t)  +  λ · (number of changes)
```

It's a penalised segmentation, the same idea as penalised change-point detection
([PELT, Killick et al. 2012](https://arxiv.org/abs/1101.1438)). Classic HMM and Viterbi reference:
[Rabiner 1989](https://ieeexplore.ieee.org/document/18626).

- **Pros:**
  - A single main knob (λ) for the flicker vs short-possession dilemma.
  - Boundaries fall where the evidence changes, with no systematic delay.
  - **Frames without the ball are handled naturally**: a neutral emission (or that of a ball-free model), and the
    state is kept unless the context calls for a change.
  - It allows asymmetric costs: `H→A` vs `H→D` vs `D→H`.
  - It allows forbidden transitions, as in PathCRF, which masks impossible transitions with a very negative score.
- **Cons:**
  - It needs reasonably calibrated emissions.
  - An HMM implies geometric durations, which aren't football's.
  - λ has to be chosen with data other than the public window (section 6).
- **HSMM** (*hidden semi-Markov model*, with explicit duration, [Yu 2010](https://doi.org/10.1016/j.artint.2009.11.011)):
  - It models each state's duration distribution. For example, `D` with a minimum of a couple of seconds.
  - More expensive: O(T·D_max) with 160,000 frames. It can be reduced by working at 5 fps (PathCRF does this) and
    then refining the boundaries at 25 fps.
  - A minimum of k frames can also be obtained in a normal HMM by chaining k substates.
- **CRF** ([PathCRF](https://arxiv.org/abs/2602.12080)): the emissions and transitions are learned from labelled
  data, and decoding is the same, with Viterbi.

### 4.6 Boundary refinement

Segment first. Then each boundary is moved within ±Δ frames to the frame with the most evidence of a touch (change
of the ball's direction next to a player of the new team) or of a stoppage and restart. It's what
[ASRF](https://arxiv.org/abs/2007.06866) does in action segmentation: one branch predicts boundaries and corrects
the segmentation. It fits here because `spellF1` punishes shifts of more than ~3 frames, especially on short
possessions. In the simulation, noise of σ = 5 frames on the boundaries costs between 0 and 7 points, and σ = 12
costs between 2 and 23, depending on how many short possessions there are.

### 4.7 Comparison

| technique | flicker | real short possessions | boundaries | missing ball | parameters |
|---|---|---|---|---|---|
| voting window | good if w is large | erases them if w is large | shift | confuses it with `D` | w |
| median / morphology | good | erases them (< k) | stable | — | k per class |
| minimum duration | good | erases them (< k) | stable | — | k per class |
| hysteresis | good | keeps them if the evidence is strong | delay unless backdated | keeps the state | θ_on, θ_off, k |
| HMM/Viterbi + λ | good | depends on λ and the evidence | where the evidence changes | neutral emission | λ (+ asymmetries) |
| HSMM / CRF | good | models durations | where the evidence changes | yes | durations / learned |
| + boundary refinement | — | — | **improves** | — | Δ |

**Recommendation:** HMM/Viterbi as the backbone, with emissions built from the control events (3.2), a `D` model
(3.4) and a neutral emission without the ball. The voting window and hysteresis remain as comparisons, and boundary
refinement is added at the end.

---

## 5. State of the art

### 5.1 Possession and events from tracking

| work | input | what it does | why it matters to us | what we have verified |
|---|---|---|---|---|
| [Link and Hoernig 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225/), *PLoS ONE* | TRACAB 25 Hz, with the data's own ball-in-play flag | Individual possession: it starts when the ball enters the player's action space; kick detection by a ball acceleration peak ≥ 4 m/s²; end by predicting the ball 1 s ahead. A Bayesian network tells control apart from mere contact. F = 0.83 on individual possession (0.6 s tolerance) | Contact and control rules; the idea that control ≠ being close | full text (PMC) |
| [Vidal-Codina et al. 2022](https://arxiv.org/abs/2202.00804), *Sports Engineering* | 25 Hz tracking from three providers | Deterministic decision tree: possession zone of 0.5 or 1 m, duel zone of 1 m, gain if the ball's direction or speed changes, loss if the ball leaves its zone and the player doesn't take part in the next control frame. Dead ball by flag or by ball absence. Restarts by position patterns. 90%+ detection on most events | The most complete rule-based reference; databallpy implements it | arXiv text (the angle and speed thresholds are in supplementary material we haven't read) |
| [Khaustov and Mozgovoy 2020](https://doi.org/10.3390/app10228046), *Applied Sciences* | tracking | Rules for possession, passes and shots, set out as a practical baseline | Another rule-based baseline | abstract only |
| [Richly et al. 2016](https://scitepress.org/Papers/2016/58776), IoTBD | positions | SVM, k-NN and random forest on positional features for compound events | Classical ML on hand-crafted features | abstract only |
| [Morra et al. 2020](https://arxiv.org/abs/2004.04147), ICIAR | synthetic tracking (SoccER) | Atomic events plus interval temporal logic for complex events | Formalising temporal rules ("touch and then control") | abstract only |
| [Borghesi et al. 2023](https://doi.org/10.1016/j.eswa.2023.119780), *Expert Systems with Applications* | professional tracking | **A TCN that classifies each moment as dead ball, home possession or away possession**, with aggregation invariant to player permutations. 86.2% accuracy on possession and 89.2% on alive/dead (+7.3% and +33.2% over the previous state of the art, according to the abstract) | **It is almost exactly our task**. It suggests separating alive/dead from home/away | abstract only (the PDF couldn't be downloaded). Time window, inputs and handling of the missing ball: **unverified** |
| [Kim et al. 2023](https://arxiv.org/abs/2306.08206), KDD (Ball Radar) | **players only** | Set Transformer and hierarchical Bi-LSTM: first it predicts the owner and then the ball's trajectory. The abstract gives 64.7% accuracy on the individual owner | Inferring where the ball is when it's missing. [Code](https://github.com/pientist/ballradar) | abstract |
| [Kim et al. 2026](https://arxiv.org/abs/2602.12080), KDD (PathCRF) | **players only** (Sportec Open DFL) | Models possession as a player→player edge (with self-loops for "has it" and "out" nodes). Uses a **CRF with masked impossible transitions** and **Viterbi decoding**. Event F1 of 75.7%; 92.4% per-frame accuracy on team possession | Structured decoding without the ball; forbidden transitions | part of the text. The 92.4% figure comes from a summary and must be checked in the paper. Its abstract links [code](https://github.com/hyunsungkim-ds/pathcrf.git) (not opened) |
| [Wei et al. 2015](https://openaccess.thecvf.com/content_iccv_2015_workshops/w21/html/Wei_Predicting_Ball_Ownership_ICCV_2015_paper.html), ICCV-W (basketball) | player trajectories | Predicts who has the ball from the players' arrangement alone, ordered by role | The collective context gives away the owner | abstract |
| [Wang et al. 2014](https://infoscience.epfl.ch/record/185107), *CVIU* | video | Ball tracking framed as "who has it" | Possession as a latent state | abstract |
| [Maksai et al. 2016](https://openaccess.thecvf.com/content_cvpr_2016/html/Maksai_What_Players_Do_CVPR_2016_paper.html), CVPR | video | Ball tracking with player–ball interactions and physical constraints (mixed integer programming) | Ball physics to fill gaps | abstract |

### 5.2 Temporal segmentation (the same problem, in another field)

- [Lea et al. 2017](https://arxiv.org/abs/1611.05267): they propose the **segmental F1** with an IoU threshold, which
  penalises over-segmentation and is insensitive to small shifts. It is the direct predecessor of `spellF1`.
- [Farha and Gall 2019 (MS-TCN)](https://arxiv.org/abs/1903.01945): to curb over-segmentation they add a **smoothing
  loss** (truncated MSE between the log-probabilities of consecutive frames) and refine in stages. Applicable if we
  train a model.
- [Ishikawa et al. 2021 (ASRF)](https://arxiv.org/abs/2007.06866): a boundary branch that corrects the
  segmentation; its abstract reports improvements of up to 16.1% in segmental F1. It inspires 4.6.
- HMM and Viterbi ([Rabiner 1989](https://ieeexplore.ieee.org/document/18626)); HSMM
  ([Yu 2010](https://doi.org/10.1016/j.artint.2009.11.011)); penalised change points
  ([PELT](https://arxiv.org/abs/1101.1438)).

### 5.3 Video (in case we use the tactical video)

- [SoccerNet 2023](https://arxiv.org/abs/2309.06006) includes *ball action spotting*: locating passes and dribbles
  in time in TV video. It's a reference if we ever detect touches in the video to sharpen boundaries. Not a
  priority: `CHALLENGE.md` makes it clear the challenge isn't about redoing vision.

### 5.4 Open data and useful tools

| resource | what it provides | caveat |
|---|---|---|
| **Sportec Open DFL** ([Bassek et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/); data on [figshare](https://doi.org/10.6084/m9.figshare.28196177)) | 7 Bundesliga 1 and 2 matches with positions, events and, for the ball, `BallPossession` (1/2) and `BallStatus` (0/1). **Same semantics as our GT.** CC-BY 4.0. Loads with kloppy or floodlight | High-quality tracking (it has to be degraded to look like ours). Its definition of "owner" may differ from Metrica's. We haven't verified the files' frequency (the cameras run at 25 Hz) |
| [kloppy](https://github.com/PySport/kloppy) | Reads our EPTS and the DFL format, with `ball_owning_team` and `ball_state` | — |
| [databallpy](https://databallpy.readthedocs.io/en/latest/features/team_and_player_possession.html) | Individual possession following Vidal-Codina, with default parameters `pz_radius=1.5`, `bv_threshold=5.`, `ba_threshold=10.` and `min_frames_pz=0`. Also team possession from events | The documentation has inconsistencies (one example uses 1.5 instead of 5 for `bv_threshold`) |
| [SkillCorner opendata](https://github.com/SkillCorner/opendata) | **Broadcast** tracking at 10 fps with per-frame possession (player and group): noise more like ours | Another frequency and another definition of possession. The exact format isn't verified |
| [Metrica sample-data](https://github.com/metrica-sports/sample-data) | Sample Game 3 in **the same EPTS format** as our ATD, with JSON events | Anonymised match. Possession would have to be derived from the events |

`RULES.md` allows external data if the organisers can access it and the technical document explains it. All three
datasets are public.

---

## 6. Proposal

### 6.1 What to try and in what order

Ordered by expected gain and cost. Each step is measured against the previous one, not against the original
baseline.

| # | improvement | why first | parameters to validate |
|---|---|---|---|
| **P0** | **Instrumentation:** a local script that generates, validates and scores, and prints the diagnostics from 2.6 and a duration histogram; bootstrap; a record template (6.3). An external validation bench with degraded DFL (6.2) | Without this, everything else is decided with 17 possessions | — |
| **P1** | **Separate "can't see" from "dead":** without the ball, `D` isn't written; the label is kept | It removes the biggest source of false cuts (≈ 1.1/N each). A few-line change | — |
| **P2** | **`D` detector** (3.4): ball out, collective stillness, restarts, Smart Tagging `SET PIECES`, kick-off | After P1, real stoppages have to be detected with evidence. Their edges are possession edges | out-of-bounds margin; mean speed and duration of stillness; minimum `D` |
| **P3** | **Control events + keep the last team** (3.2), instead of the nearest player in each frame | It's the challenge's definition; it removes flicker from passes and duels at the source | R (0.5–1.5 m); ball angle and speed thresholds; confirmation k; R_duel |
| **P4** | **HMM/Viterbi** with {`H`, `A`, `D`}, switching cost λ and emissions from P2 and P3 (neutral without the ball). Compare with the window and hysteresis | It optimises the whole sequence, with a clear knob for the flicker vs short-possession dilemma | λ (sweep looking for a plateau); asymmetries |
| **P5** | **Boundary refinement** to the frame of the touch, the exit or the restart | Delays of more than 3 frames cost a lot with short possessions | search Δ |
| **P6** | **Ball gaps:** short interpolation; for long gaps, collective features (pressure, direction of the blocks) or a ball-free model | 41% of frames without the ball, and changes inside gaps are dated badly | maximum interpolation length |
| **P7** | **Smart Tagging** as a soft team prior (phases) and change prior (transitions) | Free information, but noisy | prior weight |
| **P8** | **Learned model** (per-frame gradient boosting, or a Borghesi-style TCN) trained on degraded DFL, decoded with P4 | Only if P1–P6 stall; it needs P0 well set up | — |

### 6.2 How to validate without overfitting the public window

The public window has 17 possessions, and one badly resolved possession moves ~6 points. The challenge itself shows
that choosing with it leads to the wrong option (`EVALUATION.md`, `FAQ.md`). Proposed protocol:

1. **The public window is for checking that the pipeline is correct** (aligned frames, format, `H` being
   Barcelona), **not for choosing** between versions. Its bootstrap intervals are looked at, not the bare figure.
2. **Choose parameters on labelled external data:** the 7 Sportec/DFL matches, with leave-one-match-out
   validation. Before that, they're **degraded to look like ours**:
   - remove the ball in ~41% of frames, in bursts whose length and zone distribution is measured on our ATD (without
     GT, [L1](#7-local-experiments-for-the-team));
   - remove identities and keep only team and position;
   - fragment the tracks and add position noise.
3. **Plateau rule:** each parameter is swept and the centre of a flat region is chosen, not the peak. A method that
   only works at one exact value is overfitted.
4. **Label-free checks on the full match:**
   - number of possessions;
   - duration histogram;
   - fraction of `D` (~20% in the public window);
   - fraction of possessions under 1 s;
   - home/away split;
   - consistency between the two halves.

   No tuning to hit them exactly: they're for spotting something odd.
5. **Few parameters, with physically meaningful values** (radii in metres, times in tenths of a second), and
   documented.
6. **Each experiment is recorded before seeing the result** (hypothesis and expected effect), including the failed
   ones. This fits with the team log.
7. **Freeze:** the final configuration is chosen with DFL and with a priori criteria. The public window is looked at
   one last time to rule out a serious regression.

### 6.3 What to record for each experiment

| field | example |
|---|---|
| id, date, author, commit | `E07 · 2026-10-24 · Nico · a1b2c3d` |
| hypothesis and expected effect | "no ball ≠ `D` reduces predicted possessions and raises `spellF1`" |
| change and parameters | `R=1.0 m, k=5, λ=8` |
| public window | `spellF1` (5–95% bootstrap interval), `macroF1`, `alive_dead_f1`, `team_acc_both_alive`, `n_pred_spells` vs 17, mean duration, transition P/R at ±12 and ±25 |
| degraded DFL (leave one match out) | mean `spellF1` ± deviation |
| full match, no labels | no. of possessions, % of `D`, % of possessions < 1 s |
| decision | adopted / discarded / unclear, and why |

Only aggregate metrics and conclusions go into the public log, never match data (`docs/README.md`).

---

## 7. Local experiments for the team

These experiments **require looking at the match data or the public GT**, so the team runs them locally, without
passing data or extracts to any cloud LLM. The aggregate results can be noted in this document or in the log.

| id | question | how | what for |
|---|---|---|---|
| **L0** | Which channels does the ATD have? (ball height, speed, any ball state or owner?) | Read the `DataFormatSpecification` of the metadata XML | Know which signals we have |
| **L1** | What are the ball gaps like? | Histogram of gap lengths in the scored frames; pitch zone where they start | Decide the interpolation (P6) and degrade DFL realistically (6.2) |
| **L2** | How many short possessions does the public GT have? | Duration histogram of the 17 possessions; count those under 1 s and under 2 s | Confirm or refute section 2.5 |
| **L3** | How much does the minimum duration cost, as a ceiling? | Apply minimum durations of 0.2 / 0.5 / 1 / 2 s **to the public GT itself** and score | Maximum cost of the filter (4.3) |
| **L4** | Does a missing ball indicate `D`? | % of frames without the ball inside `D` and inside live play, in the public window | Decide whether a long absence is evidence of a stoppage (3.3) |
| **L5** | What is each short possession and each change in the GT? | Watch the public window's changes on the video (the scorer's `_transitions.csv` gives the frames) | Pin down what counts as control in practice (1.2) |
| **L6** | At what distance is the "nearest" right? | With the ball visible and the GT alive: team accuracy by player–ball distance bands | Calibrate R (P3) |
| **L7** | How much does P1 give on its own? | `smooth()` without writing `D` when the ball is missing; score with bootstrap and on DFL | First experiment in the record |

In L2, L3 and L5, remember that the public window has 17 possessions. They're for **understanding** the problem,
not for setting thresholds; thresholds are set on DFL (6.2).

---

## 8. Sources

**Challenge documentation** (this repository): `CHALLENGE.md`, `EVALUATION.md`, `DATA.md`, `FAQ.md`, `RULES.md`,
`OVERVIEW.md`, `evaluation/possession_metrics.py`, `evaluation/run_evaluation.py`, `starter/baseline.py` and
`starter/0[1-3]_*.ipynb`.

**Literature and resources** (links checked on 20/10/2026; in brackets, what we've read):

1. Link, D. and Hoernig, M. (2017). *Individual ball possession in soccer.* PLoS ONE 12(7): e0179953.
   [doi:10.1371/journal.pone.0179953](https://doi.org/10.1371/journal.pone.0179953) (full text).
2. Vidal-Codina, F., Evans, N., El Fakir, B. and Billingham, J. (2022). *Automatic event detection in football
   using tracking data.* Sports Engineering. [arXiv:2202.00804](https://arxiv.org/abs/2202.00804) (arXiv text
   without the supplementary material).
3. Khaustov and Mozgovoy (2020). *Recognizing events in spatiotemporal soccer data.* Applied Sciences 10(22):
   8046. [doi:10.3390/app10228046](https://doi.org/10.3390/app10228046) (abstract).
4. Richly, K., Bothe, M., Rohloff, T. and Schwarz, C. (2016). *Recognizing compound events in spatio-temporal
   football data.* IoTBD 2016. [SciTePress](https://scitepress.org/Papers/2016/58776) (abstract).
5. Morra, L. et al. (2020). *Slicing and dicing soccer: automatic detection of complex events from spatio-temporal
   data.* ICIAR 2020. [arXiv:2004.04147](https://arxiv.org/abs/2004.04147) (abstract).
6. Borghesi, Costa, Morra and Lamberti (2023). *Using temporal convolutional networks to estimate ball possession
   in soccer games.* Expert Systems with Applications 223: 119780.
   [doi:10.1016/j.eswa.2023.119780](https://doi.org/10.1016/j.eswa.2023.119780) (abstract; the method's details are
   unverified).
7. Kim, H., Choi, H.-J., Kim, C. J., Yoon, J. and Ko, S.-K. (2023). *Ball trajectory inference from multi-agent
   sports contexts using Set Transformer and hierarchical Bi-LSTM.* KDD 2023.
   [arXiv:2306.08206](https://arxiv.org/abs/2306.08206) (abstract).
8. Kim, H., Lee, K., Seo, S., Ko, S.-K., Yoon, J. and Park, C. (2026). *PathCRF: Ball-free soccer event detection
   via possession path inference from player trajectories.* KDD 2026.
   [arXiv:2602.12080](https://arxiv.org/abs/2602.12080) (introduction and method; part of the tables only through a
   summary).
9. Wei, X., Sha, L., Lucey, P., Carr, P., Sridharan, S. and Matthews, I. (2015). *Predicting ball ownership in
   basketball from a monocular view using only player trajectories.* ICCV Workshops.
   [CVF](https://openaccess.thecvf.com/content_iccv_2015_workshops/w21/html/Wei_Predicting_Ball_Ownership_ICCV_2015_paper.html)
   (abstract).
10. Wang, X., Ablavsky, V., Ben Shitrit, H. and Fua, P. (2014). *Take your eyes off the ball: improving
    ball-tracking by focusing on team play.* CVIU 119: 102–115. [EPFL](https://infoscience.epfl.ch/record/185107)
    (abstract).
11. Maksai, A., Wang, X. and Fua, P. (2016). *What players do with the ball: a physically constrained interaction
    modeling.* CVPR 2016.
    [CVF](https://openaccess.thecvf.com/content_cvpr_2016/html/Maksai_What_Players_Do_CVPR_2016_paper.html)
    (abstract).
12. Lea, C., Flynn, M. D., Vidal, R., Reiter, A. and Hager, G. D. (2017). *Temporal convolutional networks for
    action segmentation and detection.* CVPR 2017. [arXiv:1611.05267](https://arxiv.org/abs/1611.05267)
    (definition of F1@k).
13. Abu Farha, Y. and Gall, J. (2019). *MS-TCN: multi-stage temporal convolutional network for action
    segmentation.* CVPR 2019. [arXiv:1903.01945](https://arxiv.org/abs/1903.01945) (abstract).
14. Ishikawa, Y., Kasai, S., Aoki, Y. and Kataoka, H. (2021). *Alleviating over-segmentation errors by detecting
    action boundaries.* WACV 2021. [arXiv:2007.06866](https://arxiv.org/abs/2007.06866) (abstract).
15. Rabiner, L. R. (1989). *A tutorial on hidden Markov models and selected applications in speech recognition.*
    Proc. IEEE 77(2): 257–286. [IEEE Xplore](https://ieeexplore.ieee.org/document/18626).
16. Yu, S.-Z. (2010). *Hidden semi-Markov models.* Artificial Intelligence 174(2): 215–243.
    [doi:10.1016/j.artint.2009.11.011](https://doi.org/10.1016/j.artint.2009.11.011) (abstract).
17. Killick, R., Fearnhead, P. and Eckley, I. A. (2012). *Optimal detection of changepoints with a linear
    computational cost.* JASA 107(500): 1590–1598. [arXiv:1101.1438](https://arxiv.org/abs/1101.1438).
18. Cioppa, A., Giancola, S. et al. (2023). *SoccerNet 2023 challenges results.*
    [arXiv:2309.06006](https://arxiv.org/abs/2309.06006) (abstract).
19. Bassek, M., Rein, R., Weber, H. and Memmert, D. (2025). *An integrated dataset of spatiotemporal and event data
    in elite soccer.* Scientific Data 12: 195.
    [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/) · data on
    [figshare](https://doi.org/10.6084/m9.figshare.28196177) (methods section: `BallPossession` and `BallStatus`).
20. kloppy, Sportec deserializer:
    [code](https://github.com/PySport/kloppy/blob/master/kloppy/infra/serializers/tracking/sportec/deserializer.py)
    (`BallPossession` → `ball_owning_team`, `BallStatus` → `ball_state`).
21. databallpy, *Team and player possession*:
    [documentation](https://databallpy.readthedocs.io/en/latest/features/team_and_player_possession.html).
22. SkillCorner opendata: [GitHub](https://github.com/SkillCorner/opendata) ·
    Metrica sample-data: [GitHub](https://github.com/metrica-sports/sample-data).

**Unverified** (not used for any conclusion): the internal details of Borghesi et al. 2023 (time window, inputs,
handling of the missing ball); the thresholds in the supplementary material of Vidal-Codina et al.; the exact
SkillCorner format; the frequency of the DFL files; and the contents of the PathCRF and Ball Radar repositories.

---

## Appendix: synthetic simulation of the scorer

To quantify the cost of each error without touching match data, **synthetic** halves of 200 possessions were
generated: lognormal duration with a mean of ~12–14 s, 30% `D` stoppages of 5–40 s and, optionally, a fraction
`p_short` of "lightning" possessions of 0.3–2 s. Then perfect predictions with a single type of error added were
scored with `possession_metrics.evaluate`. **The distributions are assumptions**: the numbers are for comparing types
of error with each other, not for predicting our score.

Results (`spellF1`):

| test | `p_short = 0` | `p_short = 0.2` | `p_short = 0.4` | real GT (`EVALUATION.md`) |
|---|---|---|---|---|
| uniform delay of 3 / 8 / 25 frames | 0.999 / 0.983 / 0.864 | 0.987 / 0.921 / 0.741 | 0.966 / 0.784 / 0.533 | 0.982 / 0.893 / 0.654 |
| 10 / 50 / 100 one-frame flickers (other team) | 0.926 / 0.695 / 0.499 | 0.928 / 0.702 / 0.497 | 0.926 / 0.699 / 0.501 | — |
| 10 / 50 / 100 one-frame `D` gaps | 0.951 / 0.772 / 0.598 | 0.951 / 0.777 / 0.593 | 0.952 / 0.777 / 0.598 | — |
| boundary noise σ = 5 / 12 / 25 frames | 0.999 / 0.975 / 0.890 | 0.978 / 0.886 / 0.792 | 0.927 / 0.773 / 0.670 | — |
| minimum duration 1 / 2 / 3 / 5 s on a perfect prediction | 0.997 / 0.961 / 0.915 / 0.764 | 0.958 / 0.856 / 0.805 / 0.714 | 0.854 / 0.658 / 0.640 / 0.578 | — |
| `X` for 5 / 25 / 50 frames after each change | 0.997 / 0.865 / 0.661 | 0.961 / 0.766 / 0.588 | 0.897 / 0.588 / 0.482 | — |

The per-error costs in section 2.3 come from deterministic cases: 100 possessions of 10 s and a single error placed
by hand.

<details>
<summary>Script (Python, numpy; run with <code>python sim_spellf1.py evaluation</code>)</summary>

```python
"""Cost of each type of error in spellF1, on SYNTHETIC sequences (no match data).

Usage: python sim_spellf1.py <path to evaluation/>
"""
import sys

import numpy as np

sys.path.insert(0, sys.argv[1])
import possession_metrics as pm  # noqa: E402

H, A, D, X = pm.H, pm.A, pm.D, pm.X
FPS = 25
rng = np.random.RandomState(0)


def synthetic_half(n_poss=200, mean_s=14.2, p_stop=0.3, stop_s=(5, 40), p_short=0.0):
    """A synthetic half: possessions with lognormal duration (mean ~mean_s) and D stoppages.

    p_short is the fraction of "lightning" possessions of 0.3-2 s (touches, rebounds with an owner).
    """
    seq, team = [], H
    sigma = 0.9
    mu = np.log(mean_s * FPS) - sigma ** 2 / 2
    for _ in range(n_poss):
        if rng.rand() < p_short:
            length = int(rng.uniform(0.3, 2.0) * FPS)
        else:
            length = max(int(rng.lognormal(mu, sigma)), 13)
        seq += [team] * length
        if rng.rand() < p_stop:
            seq += [D] * int(rng.uniform(*stop_s) * FPS)
            team = H if rng.rand() < 0.5 else A
        else:
            team = A if team == H else H
    return np.array([X] * 50 + seq + [X] * 50, dtype=np.int8)


def score(gt, pred):
    r = pm.evaluate(gt, pred)
    return r["spell_f1_mean"], r["n_gt_spells"], r["n_pred_spells"]


def spells(codes):
    return pm.possession_spells(codes, pm.valid_runs(codes))


def blip(gt, n, width, kind):
    """n flickers of `width` frames in the middle of different possessions: opposing team or D."""
    pred = gt.copy()
    chosen = rng.choice(len(spells(gt)), n, replace=False)
    for index in chosen:
        a, b, k = spells(gt)[index]
        mid = (a + b) // 2
        pred[mid:mid + width] = (A if k == H else H) if kind == "team" else D
    return pred


def jitter(gt, sigma):
    """Moves each label boundary by a Gaussian offset of sigma frames."""
    pred = gt.copy()
    for frame, old, new in pm.transitions(gt, pm.valid_runs(gt)):
        shift = int(round(rng.normal(0, sigma)))
        if shift > 0:
            pred[frame:frame + shift] = old
        elif shift < 0:
            pred[frame + shift:frame] = new
    return pred


def min_duration(codes, min_frames):
    """Merges possessions shorter than min_frames into the previous label (filling)."""
    out = codes.copy()
    for a, b, k in spells(codes):
        if b - a < min_frames and a > 0 and out[a - 1] in (H, A, D):
            out[a:b] = out[a - 1]
    return out


def lag(gt, frames):
    """Perfect prediction shifted by `frames` frames: each frame takes the label from `frames` before."""
    pred = gt.copy()
    pred[frames:] = gt[:-frames]
    return pred


def report(gt):
    base, n_gt, _ = score(gt, gt)
    lengths = np.array([b - a for a, b, _ in spells(gt)]) / FPS
    print("Synthetic GT: {} possessions, mean {:.1f} s, median {:.1f} s, <3 s: {:.0%}".format(
        n_gt, lengths.mean(), np.median(lengths), np.mean(lengths < 3)))

    print("\n0) Uniform delay (EVALUATION.md, real GT: 1->1.000 3->0.982 8->0.893 25->0.654)")
    print("  " + "  ".join("{}:{:.3f}".format(f, score(gt, lag(gt, f))[0]) for f in (1, 3, 8, 25)))

    print("\n1) Flickers in the middle of a possession (n = number of possessions affected)")
    for kind in ("team", "dead"):
        for width in (1, 25):
            row = []
            for n in (1, 10, 50, 100):
                row.append("{}:{:.3f}".format(n, score(gt, blip(gt, n, width, kind))[0]))
            print("  {:<5} {:>2} frames  ".format(kind, width) + "  ".join(row))

    print("\n2) Boundary noise (sigma in frames)")
    print("  " + "  ".join("{}:{:.3f}".format(s, score(gt, jitter(gt, s))[0])
                           for s in (2, 5, 12, 25, 50)))

    print("\n3) Minimum duration filter applied to a PERFECT prediction")
    print("  " + "  ".join("{}s:{:.3f}".format(s, score(gt, min_duration(gt, s * FPS))[0])
                           for s in (1, 2, 3, 5, 8)))

    print("\n4) X across a possession change (the X is filled with the previous label)")
    for gap in (5, 25, 50):
        pred = gt.copy()
        for frame, old, new in pm.transitions(gt, pm.valid_runs(gt)):
            pred[frame:frame + gap] = X
        print("  X in the {} frames after each change: {:.3f}".format(gap, score(gt, pred)[0]))


if __name__ == "__main__":
    for p_short in (0.0, 0.2, 0.4):
        rng.seed(0)
        print("=" * 30, "p_short =", p_short)
        report(synthetic_half(p_short=p_short))
```

</details>
