# Issue #20: Smart Tagging phase audit

## Protocol recorded before the audit runs

Audit the existing phase-prior implementation in `solution/a_opus/tags.py`,
`pipeline.calibrate_tag_codes` and `evidence.tag_team_llr`; reuse it rather than add a competing component.
The submitted `candidate_a_dfl` uses this same pipeline with its shipped external ball-free weights.
Do not change frozen inference, weights, configuration, thresholds or the selection decision in #62.

Component checks use invented XML/events and geometric observations: case/team/missing-value handling,
half-open tactical-frame conversion, attacking/defending polarity, unknown inputs, half clipping, duplicated
support, contradictory/overlapping phases, the per-frame weight bound and label-free calibration.
Report malformed XML, degenerate intervals, interior whitespace and duplicate calibration coverage as
diagnostics of the current implementation, not silent fixes or new passing acceptance claims.

The paired experiment uses the existing synthetic generator, **seeds 20, 21 and 22**, **three minutes per
half**, default noisy observations. Conditions are fixed as: original tags, absent tag file, empty tag file,
opposing phase duplicates, repeated supporting phases, and phase windows shifted by −25 / +25 frames.
Only phases change; original set-piece windows remain except in the explicitly absent/empty-file conditions.
These generated phase events are correlated with the generator's invented reference; they are development
fixtures, not an independent tagger evaluation or held-out validation.

For each identical input, run the shipped DFL candidate with `tag.enabled=0` and `tag.enabled=1`, leaving
`dead.setpiece_enabled=1` and `p2.enabled=0`. This ablates **P7's phase team prior**, not every use of Smart
Tagging. Compare official synthetic spellF1/macroF1, possession counts and changed output frames, and record
input/source/configuration/CSV hashes. Repeat the original condition for each seed to check determinism.
The reference is read only by the evaluator and removed from the input folder before inference.

No challenge asset, challenge ground truth, video or reserved DFL file is used. No parameters are tuned.
Record every seed and condition, including ties/regressions. A gain on these fixtures does not change the
final candidate or establish real-match benefit; a negative result is still evidence for #20.

Review by Jimy/Edu and the unresolved inheritance of per-match calibration declarations remain separate
from this technical audit. Acceptance will be mapped to evidence after the runs, retaining any gaps.

## Existing component and interface

Audit date: **11 November 2026**, branch `codex/issue-20-smart-tagging-audit`, base
`1da470d8082f1b7a701773f3d13c6c844cca8469`. Candidate: `candidate_a_dfl`, version `1.6.0+dfl.2`.
All inference Python, weights, configurations, official metrics and environment definitions still match
`final-a-dfl-rc1`. The candidate README correction below describes existing behaviour; it changes no inference.

| Issue requirement | Existing implementation and audit coverage | Status |
|---|---|---|
| Reuse the loader; normalise codes, teams and missing values | `tags.load` reuses `starter.load_smart_tagging.load`, as P2 does. Outer whitespace/case and known team spellings work; missing/unrecognised sides are neutral. Noncanonical/malformed input limits are recorded below. | Covered for canonical input, with explicit parser limits |
| Separate tactical phases from P2 restarts | Attacking and defending phase dictionaries have opposite prior polarity; `SET PIECES` is not a phase prior. Set-piece D evidence and optional P2 have separate switches. | Covered |
| Per-frame signals, coverage and overlaps | `evidence.tag_team_llr` produces a signed H-versus-A vector per half. Intervals are half-open, in tactical video frames, clipped against the half's start/length. Missing/unrecognised/unsupported phase input contributes zero, not a fabricated possession. | Covered; calibration counts are event occurrences, not unique coverage |
| Bounded, configurable combination | Phase contribution is added to geometry, with up to 0.03 nats/frame per distinct interval and a total cap of ±0.06. The component test checks that maximally conflicting phase evidence does not overturn full-strength observed geometric control per frame. This is not a guarantee about a whole decoded path. | Covered |
| Missing events, contradictory labels, overlaps and offsets | 18 component tests plus seven synthetic file/phase conditions. Equal opposing phase contributions cancel; duplicate emission support uses the most reliable code for identical boundaries and implied side. | Covered, with duplicate-calibration limitation |
| Same-version comparison with component on/off | 21 paired synthetic conditions, 42 primary valid CSVs plus six repeated CSVs; only `tag.enabled` differs within a pair. | Completed on declared development fixtures |
| Team integration/evaluation review | The component is already integrated in the candidate; Jimy/Edu must review the acceptance mapping and retained limitations. | Pending acknowledgement |

