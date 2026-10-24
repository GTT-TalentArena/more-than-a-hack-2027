# P2: bounded restart search for smoothed ball tracks

## Hypothesis and scope, fixed before running

Jimy's [issue #14 report](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/14#issuecomment-6347255554)
identifies a blind spot: the current rule requires three moving frames immediately after a still-ball run.
Smoothing produces intermediate speeds, so valid preparations can fail this adjacency requirement.

Add `restart_search_s=1.0`, following the reported smoothing scale rather than a public-score search. A value of
zero reproduces the original immediate-motion rule. Keep all existing speed, stillness, zone and confidence
thresholds. Search for the first sustained-motion start no later than `round(restart_search_s * fps)` frames
after stillness ends. Include the last permitted start, but require all confirming frames to fit inside the
half-open event and the same half. Stop at missing or implausible speed evidence: do not connect a preparation
to motion across a tracking gap. Date the restart at the first moving frame, not the last still frame or the
last confirming frame. Only the interval up to that restart provides dead-ball evidence.

This changes the general preparation rule only. The initial kick-off uses a separate centre-and-motion rule;
its unresolved second-half boundary is not automatically fixed by this change. Do not alter candidate A's
adapter or enable P2 by default there.

## Validation plan

- Reproduce the missed gradual-acceleration case in a synthetic regression test before changing the detector.
- Test the inclusive wait limit, one frame beyond it, event-end exclusivity, half boundaries, missing ball,
  rejected speed jumps, unsupported movement spikes, normal immediate motion and each set-piece zone.
- Test a centred 25-frame smoothing filter (`smooth_half=12`) on invented restart trajectories.
- Run the full shared test suite and candidate A's synthetic adapter tests in Docker.
- Compare the old (`restart_search_s=0`) and new rule on the same smoothed synthetic bundles. Report preparation
  coverage and restart errors as well as candidate A's synthetic metrics; more detections alone are not proof
  of a better model.
- With the local authorised bundle, run aggregate diagnostics and deterministic generation/CSV validation.
  Do not inspect or print match rows, candidate intervals or video. Do not tune on, or spend further evaluations
  of, the five-minute public ground truth for this regression fix.

No adoption or score improvement is assumed.

## Reproduction in the shared Docker image

The output paths below must be new. Match rows and generated predictions remain in git-ignored `salidas/`.

```powershell
docker compose build evaluar
docker compose run --rm --pull never --entrypoint python evaluar -m unittest discover -s tests -v
docker compose run --rm --pull never --entrypoint python evaluar -m solution.a_opus.tests --full

foreach ($seed in 0..4) {
    docker compose run --rm --pull never --entrypoint python evaluar -m solution.a_opus.synth --out-dir "/salidas/p2-smoothed-synthetic/seed-$seed" --seed $seed --ball-style real --smooth-half 12
}
$bundles = 0..4 | ForEach-Object { "/salidas/p2-smoothed-synthetic/seed-$_" }
docker compose run --rm --pull never --entrypoint python evaluar scripts/compare_p2_restart_search.py @bundles --synthetic --candidate-a --out /salidas/p2-smoothed-synthetic/report.json

$env:DATOS = "C:/Users/pablo/Documents/dataTA/organized"
docker compose run --rm --pull never --entrypoint python modelo scripts/compare_p2_restart_search.py /datos --check-consumers --out /salidas/p2-smoothed-real/report.json
```

The comparison script reports immediate (`restart_search_s=0`) and bounded (`1.0`) candidate counts.
`--check-consumers` generates both P1 and temporal outputs twice per rule, validates all eight CSV files and
checks their SHA-256 equality within each repetition pair. It reads no ground truth. `--candidate-a` requires
the explicit `--synthetic` flag and reads only the generated `synthetic_gt.csv` in each synthetic bundle.
Synthetic restart-error and false-short-possession definitions are the same as Jimy's `compare_p2.py`.
The five seeds here all use `smooth_half=12`; they are not claimed to be Jimy's exact five-match mixture.

## Regression and local-match results · 23 October 2026

