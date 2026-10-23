# Control and temporal continuity · independent experiment

> 🇪🇸 Translated from the Spanish original, [CONTROL_TEMPORAL.md](CONTROL_TEMPORAL.md).

Hypothesis fixed before running on the match: requiring unambiguous proximity and movement compatible with control, and penalising state changes, will reduce the fragmentation of P2's nearest-player consumer. Beating smooth50 isn't guaranteed and candidates A/B aren't modified.

## Initial rules and parameters

- Read the local ATD and Smart Tagging; don't consume GT in the generator. Use the metres, masks and indices of contract v1.
- Candidate control: a player of a known team at <= 2 m, a distance advantage >= 0.75 m over the other team and an observed ball speed <= 8 m/s. Both teams must have a valid distance. These are provisional physical thresholds, not calibrated.
- Confirm a run of at least five consecutive observations of the same team. Date the evidence at the start of the run, without delaying it to the confirmation. A gap or change of half breaks the confirmation. Don't derive speed between observations separated by gaps.
- H/A evidence: 1 for the confirmed team and 0 for the other. Without confirmed control, both emissions are neutral: D isn't invented because the ball is missing.
- Offline three-state H/A/D Viterbi, cost 8 per change and no minimum possession duration. Short runs with enough evidence can survive. On H/A ties, place the change as late as possible, keeping the last team through a gap.
- P2 keeps its parameters. D gets +2 per frame with P2 evidence >= 0.75; -2 when there is explicit evidence of live movement; otherwise -0.05, a weak prior against stoppages without evidence. A confirmed P2 restart forbids D on that frame. The values are scores, not probabilities.
- Reset per half; outside the blocks, X. Without team evidence yet in the half, abstain unless P2 justifies D.

The P2 detector isn't changed yet: first the effect of the consumer is isolated. The coverage of the second kick-off doesn't show that its exact boundary is correct; refining it requires a local review that doesn't expose match material.

## Validation fixed before the results

Synthetic tests: decoding against exhaustive search, absence and quick passes, confirmation and backdating, a sustained short possession, ties in gaps, a real stoppage between possessions of the same team, an explicit restart, independent halves, invalid masks and parameters, and the full circuit with a 199,319-row CSV.

Docker comparison once per configuration, with repetition and bootstrap 1000: temporal consumer with P2 off and on. Record control coverage, changes, D/X, spellF1, macroF1, fragmentation, hashes and environment. Compared with the previous P2 consumer, control and decoding change at the same time: that comparison evaluates the whole, it doesn't attribute causality to a single piece. Don't sweep parameters or choose them with the public window.

