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

Added on 29 October 2026, after the runs. The variant was frozen in commit `496893b` (its `weights.py`) before any
end-to-end run. Nothing was changed after seeing these results. The reserved matches have not been run.

### 7.1 The component (H1): supported

Model trained on the other four matches against A's self-trained model on the match, `full` profile, seed 47,
agreement with the DFL labels on the frames where A's model gives an answer (from `train.py`):

| match | no ball | ball in sight, no clear control | every live frame |
|---|---|---|---|
| J03WMX | 79.7% → **81.4%** | 76.8% → **82.6%** | 81.7% → **84.2%** |
| J03WOH | 85.7% → **88.0%** | 86.0% → **88.9%** | 87.6% → **89.4%** |
| J03WOY | 82.4% → **84.8%** | 81.8% → **85.5%** | 83.8% → **86.6%** |
| J03WPY | 81.7% → **84.3%** | 85.5% → **87.9%** | 85.1% → **87.6%** |
| J03WQQ | 85.8% → 85.8% | 86.2% → **87.6%** | 88.2% → **88.3%** |

Over all 65 development runs (every profile and seed): 84.6% → 86.2% without the ball, 82.2% → 85.2% with unclear
control, 85.5% → 87.3% on live frames. The mean leave-one-match-out agreement on every live frame is 87.5%, so A's
rule gives the shipped model **weight 1.00**.

### 7.2 End to end (H2) and the gate: passed

Each development match, averaged over the four degraded profiles × three seeds (12 runs), official metric code:

| match | spellF1 A | A, ball-free off | **variant** | variant − A | macroF1 A → variant | false short / 90 min A → variant |
|---|---|---|---|---|---|---|
| J03WMX | 0.3675 | 0.3462 | **0.3862** | +0.0187 | 0.8555 → 0.8647 | 0.3 → 0.2 |
| J03WOH | 0.4431 | 0.3851 | 0.4418 | −0.0013 | 0.8601 → 0.8648 | 0.5 → 0.6 |
| J03WOY | 0.3777 | 0.3358 | **0.4199** | +0.0422 | 0.8301 → 0.8461 | 0.1 → 0.0 |
| J03WPY | 0.4442 | 0.3850 | **0.4596** | +0.0154 | 0.8642 → 0.8745 | 0.1 → 0.2 |
| J03WQQ | 0.4910 | 0.4215 | 0.4837 | −0.0073 | 0.8612 → 0.8623 | 0.4 → 0.2 |
| **mean** | 0.4247 | 0.3747 | **0.4382** | +0.0135 | +0.0083 | |

Per profile, mean over the five matches and their seeds (spellF1, A / A ball-free off / variant): `clean` 0.5038 /
0.4933 / 0.5037 · `gaps-short` 0.4480 / 0.4156 / 0.4485 · `gaps-long` 0.4416 / 0.3749 / 0.4417 · `gaps-crowded`
0.4014 / 0.3587 / **0.4345** · `full` 0.4077 / 0.3497 / **0.4283**. Transition F1 at 25 frames: 0.433 → 0.450;
predicted possessions per match: 197 → 197.

**Gate (section 4): passed.** The variant is above A on 3 of the 5 matches, and its macroF1 is 0.0083 *higher* on
average. Against A without its ball-free model, the variant is higher on all five matches, by 0.040 to 0.084.

Absolute values are low (DFL has ~438 possessions per match against ~197 predicted). DFL's definition of possession
is not the challenge's (plan §1.1): only the paired differences mean anything.

### 7.3 Checks

- **The development driver reproduces the harness.** A on J03WMX `full`-47 through `heldout/run.py` (P0, a separate
  process) and through `develop.py` (in-process): same observation hash, byte-identical CSV, spellF1 0.3522 both.
- The variant runs through P0 with `configs/candidate_a_dfl.json` (`heldout run`, 23 s per DFL match).
- `python -m solution.a_dfl.tests --full` and `python -m solution.a_opus.tests --full` pass. A's CSV is
  byte-identical before and after the variant runs in the same process.

## 8. Post-hoc analysis: where the gain comes from

*Not pre-registered. It does not change the gate; it is here because it changes what to expect on BAR–ATH.*

A trains its ball-free model for one half on the other half's proximity-confident frames, and needs at least 2,000 of
them after subsampling (`ballfree.min_train`). On DFL the control zone calibrates tight (precise tracking: d0 0.53 m,
σ 0.70 m on J03WMX) and only ~9% of graded frames have a clear side on the ball. When the gaps hide the ball near
the players (`gaps-crowded`, `full`), one half often has too few targets, and **the other half gets no ball-free model
at all** (weight 0). That happened in 21 of the 30 `gaps-crowded` and `full` runs (4 with no model in either half),
and never in `clean`, `gaps-short` or `gaps-long`.