The gradual-acceleration test was run before the detector change and failed with zero preparations instead
of one. After the change all ten new regression tests pass, including a centred 25-frame smoothing filter.
The shared Docker suite passes **77 tests in 63.472 s**. Candidate A's **11 synthetic checks**, including its
P2 adapter and complete synthetic pipeline, also pass (end-to-end synthetic spellF1 0.824).

On the authorised local bundle, without reading ground truth or scoring the public window:

| Aggregate detector output | Immediate search | Bounded search |
|---|---:|---:|
| Smart Tagging set-piece windows | 59 | 59 |
| General preparation candidates | 0 | 17 |
| Candidates using a positive wait | 0 | 17 |
| Observed-exit candidates | 64 | 64 |
| Initial-kick-off contexts | 2 | 2 |
| Initial kick-offs with a confirmed restart | 1 | 1 |

Seventeen preparations are candidates, not seventeen verified correct restarts or a recall estimate. The
initial-kick-off rule is unchanged, so this fix does not resolve its outstanding second-half boundary.

Both P1 and temporal consumers were run twice per rule. All eight generated CSV files have 199,319 valid
rows and identical SHA-256 within each repetition pair. The legacy setting also reproduces the previously
validated LF CSV hashes: P1 `7d5374a4019646b4e432c0f5d910e5bb5296088e01774e4b64c68a50966af665` and temporal
`baf41868594358edcd3258093dac4f61f52f19bf9eb4488864a4cd8fd74dfc7b`. New-rule hashes are
`cfd52a9a3f340103e5b8c11c1df643c3034d0262994284f970bd7635bbba4fef` (P1) and
`ecc8858a183d1355defd48eed15b89c4cac1e0b460bd2a7bb57f310d8f8630c8` (temporal).

These runs validate generation and reproducibility, not full-match prediction quality. P1 emits 16,462 D
frames (16,021 before); the temporal consumer emits 16,391 (15,959 before). More D frames are not necessarily
better. The detector's source hash and ATD/Smart Tagging hashes are recorded in the local aggregate report.
The working base is `65c3c70`; these evaluations preceded the delivery commit.

Local evidence, all ignored by Git: `salidas/p2-smoothed-regression-before.log`,
`salidas/p2-smoothed-regression-after.log`, `salidas/p2-smoothed-tests.log`,
`salidas/p2-smoothed-candidate-a-tests.log` and `salidas/p2-smoothed-real/report.json`.

## Five smoothed synthetic matches

Seeds 0–4 were generated independently with `--ball-style real --smooth-half 12`, then evaluated on the same
three candidate A profiles. No public or private match GT was read. Across 445 synthetic set-piece windows,
the old rule produces **4 general preparation candidates**, while the bounded rule produces **269**, 268 of
which use a positive wait. Initial-kick-off and observed-exit candidate counts are unchanged within each match.

| Candidate A profile | Mean spellF1 | Mean macroF1 | False possessions under 2 s | Restart error p50 / p90, frames |
|---|---:|---:|---:|---:|
| P2 off | 0.788565 | 0.924313 | 26 | 7 / 82 |
| P2 on, immediate rule | 0.788565 | 0.924291 | 26 | 7 / 82 |
| P2 on, bounded rule | 0.787980 | 0.922931 | 26 | 10 / 81.1 |

Each profile misses 10 synthetic restarts under the existing comparison's reach definition. Means are across
the five matches; error percentiles are pooled. More preparations do not improve A here: spellF1 drops by
about 0.000585 from the immediate rule, and median restart error increases by three frames. This is consistent
with Jimy's warning that A already has its own restart evidence. It does not justify enabling P2 in A.

**Decision:** the regression fix restores preparation detection on gradually accelerating/smoothed tracks,
with bounded search and compatibility at zero wait. Keep the fix available to P1 and temporal consumers,
but do not claim improved real-match accuracy or change candidate A's P2-disabled default. Review candidate
boundaries locally before adoption; the second-half kick-off remains a separate unresolved case. No
thresholds were adjusted after viewing these results, and no further public-window evaluation was consumed.

Synthetic aggregate evidence is `salidas/p2-smoothed-synthetic/report.json`; console output is preserved in
`salidas/p2-smoothed-synthetic.log`. Only aggregate statistics, source/input hashes and synthetic per-match
metrics are exported. Full prediction files stay local and ignored.