### Phase dictionary and normalisation

Prior **with** the tagged team: `build up`, `progression`, `creating chances`, `ball in final third`,
`ball in the box`, `players in the box`, `long ball`, `attacking transition`.
Prior **against** the tagged team: `defending in defensive third`, `defending in middle third`,
`defending in attacking third`, `defensive transition`. Other codes are not phase evidence.
These are prior directions, not possession labels: geometric agreement can flip a code or suppress it.

Team values are matched to metadata names with the existing normaliser/fuzzy matching and known
Barcelona/Athletic spelling fallbacks. Empty, N/A, none and unrecognised names stay unknown. The loader strips
outer whitespace and lowercases codes/label-group names; it does not collapse interior code whitespace.
Seconds are rounded at 25 fps to tactical video frames without a broadcast offset. The existing adapter
extends zero/reversed-duration events to one frame rather than rejecting them.

### Configuration and scope of the switch

| Setting | Frozen value | Meaning |
|---|---:|---|
| `tag.enabled` | 1 | Enable phase calibration and the phase H/A contribution |
| `tag.beta` | 0.03 | Per-interval/per-frame weight at reliability 1 |
| `tag.max_per_frame` | 0.06 | Absolute cap after overlapping contributions |
| `tag.min_calib_frames` | 100 | Confident frame/event occurrences needed for empirical calibration |
| `tag.default_reliability` | 0.3 | Weak prior when that count is insufficient |
| `tag.full_agreement` | 0.8 | Agreement scale for full reliability |
| `dead.setpiece_enabled` | 1 | Separate automatic restart-window D/live evidence |
| `p2.enabled` | 0 | Separate P2 detector, unchanged and disabled |

Phase evidence is added on **all covered frames**, including observed ball/control. The old English README's
missing-ball-only statement and 0.03 total-cap description were inaccurate; they are corrected in this change.
`tag.enabled=0` removes neither automatic set-piece evidence nor other geometric D/live evidence. A missing
whole tag file removes both phase and set-piece inputs, so it is not equivalent to disabling P7 alone.
The experiment compares on/off *within* each identical-input condition, rather than interpreting differences
between original and absent-file conditions as P7 effects.

## Paired synthetic results

Every primary and repeated CSV validates with **199,319 rows**, frames 0..199318. Each seed has **9,000
synthetic scored frames**, three minutes in each half; the remaining reference frames are X. The shipped
DFL weights are used, and logistic fitting is blocked during inference. The evaluator-only synthetic
reference is removed from the input directory before either model call. Other inherited label-free
calibrations still run as in the frozen candidate; they are not newly certified by this experiment.

Original generated tag condition:

| Seed | Phase / set-piece events | spellF1 off | spellF1 on | macroF1 off | macroF1 on | Possessions off / on | Changed scored frames |
|---|---:|---:|---:|---:|---:|---:|---:|
| 20 | 9 / 6 | 0.775000 | 0.775000 | 0.926001 | 0.926001 | 16 / 16 | 0 |
| 21 | 13 / 5 | 0.786667 | 0.786667 | 0.923422 | 0.923422 | 14 / 14 | 0 |
| 22 | 13 / 5 | 0.757143 | 0.827586 | 0.935132 | 0.951233 | 13 / 14 | 108 |

All seven predeclared conditions, expressed as on-minus-off differences:

| Condition | Delta spellF1, seeds 20 / 21 / 22 | Delta macroF1, seeds 20 / 21 / 22 | Changed scored frames, seeds 20 / 21 / 22 |
|---|---|---|---|
| Original | 0 / 0 / +0.070443 | 0 / 0 / +0.016101 | 0 / 0 / 108 |
| Missing file | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Empty file | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Opposing phases | 0 / 0 / 0 | 0 / 0 / 0 | 0 / 0 / 0 |
| Repeated phases | 0 / 0 / +0.070443 | 0 / 0 / +0.016101 | 0 / 0 / 108 |
| Phase shift −25 frames | 0 / 0 / +0.070443 | 0 / 0 / +0.015504 | 0 / 0 / 112 |
| Phase shift +25 frames | 0 / 0 / 0 | −0.000006 / +0.001064 / −0.000002 | 4 / 8 / 2 |

**Interpretation:** the implemented phase switch works and its effect is reproducible. There is a gain on
one original generated world and ties on two; a one-second delayed phase window removes that spellF1 gain
and produces small mixed macroF1 changes. Opposing-phase conditions contribute no output change here.
The repeat condition retains the same prediction effect on these worlds; the separate short calibration
probe below shows why this does not establish general duplicate invariance.

