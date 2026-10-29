# Reading of the public metrics received

> 🇪🇸 English translation of [ANALYSIS.md](ANALYSIS.md). The Spanish original is kept unchanged.

This note uses only the aggregates provided by the participant. No match
CSV was opened and the method is not changed on the basis of these results.

## What improvement is observed

`spellF1` goes from 0.3256 to 0.3895: **+0.0639**. `macroF1` rises by **0.0413**.
It goes from 26 to 21 possessions against 17 real ones, and from 10.8 to 13.6 s of mean
duration against 14.2 s. This is consistent with less fragmentation, but getting a count
or a mean right does not guarantee getting the intervals or their teams right.

The formula allows part of the rise to be separated descriptively. At each IoU threshold:

`F1 = 2 × TP / (N_GT + N_pred)`.

The denominator is constant across the five thresholds, so it also holds for
the mean of the TPs. With the rounded numbers provided:

- Baseline: `0.3256 × (17 + 26) / 2 ≈ 7.0` average matchings.
- Candidate: `0.3895 × (17 + 21) / 2 ≈ 7.4` average matchings.
- Keeping 7.0 matchings and dropping to 21 predictions, the F1 would be
  `14 / 38 ≈ 0.3684`: about **0.0428** of the rise is explained by the smaller
  denominator. The remaining **0.0211** comes from the increase in matchings.

So about two thirds of the rise comes from fewer
predictions, and one third from more matchings. It is an arithmetic decomposition, not
a causal ablation or proof that exactly five errors were removed.
Nor is it exactly "one more possession": it is about **0.4 extra average
matchings** across thresholds. A possession can match at some IoUs and not at others.

The 90 % CIs `[0.214, 0.447]` and `[0.242, 0.537]` overlap widely. With only 17
possessions there is no basis for claiming an improvement that generalises. The overlap of two
marginal intervals is not a formal test of the difference either; that would need a
paired analysis. The window is not used to choose a threshold or a version.

## What could generalise

Separating "ball not observed" from "dead ball" addresses a documented structural
failure: the ball is missing in many images, also during live play. Keeping
the possession during an occlusion can avoid false cuts anywhere in the
match. The same goes for requiring absolute proximity and persistent evidence before
switching to the opponent during a pass. These are reasons of continuity and control, independent
of the number of possessions in this window.

The switching cost and decoding without reducing the temporal frequency can also
keep complete intervals without systematically shifting the boundaries.
But they can merge real short possessions or delay hidden changes. The mix of
occlusions, throw-ins, free kicks and attacks may be different in the rest of the match. The
+0.0639 is not extrapolated, and 21 possessions/13.6 s is not adopted as a target.

## Why team assignment may not improve

The candidate keeps essentially the same source of information: distances between
the ball and the nearest player of each team. Confidence and continuity
regularise that decision; they do not add independent observations of who is in control.

If the projected 2D ball passes near an opponent during a flight, the receiver is missing
from the tracking, teams get mixed up or the ball is lost during the change, both
methods can be wrong in the same way. Smart Tagging is inferred from the same
inputs and describes phases, not complete possessions; it is not a reliable second annotator.
Keeping the last team can correct fluctuations, but also keep the
previous team for too long. It is plausible to improve the structure without increasing
per-frame team accuracy.

There are also two different metrics in the evaluator: accuracy over all live GT
frames and accuracy conditional on both GT **and prediction** being live. Changing `D`
changes the denominator of the second one. To compare, the same field has to be used;
the abbreviated table does not say which one was reported.

## What the values received do not allow concluding

The candidate's row does not include the `D` F1 or the team accuracy. The participant's
verbal remark that the team does not improve is taken as additional information; it
cannot be checked or quantified with that row. The rise in `macroF1` on its own
does not show that `D` improves.

In fact, if there are no abstentions inside the window and the means refer to
the same scored stretches, the approximate products suggest:

- Baseline: `26 × 10.8 ≈ 280.8 s` of live possession in 300 s.
- Candidate: `21 × 13.6 ≈ 285.6 s` of live possession.

That would leave about **6.4 %** and **4.8 %** `D`, respectively, against the
~19.6 % published for the window. These are inferences from rounded means and assumptions
about the scope of the report; the exact percentages have to come from the diagnostic.
Having less `D` does not prevent its F1 from improving if precision rises, but it does not show
better coverage of stoppages. That is why percentages and restart coherence
for the whole match are added without consulting the GT, instead of tweaking the detector.

## Decision for this version

The method and all its parameters are kept. Symmetric diagnostics are added for
the candidate and the baseline, with explicit denominators. Coherence with Smart
Tagging is an internal and partly circular check: the candidate already uses
those annotations. It serves to detect suspicious behaviour, not to estimate
`spellF1` or to maximise that coherence at the cost of labelling everything as `D`.

Really improving team assignment would require additional evidence of reception,
control and trajectory, or external validation with compatible semantics. No
classifier is added now and no radii or costs are changed on the basis of these five minutes.
