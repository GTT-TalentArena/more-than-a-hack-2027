# Candidate A with a ball-free model trained on other games (issue #47)

Variant for [#47](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/47), compared with candidate A v1.6
under the plan in [`ISSUE_47_ALTERNATIVE_TO_A.md`](ISSUE_47_ALTERNATIVE_TO_A.md). Sections 1–6 were written and
committed on **29 October 2026, before any run of the variant on DFL data**; results are added below them and do not
change them.

Module `solution/a_dfl`, config `configs/candidate_a_dfl.json`. Candidate A (`solution/a_opus`) is not modified.

## 1. Why this variant

Candidate A has a **ball-free team model**: a logistic regression on team shape that says which side has the ball
where the ball cannot be seen. It is trained on the challenge match itself, with targets made by ball proximity (the
frames where one side is clearly on the ball), cross-fitted by half.

- **Compliance.** In #47 (26 October) Edu read the organisers' answer in metrica-sports/more-than-a-hack-2027#2
  ("you may not annotate or label the provided dataset, either for use in your submission or to train any model",
  given for a detector trained on the provided tracking with automatic labels) as ruling this out. Alejandro read it
  as allowed. The question is with the organisers. Edu's proposed compliant route: fit the same model on the DFL
  development matches and apply it unchanged to BAR–ATH. This variant is that route.
- **What is at stake.** On two DFL development matches (`gaps-crowded` and `full`, seed 47), switching the ball-free
  model off costs A 0.024–0.048 spellF1 (Edu, #47).
- **A second reason.** A trains the model on frames where the ball is seen and one side clearly controls it, and uses
  it where there is no ball or no clear control: different frames. DFL has real labels on every live frame,
  including those.

## 2. Hypotheses

- **H1, the component.** On the DFL development matches, leaving one match out, the DFL-trained model agrees with
  the DFL possession labels more often than A's self-trained model on the frames where A uses it: live frames with
  no ball in the degraded observation, and live frames with the ball in sight but no clear control.
- **H2, end to end.** With everything else in A unchanged, replacing the self-trained model by the DFL-trained one
  does not lower spellF1 on the degraded profiles, and keeps most of what A loses when the ball-free model is off.

H1 is refuted if the leave-one-match-out accuracy is lower than A's on those frames; H2 if the variant's spellF1 is
lower than A's on most development matches.

## 3. What changes and what does not

- **One function of A is replaced**, in the variant's own process: the ball-free fit (`ballfree.cross_fit`) returns
  the logits of a fixed model trained on DFL, and the ball-free weight is a constant instead of being set by the
  model's agreement with ball proximity on the match. Everything else is A v1.6 as delivered: the same evidence,
  decoder, constants and self-calibration, and the same frames where the ball-free evidence applies.
- **Features**: A's own `ballfree.features` (team shape and movement, raw, smoothed over 1 s and 4 s, and 2 s means
  shifted 1 s and 2 s ahead and 1 s behind), computed by A's own code on each bundle.
- **Model**: an L2 logistic regression, fitted with A's `fit_logistic` and A's `l2 = 1.0`, made **antisymmetric
  under swapping the two teams**: the logit changes sign when home and away are exchanged, so the model has no
  preference for either side. It uses the five features that change sign under that swap (spreads in x and y, mean
  speed, block position, block velocity: 5 × 6 windows = 30 columns) and no intercept. The other two
  (`relative_position`, `relative_velocity`) do not change under the swap: a team-symmetric linear model cannot use
  them to say *which* side has the ball. Reason: a model fitted on five other matches must not carry their home and
  away habits into BAR–ATH.
- **Training data**: the five development matches of plan §2 (`J03WMX`, `J03WOH`, `J03WOY`, `J03WPY`, `J03WQQ`),
  observed through the `full` profile with seed 47 (anonymous fragmented tracks and position noise, the closest
  profile to the ATD; the shape features only use the players). The reserved matches `J03WN1` and `J03WR9` are
  **not downloaded** on the machine where the variant is developed.
- **Targets**: the DFL labels (`BallStatus` active and `BallPossession`), on live frames with valid features, one
  frame in three (A's `ballfree.subsample`). Dead frames are not used to train.
- **Weight**: A's own rule, `clip((acc − 0.55) / 0.20, 0, 1)`, applied to the mean leave-one-match-out accuracy on
  the development matches (live frames with valid features, against the DFL labels). It is fixed in the shipped
  model.
- **On BAR–ATH nothing is fitted, tuned or selected.** The log prints the model's agreement with ball proximity as a
  diagnostic; it is not used.
- **Out of scope**: A's other self-calibrations stay as they are. The Smart Tagging calibration also measures
  agreement with proximity-confident frames: worth adding to the question to the organisers, but not changed here.

## 4. Development evaluation, fixed now

Development matches only. Every run uses the official metric code through `heldout/score.py` and the observations of
`heldout/degrade.py`, exactly as the harness builds them.

- **Component (H1).** For each development match, the model trained on the other four against A's self-trained
  model on that match, both against the DFL labels: accuracy on (a) live frames with no ball, (b) live frames with
  the ball in sight but no clear control, (c) all live frames with valid features. Every profile, seed 47.
- **End to end (H2).** A v1.6, A without the ball-free model (`ballfree.enabled=0`), and the variant with the model
  trained on the other four matches. Each development match, the five profiles, seeds 47, 48 and 49.
- **Gate to send the variant to the reserved comparison**: averaged over the degraded profiles and seeds, its
  spellF1 is higher than A's on at least 3 of the 5 development matches, and its macroF1 is at most 0.02 lower than
  A's on average. Otherwise the result is "no improvement on development", and the variant is only offered as the
  compliant fallback if the organisers rule out self-training (against A without the ball-free model).

The leave-one-match-out runs need a different model per match, which a fixed P0 config cannot carry, so they go
through `solution/a_dfl/develop.py`. The reserved comparison uses Edu's harness unchanged, with the model trained on
all five development matches.

## 5. Risks

- **Domain gap.** DFL is corrected optical tracking of the Bundesliga and 2. Bundesliga; the challenge ATD is
  automatic tracking of LaLiga, with 46 anonymous slots and fragmented tracks. Team-level features (means, spreads,
  speeds) should travel better than anything about the ball, but there is no way to measure the gap on BAR–ATH
  without labels.
- **Two definitions of possession.** DFL's `BallPossession` is not Metrica's ground truth (plan §1.1). A model
  trained on DFL labels learns DFL's definition.
- **Style.** Four of the five development matches are Fortuna Düsseldorf's (2. Bundesliga). BAR–ATH is a much more
  lopsided match (Barça had about 65% of live possession in A's log). A symmetric model cannot use match-specific
  asymmetries that A's self-trained model can.
- **No adaptation.** With a fixed weight, a model that transfers badly is not switched off. The agreement line in
  the log shows it, label-free, but nothing acts on it automatically.
- **Two reserved matches** describe uncertainty conditional on those matches (plan §3.3).

## 6. Deviations from the #47 plan

- The variant is fixed on **Thursday 29 October**, not on Wednesday 28.
- Development runs go through `solution/a_dfl/develop.py` (section 4), not through `heldout/run.py`.

## 7. Results on the development matches

*Added after the runs.*