This is not a demonstrated robust improvement. Phase events are generated from the invented world's
labels with jitter/omissions and are correlated with the evaluator's reference. These three development
worlds, their related variants and their short halves cannot establish actual Smart Tagging quality,
uncertainty across matches or performance on BAR–ATH. No public/private challenge score or reserved DFL
result was consumed. Keep the frozen candidate unchanged; do not select a switch value from this audit.

## Retained limits and decisions needed

1. **Duplicate calibration coverage:** with 40 unique confident frames balanced between teams, a single
   event gets the weak prior (40 occurrences, reliability 0.3). Three copies count 120 occurrences, cross
   the 100-frame threshold and yield reliability 0. The resulting phase signal changes by 0.009 nats/frame.
   Emission deduplication does not prevent repeated same-code observations inflating calibration counts.
   This is a concrete robustness gap to review, not a measured rate of real input duplication.
2. **Interior whitespace:** `BUILD  UP` becomes `build  up`, which is not in the dictionary and contributes
   no phase prior. Canonical case/outer-space normalisation passes; arbitrary whitespace does not.
3. **Degenerate intervals:** a zero-duration invented interval at frame 10 is loaded as [10, 11).
   Reversed intervals receive the same one-frame extension by the current adapter. Strict rejection is not
   implemented. This audit demonstrates the zero-duration case, not a full malformed-interval validation suite.
4. **Malformed XML:** `ParseError` propagates. A missing file has an explicit neutral fallback; a broken
   XML file does not. No silent fallback for damaged XML is claimed.

Record these limits in review. Any proposed runtime correction needs the candidate owners' agreement and
an unused validation plan before it enters the frozen submission; this audit makes no such correction.
Review by another teammate is required for #20 acceptance. Do not mark all criteria complete or close the
issue automatically while that acknowledgement and the handling of these limits remain unresolved.

## Verification and reproduction

Docker Desktop 4.96.2 / engine 29.9.2, existing `gtt-mtah:local` image
`sha256:3f1d1d73217e38d3025e833ace299c252540d35586cda0ff568f2e9308a79182`;
Python **3.11.17**, NumPy **2.4.6**, pandas **3.0.6**. The `evaluar` service mounts the repository read-only
and ignored outputs, without the external match-data folder. Temporary invented input/prediction folders
are removed after each seed; only aggregate metrics and identities are retained.

| Check | Result | Ignored evidence under `salidas/issue20-20261111/` |
|---|---|---|
| New component checks | 18 pass; the final version directly checks observed geometric control against conflicting capped phases | `component-tests-verified.log` |
| Shared regression | 140 pass, 66.809 s; the strengthened component assertion was then rerun successfully | `shared-tests.log` |
| Paired experiment | 21 pairs / 42 valid CSVs, plus six valid deterministic repeat CSVs | `audit-report.json`, `ablation.log` |
| Original-condition determinism | Both on/off profiles reproduce for all three seeds | `runs[].repeat_sha256` in the report |
| Pre-run protocol | Saved before generation; SHA-256 `97caf8ca366bf199a2263cbb4a4e77164522dd0843ab5856c3dfdd0a60369a86` matches the report | `protocol-before-results.md` |
| Final evidence audit | All 21 pairs, six repeats, protocol/source/configuration hashes and document links checked; 43 frozen runtime/environment files match the release tag | `evidence-audit.json`, `evidence-audit-verified.log` |

The report records the base/tree state, candidate sources/weights, test/runner/loader hashes, two
configuration hashes, per-condition input hashes, synthetic-reference hashes and every CSV hash. The
working tree includes new audit code/tests/docs, and the Windows CRLF mount also makes the container's
Git state dirty. This is not a clean release reproduction or a new model version.

Run from the repository root with a new output path (the runner rejects existing report files):

```powershell
docker compose run --rm -T --pull never --entrypoint python evaluar -m unittest discover -s tests -p test_smart_tagging.py -v
docker compose run --rm -T --pull never --entrypoint python evaluar -m unittest discover -s tests -v
docker compose run --rm -T --pull never --entrypoint python evaluar -m tools.smart_tagging_audit --out /salidas/issue20-repeat/audit-report.json
```

On this Windows machine, prepend `--context desktop-linux` after `docker` if needed. Build the common image
first on a new machine. A zero audit exit code means report generation and its technical invariants passed;
the parser/calibration limitations still need review. The initial protocol above is retained as a historical
pre-run specification; later regenerations hash the then-current report document rather than the initial
protocol-only snapshot. The original snapshot and its matching hash are preserved in the local evidence.
