# P2 · Stoppages and restarts (#14)

> 🇪🇸 Translated from the Spanish original, [P2_DEAD_BALL.md](P2_DEAD_BALL.md).

Hypothesis before running: combining observed exits from the pitch with preparation and movement within the restart context can recover real stoppages without turning occlusions into D. No spellF1 improvement is assumed.

## Interface and scope

`solution.dead_ball.detect()` receives geometry in metres, masks, periods and events from the official loader; it returns `dead_score`, `restart_score`, `dead_valid`, `restart_valid` and local candidates. Arrays of length N; absence = NaN and a false mask. The scores are evidence, not probabilities. It consumes neither GT nor player identities.

Contract v1 is kept: ATD `frame_id - 1`; events `round(seconds * fps)`; half-open intervals; dimensions and blocks from `games.py`. Overlaps of the same type are combined by max. Contradictory teams are kept in the events, without deciding H/A. N/A stays unknown. General H/A tactical context belongs to #20.

## Initial rules, fixed before results

- Exit: three consecutive observations more than 0.5 m outside the rectangle; the start is dated at the first one. Coordinates aren't clipped.
- Movement: speeds derived only between consecutive original observations in the same half; jumps above 45 m/s are discarded. A restart requires three frames of movement at at least 2 m/s.
- General preparation: at least five consecutive frames of the ball at no more than 0.5 m/s, in a zone compatible with the type of restart and inside its automatic window. Sustained movement is then looked for; the whole interval isn't copied as D. The first kick-off has the specific rule below.
- Initial zones: corner at <= 5 m from both lines; throw-in at <= 3 m from the touchline; goal kick at <= 18 m from a goal line; free kick with no zone imposed. They are geometric approximations, not regulatory validations of the exact restart position.
- A throw-in accepts re-entry from outside with sustained movement. A ball that reappears after a gap provides no speed during the gap.
- The first kick-off event of each half provides D context up to the start of its window. Sustained movement starting near the centre (3 m radius) is looked for, without requiring prior stillness. If it is confirmed, D extends up to that restart; if not, the inside of the window stays uncertain. The published kick-off numbers are only used for diagnostics, not to generate labels.
- Collective stillness (median speed <= 1.5 m/s, at least six observed slots) reinforces preparation; it never generates D by itself. Trajectories aren't derived by slot identity.
- A confirmed exit can hold stoppage evidence until re-entry with movement or a confirmed contextual restart, for at most 90 s; when the horizon runs out, it goes back to unknown. It isn't claimed that an absence is D: the evidence comes from the previous exit.
- The 90 s limit affects exits without a paired contextual boundary. A preparation with a confirmed restart has its own observed end; the initial stretch before the kick-off can exceed that horizon.
- Without enough evidence, no decision is forced. The context is reset between halves.

## Experimental integration

### Smoothed-track correction · 23 October 2026

The general preparation rule now searches for sustained motion within a bounded delay after stillness,
instead of requiring an immediate jump from <= 0.5 to >= 2 m/s. `restart_search_s=1.0` is the default;
zero restores the previous rule. The search cannot bridge missing or implausible speed evidence, an event
boundary or a half boundary. The restart is dated at the first confirmed moving frame, not the end of
stillness or the final confirmation frame. All other physical thresholds are unchanged.

Both `baseline_dead_ball` configurations include the new required parameter. The initial kick-off rule
is separate and unchanged. Candidate A remains P2-disabled by default. Regression tests, smoothed synthetic
comparisons and local aggregate validation are documented in [P2_SMOOTHED_RESTARTS.md](P2_SMOOTHED_RESTARTS.md).

Internal model `baseline_dead_ball`: the same nearest-team and hold from P1 in both variants; only `enabled` changes. D integration threshold = 0.75; confirmed restarts cut the D holding. It is a provisional consumer of the signals, not the Viterbi implementation of #16. The final integration requires review by Jimy/Alejandro and doesn't alter the frozen A/B candidates.

## Planned validation

Synthetic tests of indices, absence, preparation, movement, overlaps, out of bounds, reset between halves and boundaries. Then official references and an on/off comparison with repetition in Docker. One public comparison per variant, without a parameter sweep. Metrics, coverage, candidates, conflicts, configuration, hashes and limitations will be recorded. Review football errors locally without publishing intervals or match material. Human review/external CI pending until there is evidence.

## Reproduction

From the repo root, with Python and the dependencies from `docker/requirements.lock` installed:

```powershell
.\scripts\prepare_data.ps1 -Source "D:\pcordoba\Documents\dataTA" -Destination "D:\pcordoba\Documents\dataTA\organized"
.\scripts\verify_p2.ps1 -DataDir "D:\pcordoba\Documents\dataTA\organized" -Python ".\.venv\Scripts\python.exe"
```