| development runs (degraded profiles) | runs | spellF1 A | variant | variant − A | variant above A |
|---|---|---|---|---|---|
| A's model missing in a half | 21 | 0.3748 | 0.4165 | **+0.0417** | 21 of 21 |
| A's model in both halves | 39 | 0.4516 | 0.4499 | **−0.0016** | 15 of 39 |
| … of which `gaps-short`, `gaps-long` | 30 | | | +0.0003 | 13 of 30 |
| … of which `gaps-crowded`, `full` | 9 | | | −0.0080 | 2 of 9 |

- **The whole average gain comes from the runs where A's self-trained model is missing.** Where A has its model in
  both halves, the variant ties with it (−0.0016), although its agreement with the labels is higher (section 7.1).
- A likely reason for the tie: A's self-trained logits are more extreme. On live frames, 61–76% of them reach the
  ±3 clip, against 32–44% for the variant (mean |logit| 2.4–2.7 against 2.0–2.3). So the variant's ball-free evidence
  is about 15–20% weaker per frame: more often right, but quieter.
- **BAR–ATH is in the "both halves" case.** A's logs on the challenge match show the self-trained model with
  held-out agreement 82–88% in both halves (`solution/a_opus/README.en.md`), so weight 1 in both. **On BAR–ATH,
  the variant should be expected to tie with A, not to beat it.**
- The reserved matches will probably show the same pattern. A win there driven by A's missing halves would not
  transfer to BAR–ATH. The coverage of A's model per run (A's log line `ball-free team model … -> weight a / b`) should
  be reported next to the result.

## 9. What this means for #47

The decision is Alejandro's (plan §3.6). This is the evidence from the development matches:

- **As a replacement for A, the variant shows no improvement where it would matter.** It ties with A when A's own
  model works, which is BAR–ATH's case.
- **As the compliant route, it works at no measured cost.** It does not learn from the challenge match, it ties with
  A where A is complete, and it is more robust when A's self-training lacks data. If the organisers rule out
  self-training on the provided match, the variant beats the alternative (A with the ball-free model off) on all five
  development matches, by 0.040–0.084 spellF1.
- So the variant's value depends on the organisers' answer (question 3 of the email). With self-training allowed,
  keep A. Without it, use the variant rather than switching the model off.

## 10. Reproduction record

| item | value |
|---|---|
| pre-registration | commit `2b25096` (29 Oct 2026, 15:43 CET), before any run of the variant |
| variant frozen | commit `496893b`: `solution/a_dfl/weights.py`, SHA-256 `70aa2f52…5d1b82f` with LF line ends |
| candidate A | `solution/a_opus` unchanged from `main` at `675498b`; feature-code SHA-256 `a3f8f8d9…a5e5071` |
| DFL data | figshare 10.6084/m9.figshare.28196177 v1, CC BY 4.0; MD5 of each file in `weights.py` |
| environment | Windows 11, Python 3.11.3, numpy 2.4.6, pandas 3.0.6, kloppy 3.18.0 (`docker/heldout.lock`), no Docker |
| hardware | Intel Core i5-8400 (6 cores), 16 GB RAM |
| durations | features 40–45 s per match; 195 development runs in ~30 min with 5 processes; 10–23 s per run |

```bash
python -m heldout fetch J03WMX J03WOH J03WOY J03WPY J03WQQ
python -m heldout convert J03WMX J03WOH J03WOY J03WPY J03WQQ
python -m solution.a_dfl.train                    # weights.py identical to 496893b (git diff is empty)
python -m solution.a_dfl.develop --matches J03WMX # one per match, in parallel if wanted
python -m solution.a_dfl.develop --summary
```

## 11. Pending

- **Edu: the reserved comparison**, with the harness unchanged, on the frozen variant:
  `heldout run --heldout --matches J03WN1 J03WR9 --model a=configs/candidate_a.json --model v=configs/candidate_a_dfl.json`
  and `heldout report --a a=configs/candidate_a.json --variant v=configs/candidate_a_dfl.json`. Please add the
  coverage of A's ball-free model per run (section 8).
- **Jimy: the plausibility check on BAR–ATH** (plan §3.4), run locally. Only the aggregate log comes back: number and
  median length of possessions, share of `D`, and the variant's agreement line.
- **Alejandro: the organisers' answer** on self-training (it decides between A and the variant), and whether the Smart
  Tagging calibration, which also uses proximity-confident frames, needs the same question.
- A possible next iteration, which would need a new pre-registration: calibrate the scale of the variant's logits on
  the development matches (section 8).
