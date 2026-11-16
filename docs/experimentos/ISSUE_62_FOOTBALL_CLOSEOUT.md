# Issue #62: football review and delivery risks

Review prepared for Pablo on **11 November 2026**, covering his three tasks in
[#62](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/62). This is the technical
handoff for the submission document; team acceptance, independent final reproduction and submission remain
with their respective owners.

## Recommendation for the freeze

Retain the identified `candidate_a_dfl` candidate and record the limitations below. Keep P2 disabled. The
synthetic evidence does not justify a last-minute restart rule, a threshold change or a claim of improved
BAR–ATH accuracy. The unresolved second-half kick-off remains a limitation of #14; this review does not
complete that issue's acceptance criteria.

Jimy's [10 November candidate record](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/62#issuecomment-6766383535)
identifies version `1.6.0+dfl.2`, tag `final-a-dfl-rc1`, commit
`bf4f994c9711a56c1432fbe71d1a554040af600c` and `configs/candidate_a_dfl.json` (seed 0).
The checked-out main base is `cf04e15b6bafc40bd059a11ce44b8f2d094b6438`. Its model Python files,
configurations, evaluator, timeline and Docker environment files match that tag; subsequent differences in
the model directories are documentation only. This work adds review tooling and documentation, with no
inference, weight, threshold or configuration change.

The weights were trained on five DFL development games. The already published reserved comparison in
[the common report, section 4.2](ISSUE_47_ALTERNATIVE_TO_A.md#42-paired-external-results) supports the
eligibility-based replacement recommendation under its amendment. It does not establish superiority over A:
one paired interval includes zero, the second reserved match has mixed results, and DFL's targets/domain
differ from the challenge. The variant replaces the ball-free team model; it does not redesign live/dead
decoding or recover unobserved restart timing. Other inherited per-match calibrations still require the
team's eligibility declaration. The reserved matches have been consumed and were not rerun here.

## Interpretation of PR #55

Replayed the existing **17 invented worlds in four conditions each**: original, team swap, unscored offset
and within-team slot permutation. The unchanged A runner and the fixed DFL candidate each produce
**12 passes, 20 failures and 36 diagnostic-only results**, plus **two team-swap flags** in unsupported cases.
All 68 paired observation hashes and all 68 paired prediction CSV hashes match. Identical outputs on these
small development worlds do not establish equivalence on full matches or independent validation.

| Football behaviour | Evidence and interpretation |
|---|---|
| Deflection, neutral contest, same-team occlusion (FA02–FA04) | All 12 probes meet the existing targets. Retaining the team through a touch/duel without demonstrated opposing control, or through a same-team gap, is reasonable. These examples do not validate every contact or gap. |
| Genuine short recovery (FA01) | All four probes fail. In the baseline trace, usable control/team evidence exists, but neutral dead evidence gives D the best live emission without paying H/A switching costs. All-D can therefore win in this toy world. This is a live/dead scoring limitation, not proof that all short recoveries are always removed or that control is absent. |
| Different team after a missing-ball gap (FA05) | All four probes fail the observable-bracket target. Interpolated geometry is not a measurement of the hidden recovery. The exact switch inside an occlusion is unobservable; a model should not claim frame-exact knowledge there. |
| Same-team restart after a stoppage (FA06) | All 12 probes fail strict topology/boundary targets. The same team before and after does not make the interruption one possession. P2 component successes do not certify the complete candidate: P2 is off in its default configuration. |
| Gradual motion, shifted kick-off tags, reset and unsupported input (FA07–FA10) | All 36 remain diagnostic, not acceptance passes. The two team-swap flags are in unsupported FA09/FA10 conditions; no offset or within-team slot-permutation flag occurs. They expose tie/prior behaviour, not demonstrated cross-half state leakage. |

The [PR #55 rule review](ISSUE_47_ALTERNATIVE_TO_A.md#39-football-rule-review) was reproduced: every one
of its 17 observed baseline CSVs matches a separate ordinary run. Contact versus control, imputation versus
measurement, and a detector's confirmation versus physical onset remain distinct. No failure count here is a
real-match error rate, and the simplified collective movement limits label-free calibration.

## Second-half kick-off and P2

The existing initial-kick-off branch resets per half and requires three consecutive moving observations
at at least 2 m/s within the automatic event window, with the motion start or preceding observation within
3 m of the centre. It is separate from the general stillness-to-motion rule; that rule's one-second bounded
search does not extend the initial-kick-off window.

| Existing invented probe | Reproduced detector result |
|---|---|
| Period-2 event shifted −25, 0 or +25 frames, with central motion still supported inside it | Confirms the physical onset in all three examples. |
| Window ends at onset, or includes only two moving frames | No confirmed restart. |
| Five missing frames cover onset | Confirms five frames late (+0.20 s at 25 fps). This dates later observed motion, not the hidden kick. |
| Ball reappears beyond the central zone | No confirmed restart. |
| Gradual acceleration, then its smoothed version | General preparation confirms +4 / +6 frames after the invented first motion (+0.16 / +0.24 s). |
| Tag without ball observations, or no restart evidence | No confirmed restart; unknown signal validity is preserved. |

**Decision for #62:** document missed/late restarts as a retained limitation. These supported cases do not
resolve the real second-half boundary in #14. Its prior aggregate diagnostics reported two initial contexts
but only one confirmed restart; that is historical coverage evidence, not manually verified correctness.
This work does not inspect challenge video, annotate intervals or create a frame-specific correction.

For future development, any proposed general rule must work across halves, tag shifts, observation gaps and
unrelated central motion, distinguish preparation from resumption, and report uncertainty when the onset is
hidden. It needs independently agreed, unused validation evidence before changing the frozen candidate.
The available evidence does not show that widening the window or enabling P2 improves the complete model.

## Text for the technical document

The final candidate uses geometric control proxies and temporal decoding, with its ball-free team component
trained on external DFL development matches. Synthetic review confirms reasonable handling of selected
deflections, neutral contests and same-team gaps, while exposing failures on short recoveries, hidden team
changes and same-team stoppages. Neutral live/dead evidence and temporal costs can favour D in simplified
worlds despite usable team evidence. Missing or smoothed ball observations can delay or prevent restart
confirmation, including the second-half kick-off. P2 remains disabled in the final candidate; its component
checks do not establish a full-model improvement. DFL comparisons support the documented eligibility-based
replacement, not a demonstrated gain on BAR–ATH. The public window is not used for model selection; the
private full-match ground truth is unavailable and no full-match accuracy is claimed from this review.

## Docker verification and evidence

Used the existing `evaluar` image, with the repository mounted read-only and outputs in ignored `salidas/`.
This service does not mount the external challenge-data folder. The review commands generate invented
tracking/targets only; no challenge ground truth, video or reserved DFL file is read.

Environment: Docker Desktop 4.96.2 / engine 29.9.2; Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6.
Image ID: `sha256:3f1d1d73217e38d3025e833ace299c252540d35586cda0ff568f2e9308a79182`.

| Check | Result | Local evidence under `salidas/issue62-20261111/` |
|---|---|---|
| Shared regression suite | 122 tests passed, 62.730 s | `shared-tests.log` |
| DFL variant suite, including synthetic training/inference isolation | Seven checks passed; uses temporary synthetic weights, leaving shipped weights unchanged | `dfl-tests.log` |
| Baseline acceptance and full-size smoke | 12 pass / 20 fail / 36 diagnostic; two symmetry flags; expected exit 1 | `acceptance.json`, `acceptance.log` |
| Fixed shipped DFL weights on the same 68 probes | Same counts and all paired CSV hashes match A; expected exit 1 | `final-candidate.json`, `final-candidate.log` |
| Baseline rule review and four kick-off probes | 17 observer/ordinary CSV pairs match; boundary results above reproduced | `rule-review.json`, `rule-review.log` |
| Final evidence/source audit | All 68 observation/CSV pairs agree; 43 runtime, configuration and environment files match the frozen tag; local document links resolve | `audit.json`, `audit.log` |

The full-size smoke is **synthetic baseline A**, not the final challenge submission: 199,319 valid rows,
two identical CSVs, SHA-256 `c6a7751eaa7ab2a78f0854aaf217c21569a986bb897ecd7a515d3456e641857d`.
Edu's clean-clone final-candidate reproduction in #22/#62 remains a separate responsibility.

The recorded baseline source/configuration, P2 and review-runner hashes match PR #55's earlier local
record (common report section 5.1). The container reports a dirty tree on the Windows CRLF mount;
read-only `git -c core.filemode=false -c core.autocrlf=true status --porcelain -uno` clears the tracked-file
differences before these documentation edits. No Git settings were changed. The new review runner and this
note are working-tree additions; these checks are not represented as a clean release reproduction.

Reproduce from the repository root. Choose new output paths; runners reject existing reports. Use
`docker --context desktop-linux compose` on this Windows machine if its default context is not the Linux engine.

```powershell
docker compose run --rm -T --pull never --entrypoint python evaluar -m unittest discover -s tests -v
docker compose run --rm -T --pull never --entrypoint python evaluar -m solution.a_dfl.tests --full
docker compose run --rm -T --pull never --entrypoint python evaluar -m tools.football_acceptance --out /salidas/issue62-repeat/acceptance.json --check --full-size-smoke
docker compose run --rm -T --pull never --entrypoint python evaluar -m tools.final_football_review --out /salidas/issue62-repeat/final-candidate.json --check
docker compose run --rm -T --pull never --entrypoint python evaluar -m tools.football_rule_review --out /salidas/issue62-repeat/rule-review.json
```

The two `--check` commands are expected to exit **1** for the retained football failures. Passing software
tests and successful report generation do not turn that acceptance gate green.

## Handoff

This supplies the synthetic interpretation, the P2/kick-off recommendation and the short technical text
requested from Pablo. Edu can incorporate the text in #23; Jimy/Alejandro retain candidate/freeze and
eligibility decisions, and Edu retains independent reproduction and final package checks. Team review and
acknowledgement are still required. The whole of #62 stays open until the team's acceptance criteria hold;
this contribution does not close #14 or any other issue.