The preparation checks duplicates by SHA-256, doesn't overwrite different files and creates hard links to videos on the same drive; it doesn't duplicate their contents. It needs write permission on the destination. The signals only consume tracking and Smart Tagging, not video or homography. Don't open the assets with a cloud LLM.

Aggregate diagnostics, without scoring:

```powershell
python -m solution.dead_ball --data-dir "D:\pcordoba\Documents\dataTA\organized" --out salidas/p2-diagnostic.json
```

Docker, once its engine and the common image described in `docs/DOCKER.md` are available:

```powershell
.\scripts\verify_p2.ps1 -DataDir "D:\pcordoba\Documents\dataTA\organized" -Docker
```

The Docker script requires the local image `gtt-mtah:local` to exist and uses `--pull never`, a read-only data mount and the same pipeline. `docker compose run` doesn't accept `--no-build`; the image is checked first and `--build` isn't requested. It doesn't run backend builds. The byte-for-byte baseline check can detect line-ending differences between a Windows and a Linux checkout: don't edit the reference or present that code 4 as a success; diagnose it separately.

Each variant generates, validates and repeats its CSV before evaluating it; the controlled summary checks configuration, code, environment and the hashes of common inputs. The outputs and full reports stay ignored under `salidas/`. The P2 records include hashes of the model's sources, plus the commit and the tree status; a run with pending changes isn't equivalent to a reproduction from a published commit.

On this machine, `.venv` was created with Python 3.12.14 and access to the dependencies already available in the local runtime (NumPy 2.3.5 and pandas 3.0.1). It isn't presented as the pinned Docker environment, which is still pending. The team's locked dependencies weren't changed.

## Limits of the first version

It doesn't directly detect whistles, fouls or substitutions. A false event, ball placement movement or shifted tracking can cause wrong boundaries. 2D geometry doesn't determine whether the whole ball crossed a line, nor does it distinguish height. Collective speeds aggregate observed slots, with possible duplicates; they don't represent stable identities. Without enough observed movement, the kick-off may stay unrefined; the other restarts also require preparation. There is no guarantee of recovering every stoppage or of improving the private test.

## Earlier state of Docker

In the previous session, on 22 October 2026, Docker Desktop 4.11.1 ended with `Access denied`; the `docker-users` group was empty. Compose validated statically, but the engine wasn't available. Work continued in Python and Docker was left pending. That result wasn't a container validation. The installation and verification on the current PC are recorded below.

## Acceptance correction before the final version

The first comparison reproduces both CSVs and verifies the inputs, but the specific check of the second kick-off fails: 0 kick-offs refined and only 17.21% of the preceding stretch marked D. It is corrected by this functional criterion, not to maximise the public score. The physical thresholds stay the same.

Revised rule: the first `Kick Off (Start)` event of each half provides D context from the start of the block to the start of its window. Inside that window, sustained movement starting next to the centre is looked for, without requiring prior consecutive stillness. If it is confirmed, the boundary is dated at the first movement of that sequence; if not, the inside of the window stays uncertain. The whole window isn't labelled D, and the published frames aren't fed into the generation. The automatic label can be offset or false: that limitation is kept.

The initial comparison remains as evidence of a coverage failure: spellF1 0.04414 → 0.04658, macroF1 0.46039 → 0.50611. Fragmentation gets worse, from 6.0952 to 6.1905. It isn't adopted on those figures; both variants are still far from smooth50 (0.32558 public). The controlled comparison will be repeated after the correction, without parameter sweeps.

## Verification and final result · 22 October 2026

**53 tests pass** in 101.145 s, without match fixtures. They include the contract, P0/P1, P2, synthetic generation of 199,319 rows, restarts, the second half, duplicated events and rejection of comparisons with different code/data/parameters. `git diff --check` and `docker compose config --quiet` with the real data path pass.

Data: 13 ZIP entries checked; seven unique assets extracted and two videos linked under `dataTA/organized`. Repeating the preparation creates zero files. The four official baselines were regenerated with real tracking, match byte for byte the ones published in this checkout and give the same hashes in two runs. The public evaluation of the references ends with code 0.

Final comparison in local Python, `public-5min`, bootstrap 1000, same base commit `88f4724`, tree with own pending changes, same hashes of code, environment and common inputs. Only `enabled` changes; P2 on adds Smart Tagging to its manifest. The automatic checker verifies these conditions. It isn't a comparison with Viterbi or with an A/B candidate.

| Variant | spellF1 | macroF1 | alive_dead_f1 | Possessions | Mean duration (s) | Fragmentation | Public X |
|---|---|---|---|---|---|---|---|
| P2 off, P1 hold 25 | 0.0441379310 | 0.4603944218 | 0.8964002823 | 128 | 2.34375 | 6.0952380952 | 780 |
| P2 on | 0.0465753425 | 0.5059441824 | 0.9033125148 | 129 | 2.29333 | 6.2380952381 | 778 |
| official smooth50, public reference | 0.3255813953 | 0.6207331924 | — | 26 | 10.8031 | 1.4285714286 | 0 |

