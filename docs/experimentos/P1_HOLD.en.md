# P1 · Temporarily keep the state when the ball is missing

> 🇪🇸 Translated from the Spanish original, [P1_HOLD.md](P1_HOLD.md).

> Issue [#13](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/13). Implementation author: Alejandro Molines. Contract v1 unchanged; new code in English.
>
> Status: implementation, tests and a first public comparison with real tracking verified. Result: a small macroF1 improvement, with no improvement in spellF1 or fragmentation; peer review and P1 CI still to be confirmed. It isn't an official result on the full match and doesn't change candidates A/B.

## Hypothesis, fixed before real results

A missing ball observation doesn't prove a stoppage. Briefly keeping the last team hypothesis could avoid artificial stoppages, but it can delay real recoveries. A provisional limit of **25 frames (1 s)** is set, not tuned on the public window. It is compared with a limit of 0 to isolate the effect of holding.

## Implementation

- `solution/hold.py`: tactical ATD reading, `ball_observed` mask, assignment to the nearest valid player, causal hold and aggregate diagnostics.
- `configs/baseline_hold.json`: limit 25; `baseline_hold_disabled.json`: limit 0, all other decisions equal.
- `solution/predict.py` and `docker/pipeline.py`: integration into the same P0 circuit, input manifest, diagnostics in `run.json` and fragmentation/abstention metrics from the official evaluator.
- `tests/test_hold.py`: fully invented examples and a full circuit with a synthetic 199,319-row CSV.

Finite coordinates are validated on both axes; invalid players and slots of unknown team don't vote. The slot isn't interpreted as a stable identity. Distances in metres according to the dimensions in `games.py`. ATD uses `frame_id - 1`; the official loaders and baseline aren't altered.

The nearest player is a **baseline hypothesis**, not proof of control. There is no calibrated control threshold in P1 and no detection of real stoppages: those belong to P3/P2. A usable observation allows switching to the newly observed team, without using the reappearance to rewrite the previous gap.

| Case | Policy |
|---|---|
| Valid H/A state and no usable observation | Repeat for at most 25 frames |
| Limit reached | X until new evidence |
| Start of a half without evidence | X; no team or D is invented |
| Change of half / outside the halves | Reset; outside the halves emit X |
| Ball visible without a valid player of a known team | No new hypothesis; same holding limit |
| Valid D evidence provided by another module | The hold function can accept it; P1's nearest-player reader doesn't produce it |

No smoothing, so as not to hide absences or carry labels across half-time. The published blocks are read from `games.half_video_blocks()`. They aren't confused with the kick-off: the second half includes a scored stretch before the kick-off. P1 doesn't resolve D in that stretch.

**X doesn't remove the temporal error:** the evaluator fills abstentions for its temporal metrics and penalises them in macroF1. A hold limit doesn't limit how far the evaluator drags the previous label. That's why abstentions, fragmentation and limitations are also recorded; no spellF1 improvement is promised.

## Run locally

From the repo root, with the [P0](../EJECUCION.en.md) environment. Replace the example paths; never copy tracking into documentation or into an external LLM.

Aggregate diagnostics without spending a public evaluation:

```bash
python -m solution.hold --data-dir /path/to/data --out salidas/p1-gap-summary.json
```

The JSON doesn't overwrite existing files. Per half, it includes the percentage without the ball, number of gaps, median, p90, maximum and distribution of durations. It separates a missing ball from the impossibility of assigning a team. It excludes half-time and frames outside the halves; the blocks may include stopped time, so it is **not** a percentage of absence over active play.

Generation and evaluation with the P0 record:

```bash
python docker/pipeline.py modelo --config configs/baseline_hold.json --data-dir /path/to/data --repetir
python docker/pipeline.py modelo --config configs/baseline_hold_disabled.json --data-dir /path/to/data --repetir
```

Docker (PowerShell):

```powershell
$env:DATOS = "D:/data/mtah2027"
docker compose run --rm modelo modelo --config configs/baseline_hold.json --repetir
```

Tests:

```bash
python -m unittest discover -s tests -v
```

Don't compare variants by running sweeps on the public window. Coordinate the evaluation budget with #26. Don't unilaterally merge this improvement into an independent candidate during the round.

## Comparison with real data · 22 October 2026

Source: records and aggregate reports from the two runs done by Alejandro on Arch Linux with Docker and copied locally for review. `run.json`, the aggregate diagnostics and the aggregate fields of `reports/candidato.json` were read. It wasn't necessary to read tracking, videos, prediction CSVs or real per-frame intervals. The original files aren't added to Git.

Verified conditions:

- Same commit `606e64142baf12469b34fe156095a4fd59757976`; both runs declare a clean tree.
- Same input manifests, evaluator and public GT hashes, environment and declared seed. The models are deterministic and don't use the seed.
- Python 3.11.17, NumPy 2.4.6, pandas 3.0.6, Linux/Arch x86_64, using the project's Docker environment.
- Same `public-5min` evaluation, 7,500 scored frames and 17 reference possessions; `bootstrap: 0`.
- Effective configurations checked against their hash: only `max_hold_frames` changes, from 0 to 25. No smoothing in either hold variant.
- Both finish with `codigo_salida: 0`, `estado: ok` and `determinista: true`. This verifies functioning/repetition as declared by the pipeline, not football quality.

| Variant | Public spellF1 | Public macroF1 | Fragmentation | Possessions | Mean duration (s) | X in public frames |
|---|---|---|---|---|---|---|
| official smooth50, evaluated in both runs | 0.3255813953 | 0.6207331924 | 1.4285714286 | 26 | 10.8031 | 0 / 7,500 (0%) |
| hold 0 | 0.0441379310 | 0.4573235834 | 6.0952380952 | 128 | 2.34375 | 885 / 7,500 (11.8%) |
| hold 25 | 0.0441379310 | 0.4603944218 | 6.0952380952 | 128 | 2.34375 | 780 / 7,500 (10.4%) |

The equality of spellF1 was also checked with the full values from the records, not just with the rounded table. Equal aggregate metrics don't by themselves show that all predicted intervals are identical.

| Variant | Run ID | Candidate SHA-256 | Total recorded duration |
|---|---|---|---|
| hold 25 | `20261022T065406.346768Z-3d98f347ed5e-modelo` | `fc128f4f8b0abd118ec2d472e70086419d97703a5aa281f6a7c16b09b1fb0d69` | 116.8 s |
| hold 0 | `20261022T065814.072224Z-833429669b5b-modelo` | `981dc2d811227f411da1d5cec558f160ce89728ff90ee16d2140975d3e94bf33` | 125.6 s |

The times include the circuit and the repetition, not just inference. Two sequential runs don't allow concluding that one variant is faster. The hashes above are transcribed from the record; the predictions weren't read again to recompute them.

### Aggregate diagnostics of absences

The published blocks of the halves are used, **including their stoppages** and the stretch before the second kick-off. Half-time and frames outside those blocks are excluded. So these figures don't represent active play only. The counts of team absence match those of ball absence in this reader and these runs.

| Block | Frames | Without ball | Percentage | Gaps | Median (s) | P90 (s) | Maximum (s) |
|---|---|---|---|---|---|---|---|
| First half | 79,467 | 32,304 | 40.65% | 69 | 11.56 | 43.328 | 138.64 |
| Second half | 79,390 | 32,339 | 40.73% | 81 | 9.80 | 25.56 | 221.48 |

Total: 64,643 frames without the ball out of 158,857 frames in the blocks (40.69%), spread across 150 gaps: 17 of up to one second, 1 of more than one and up to five seconds, and **132 of more than five seconds (88% of the gaps)**. Don't add or average the medians of both halves as if they were a global median.

With hold 25, 3,398 previously abstaining frames are explicitly held (135.92 s spread across the match; not one continuous possession). That's 5.26% of the frames without an observation. The X percentage over the full blocks goes from 40.6926% to 38.5535%. In the public window, abstentions drop by 105 frames (4.2 s), from 11.8% to 10.4%; don't confuse these windows.

### Interpretation and decision

- MacroF1 increases by `0.0030708384` (about 0.307 percentage points), without computed intervals and on a small sample: no generalisable improvement is claimed.
- spellF1, fragmentation and number of possessions don't improve. The temporal evaluator's filling of X is an explanation consistent with this result: both explicit holding and abstention can end up dragging the previous state. The per-frame temporal detail wasn't compared.
- Most gaps far exceed the one-second horizon. P1 v1 only covers a fraction of the absences; increasing the limit without evidence could drag errors through real recoveries or stoppages. This diagnosis doesn't show that it should be increased.
- The high fragmentation remains. The unsmoothed nearest-player reader can change team often; checking its causes requires a local football review. Don't attribute it only to the absences or claim that a particular solution already fixes it.
- **Decision:** keep P1 as a basic reproducible component and a mixed-result experiment; don't replace smooth50 with this variant or keep tuning parameters on the public window. Coordinate control, stoppages and temporal stability with P3/P2/P4; advanced gaps belong to P6.

The difference from smooth50 can't be attributed to the hold alone: smoothing, masks and abstention also change. The controlled comparison is hold 0 vs hold 25; outside its limits, the X label and the temporal filling can make some temporal results equal despite different per-frame labels. Don't equate any public result with the private 0.2433.

## Acceptance and evidence

- Implemented: absence doesn't force D; reset per half; configurable hold; input validation; aggregate diagnostics; record and tests without restricted data.
- Checked with real records: aggregate diagnostics, controlled comparison, CSV accepted, determinism and provenance of results. Limitations and the mixed result are documented; there is no local visual analysis of specific errors yet.
- Pending: review by Jimy for state and by Nico for masks/alignment; if needed, Pablo reviews examples locally without publishing extracts; P1 CI and the PR review still to be confirmed. No reviews were requested and no changes were published in this documentation update.
- Out of scope: P2 detects stoppages, P3 confirms control, P4 decodes temporally and P6 handles advanced gaps.

Don't close #13 just because the files are there.

## Local verification on 22 October 2026

Last run: **29 tests pass** (12 new from P1 and 17 from P0), in 65.934 s, with Python 3.12.14 / NumPy 2.3.5 / pandas 3.0.1 on Windows. The integrated test uses fully invented tracking, generates the full CSV and checks validation, repetition, diagnostics, fragmentation and the reset between halves. It doesn't measure the model's real quality.

In the first run, the existing P0 concurrency test failed once. Capture of stdout/stderr was added to make diagnosis easier; ten isolated repetitions and the last full run passed. The cause of the intermittent failure isn't confirmed: it isn't presented as fixed and must be watched in CI.

The earlier synthetic check was done on Windows without Docker running. Later, Alejandro ran both variants with Docker on Arch and provided the real records described above; so the diagnostics and the comparison are no longer pending. P1's GitHub Actions wasn't checked in this review. Contract, baseline and official metrics unchanged; this documentation update makes no commit or push.