Design references: `docs/ESTUDIO_POSESION.md` (English: [`ESTUDIO_POSESION.en.md`](../ESTUDIO_POSESION.en.md)), sections 3.2 and 4.5; [Vidal-Codina et al.](https://arxiv.org/abs/2202.00804). It is an experimental implementation of our own rules, not a reproduction of the paper or the agreed integration of #15/#16.

## Reproduction

From the root, with the common image already built:

```powershell
$env:DATOS = "C:/Users/pablo/Documents/dataTA/organized"
docker compose run --rm --pull never --entrypoint python evaluar -m unittest discover -s tests -v
docker compose run --rm --pull never modelo modelo --config configs/temporal_control_no_p2.json --repetir
docker compose run --rm --pull never modelo modelo --config configs/temporal_control.json --repetir
docker compose run --rm --pull never --entrypoint python evaluar scripts/summarize_p2.py --model temporal_control --out /salidas/temporal-comparison.json
```

The summary's destination must not exist: results aren't overwritten. The exporter checks equality of sources, configuration except `p2_enabled`, tracking, environment and evaluation. It only exports permitted aggregate metrics and diagnostics. The original data is still in `dataTA`; `data/` wasn't used, it only contains its README.

## Docker result · 22 October 2026

**67 tests pass in 43.809 s.** They include twelve tests of the temporal model, a comparison with exhaustive search and a full generation/repetition/validation on invented tracking. The existing P0/P1/P2 tests and five tests of the aggregate exporter also pass.

Two full runs with local data, earlier parameters unchanged and bootstrap 1000. Both generate 199,319 valid rows, end with code 0 and repeat the same SHA-256. The P2 variant was interrupted at the user's request and resumed with the same configuration; only its completed run is used. There were no sweeps or adjustments using the public score.

| Variant | Public spellF1 | Public macroF1 | Public possessions | Fragmentation |
|---|---|---|---|---|
| Previous P2 consumer | 0.046575 | 0.505944 | 129 | 6.238095 |
| Temporal without P2 | 0.351515 | 0.503413 | 16 | 0.761905 |
| Temporal with P2 | 0.375758 | 0.549703 | 16 | 0.809524 |
| official smooth50 | 0.325581 | 0.620733 | 26 | 1.428571 |

The public reference has 17 possessions. The new consumer reduces fragmentation compared with the previous one, but a similar count doesn't show that the boundaries are correct. The spellF1 increase over smooth50 is 0.050176; macroF1 is still lower by 0.071030. The 5–95% bootstrap interval of spellF1 is [0.230303; 0.521212] with P2 and [0.218182; 0.496970] without P2; they also overlap with smooth50's. No generalisable superiority or improvement on the private test is claimed.

The controlled on/off comparison keeps the same consumer: P2 adds +0.024242 spellF1 and +0.046291 macroF1 on this sample, with slightly higher fragmentation. The comparison with the previous consumer changes control and decoding simultaneously; it doesn't attribute that gain to P2 alone. The live/dead metrics are 0.879637 with P2 vs 0.903313 for the previous consumer: the best temporal result doesn't improve every dimension.

On the full blocks, without the private GT, the model with P2 produces **241 possessions**, median 14.32 s, five under 1 s and 10.046% of frames D. These are statistics of the predictions, not measures of accuracy. Confirmed control covers 24.512% of the frames in those blocks; the rest depends on temporal continuity and P2. Long gaps can drag a wrong team or miss real recoveries. Without P2 there are 209 possessions and no D; that variant is an ablation, not a complete solution.

## Provenance and limits of the delivery

Environment: Docker Desktop 4.96.2 / WSL 3.0.3, Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6. Base commit `d0916ffc803ae2f64fb3a8e813bbb8d170d7bf65`, with model changes still uncommitted. Both records keep equal hashes of sources and common inputs; the exporter has checked them. This isn't yet the same as reproducing from a new published commit. The earlier P2 validation used a clean LF copy; this experiment uses the Windows checkout mounted in Linux. No byte equality between both checkouts is claimed.

| Variant | Run ID | Candidate SHA-256 |
|---|---|---|
| Without P2 | `20261022T164032.446705Z-822120a376a2-modelo` | `9a4272f598f443960dc4a7f17a456b471a7e21ed11eee8178ee54e8a0707bd3a` |
| With P2 | `20261022T164325.144461Z-384cce3c3433-modelo` | `baf41868594358edcd3258093dac4f61f52f19bf9eb4488864a4cd8fd74dfc7b` |

Ignored local evidence: `salidas/temporal-comparison-docker-final.json`, `salidas/temporal-full-match-summary.json` and `salidas/temporal-control-tests-final.log`. The full records and predictions stay local. The pipeline times (67.9 s and 66.6 s) include repetition and evaluation; they aren't inference benchmarks and don't justify comparing speed between variants.

Decision: keep the new implementation as a reproducible experiment and take it to review; don't automatically replace the team's official solution or close #15/#16. P2 keeps its detector and the uncertainty of the second kick-off. Before adopting it: a local review of boundaries and short possessions, external validation without tuning on this window and review by another team member. The evidence in this section was obtained before the delivery commit; the team log hasn't been published.