`alive_dead_f1` uses live play as the positive class. The CSVs of both variants validate and reproduce byte for byte; both runs end with code 0. The hashes and run IDs identify local results, not a new published commit:

| Variant | Run ID | Candidate SHA-256 |
|---|---|---|
| Off | `20261022T121354.904987Z-8e806a17987b-modelo` | `a0597187862e3a23ae9bf9d5534ca788271193a55fa95b1520b368fd661a6b18` |
| On | `20261022T121550.600410Z-f8facff86c9d-modelo` | `83d82503bb861edff3f61f92070a1615b70f703f69d0849f3994d51482f93e7e` |

Local aggregate evidence: `salidas/p2-comparison-final.json`; tests: `salidas/p2-tests-acceptance.log`. Don't publish the full reports or the CSVs. The comparison exporter only copies permitted aggregate fields.

With P2, 66 stoppage candidates and 54 restart candidate frames are generated; there are three frames with simultaneous D/restart evidence. The experimental consumer gives priority to the restart and clears the held D. One of the two kick-offs is refined. The D coverage of the published stretch before the second kick-off goes from 0% without the detector to **97.1029%**; that isn't the same as getting its exact boundary right or covering the whole stretch. That restart is still unrefined and needs a local football review. On the full match, 16,021 D frames are emitted, against zero in P1; we don't know their quality without the private GT.

**Decision: mixed result, keep it as an experimental component.** The public spellF1 improvement is small and fragmentation gets worse; no generalisable improvement is claimed and smooth50 isn't replaced. P2's goal is to provide stoppage signals; this consumer's nearest-player still fragments and doesn't implement the control of #15 or the decoder of #16.

The pending Docker validation was completed on the current PC, as detailed below. Pending for acceptance/closing of #14: a local visual review of false cuts and missed restarts, especially the second kick-off; an interface review with Jimy/Alejandro/Nico, integration with the final consumer of #16 and CI/review by another team member. The proposed log entry hasn't been published. Don't close the issue just because of the tests or the public table.

## Docker verification on the current PC · 22 October 2026

Installed Docker Desktop 4.96.2, engine 29.9.2, Compose 5.6.1 and WSL 3.0.3. VirtualMachinePlatform was enabled and, after the user restarted, the Linux containers started. The common image was built with Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6. Local data prepared under `C:/Users/pablo/Documents/dataTA/organized`; seven assets checked and two videos linked, without duplicating them. A second preparation creates zero files. The preparer was fixed to skip the README included in the official ZIP; it still rejects other unexpected entries.

The model from commit `d0916ffc803ae2f64fb3a8e813bbb8d170d7bf65` was reproduced in a clean local copy with LF line endings, under `salidas/docker-linux-source`. The working checkout has CRLF public CSVs: their references weren't modified. The four runs record the same commit, a clean tree and code 0. The changes to the reproduction scripts are pending commit in the working checkout; they don't alter the evaluated model.

- 53 tests pass in Docker, in 33.919 s.
- Four baselines regenerated twice: same hashes between repetitions and a byte-for-byte match with those published in Git.
- P2 on/off: valid, deterministic full CSVs and a verified controlled comparison, with bootstrap 1000.
- Same aggregate metrics as in the earlier Python comparison: spellF1 0.0441379310 → 0.0465753425; macroF1 0.4603944218 → 0.5059441824; fragmentation 6.0952380952 → 6.2380952381. The mixed-result decision stands.

| Variant | Docker run ID | SHA-256 of the CSV with LF line endings |
|---|---|---|
| Off | `20261022T163100.705541Z-0aed82a57f4c-modelo` | `fc128f4f8b0abd118ec2d472e70086419d97703a5aa281f6a7c16b09b1fb0d69` |
| On | `20261022T163142.231226Z-18683bc739e9-modelo` | `7d5374a4019646b4e432c0f5d910e5bb5296088e01774e4b64c68a50966af665` |

Local aggregate evidence: `salidas/p2-comparison-docker-20261022T163142.json` and `salidas/docker-p2-acceptance-20261022.json`. The full records stay in the ignored folder of the local copy. The earlier Windows hashes and the Docker ones differ because of line endings; no byte equality across platforms is claimed.

## Proposed public log (EN)

P2 investigates dead-ball and restart evidence from observed pitch exits and set-piece context. Missing ball observations do not trigger stoppages. Tagged phases only define search windows; motion refines restart boundaries. We will test synthetic transitions and compare the same P1 consumer with P2 enabled and disabled. Thresholds are fixed before public evaluation. Full-match data and frame-level outputs stay local. This is a draft for the team log; it has not been published.
