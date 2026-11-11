# Issue #34: viewer acceptance reconciliation

**11 November 2026.** Technical evidence prepared for Pablo's assigned
[issue #34](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/34). Base:
`cf04e15b6bafc40bd059a11ce44b8f2d094b6438`, branch `codex/issue-34-viewer-acceptance`, from main.
This branch does not include or depend on PR #63. This update changes documentation only.

## Outcome and remaining acceptance

The viewer implementation is already merged in [PR #46](https://github.com/GTT-TalentArena/more-than-a-hack-2027/pull/46).
Fresh Docker, playback, synthetic browser and authorised local aggregate checks pass. The local full-match
check requested by [Jimy's 29 October comment](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/34#issuecomment-6490131444)
is already documented and has now been reproduced. It is not missing implementation work.

Two explicit human acceptance requirements remain unrecorded in the checked issue/PR discussions:

- Alejandro's privacy and integration review.
- A teammate other than the author actually following the guide and recording the outcome.

PR #46 has no submitted GitHub review in the queried review list. Jimy's issue comment is useful review
evidence, but does not say he ran the guide or provide Alejandro's acceptance. A merged PR and automated
checks do not establish those actions. The [guide's synthetic sign-off procedure](../LOCAL_2D_VIEWER.md#teammate-acceptance-without-match-data)
makes the remaining review possible without restricted inputs. **The issue remains open.**

The native assignee is `PabloCordoba3`; the old issue body names `jimy-k4` as owner. A future issue update
should reconcile that discrepancy and link the evidence, while leaving human acceptance unchecked.
This local documentation change does not alter the shared issue or claim either review has happened.

## Acceptance matrix

Statuses refer to the original issue criteria, not model-quality evaluation.

| Issue criterion | Evidence | Status |
|---|---|---|
| Open/use the guide without accounts or external services | Existing host CLI; synthetic browser startup; four locally served font families; no external page requests in the exercised sessions | Technical check passed; independent guide use pending |
| Synthetic pitch, two teams, ball, transport and H/A/D/X | Existing synthetic browser suite; desktop/mobile screenshots inspected with invented inputs only | Passed |
| Known coordinates and ATD/CSV alignment, first/last frame | `tests/test_match_viewer.py` reader/coordinate fixtures; playback and browser edge-frame checks | Passed |
| Pause/seek/playback preserve frame alignment and half boundaries | Three clock tests, synthetic loading/race tests and 40 local seeks across the full timeline | Passed |
| Gaps preserve missingness; X/D/no prediction remain distinct | Python missingness/estimation checks; browser no-CSV state, observed/estimated counts and estimate toggle; ball remains observation-only | Passed technically; optional player-estimate scope still subject to integration review |
| Full-match loading/navigation, with environment/timings/limits recorded | Fresh Docker scan of 199,319 frames / 1,595 windows and local browser aggregates below | Passed |
| Automated fixtures are synthetic; verify no external transmission of real data | CI and automated regression fixtures are invented; opt-in local checks are separate, aggregate-only, without screenshots; their browser wrapper aborts nonlocal requests and observed zero attempts | Passed for the exercised paths |
| Alejandro reviews privacy/integration; another teammate tests the guide | Neither explicit sign-off is recorded in the queried issue/PR review evidence | Pending |

Player estimates are optional display-only values, with dashed markers and a toggle. Original observations,
the ball and prediction CSV are unchanged. This documented extension to the original no-interpolation MVP
still needs the named integration review; it is not silently treated as accepted scope.

## Current verification

Docker: Desktop **4.96.2**, Linux engine **29.9.2**, Python **3.11.17**, NumPy **2.4.6**, pandas **3.0.6**.
Image: `gtt-mtah:local`, ID `sha256:3f1d1d73217e38d3025e833ace299c252540d35586cda0ff568f2e9308a79182`.
Browser checks use Windows Python **3.13.7** in an isolated ignored environment, the same NumPy/pandas
versions (plus Windows' timezone dependency), Node **22.14.0**, Playwright **1.62.1**, Chrome **157.0.8103.39**.
The viewer UI runs on host loopback; Docker is for verification, not a network-exposed viewer service.

| Check | Result | Local evidence under `salidas/issue34-20261111/` |
|---|---|---|
| Viewer Python regression in Docker | 21 tests passed, 1.607 s | `viewer-tests.log` |
| Playback clock | Three tests passed | `playback-tests.log` |
| Synthetic desktop/mobile browser | H/A/D/X, missing input, no CSV, transport, stale responses, pause during loading, estimates and first/last/nonzero initial frame pass; zero external requests/errors | `synthetic-browser.log` |
| Invented full-size Docker benchmark | 199,319 frames, 46 slots, 95,362,696 input bytes; 1,594,552-byte index; 6.086 s indexing; 100 windows, 5.942 ms p50 / 8.259 ms p95 | `benchmark.log` |
| Authorised local Docker scan | 199,319 frames, 46 slots, 1,595 windows; all frame indices align; ball matches the existing reader; observations unchanged by estimates; existing CSV validates | `real-verification.json`, `real-verification.log` |
| Local desktop/mobile browser, aggregate-only | 40 seeks; tracking/CSV/inspector, label window, ball canvas, estimate toggle and playback/pause pass; zero external requests/errors | `real-browser.json`, `real-browser-ready.log` |
| Evidence/source audit in Docker | Aggregate assertions and document links pass; 34 public runtime/test files match the base; PR #63 is not an ancestor | `audit.json`, `audit.log` |

Local Docker measurements: **15.830 s** indexing and **75.177 s** scanning, including the independent
reader and display-estimate checks. Original windows: **15.071 ms p50 / 25.238 ms p95**; estimated windows:
**25.845 / 38.039 ms**. Browser seek checks: **153 ms p50 / 213 ms p95**, including automated interactions
on this machine. These are observations, not controlled comparisons with the earlier timings, a peak-memory
measurement or a universal performance guarantee. Other checks/environment setup overlapped part of the run.

The scan counts **113,488 observed ball frames** and preserves the existing CSV's SHA-256
`ab640ee8694f259697393d822b0a6665a017878b5b29d12715f59ec8a4dbc6d5`. Display-only estimates total
**12,193 player samples across 10,643 frames**, matching the earlier aggregate report. This verifies reader
consistency and rendering alignment, not the physical truth of detections, player identity or possession accuracy.
The existing candidate A CSV is an input snapshot; no model is regenerated or selected in this work.

The first local browser invocation failed at initial loading before an explicit server-readiness wait.
After waiting for `/api/meta` to report ready, the existing check passed. Both logs are retained; no viewer
runtime change was needed. The temporary local server was stopped. The earlier browser report was preserved
as `previous-browser-verification.json`; no real-match screenshot, trace, row or coordinate was exported.

## Published CI evidence

Queried GitHub checks for PR #46's head `795ebc965d2e5ebdc22c9d894a11ee15e1d7010f` and the tested main base:

| Revision | Browser CI | Docker pipeline CI |
|---|---|---|
| Published PR #46 | [Success](https://github.com/GTT-TalentArena/more-than-a-hack-2027/actions/runs/40123435548/job/120959708672) | [Success](https://github.com/GTT-TalentArena/more-than-a-hack-2027/actions/runs/40123435788/job/120959709493) |
| Main base `cf04e15` | [Success](https://github.com/GTT-TalentArena/more-than-a-hack-2027/actions/runs/42811895681/job/129815167794) | [Success](https://github.com/GTT-TalentArena/more-than-a-hack-2027/actions/runs/42811895709/job/129815167949) |

This resolves the guide's old unchecked published-PR CI item. It does not predict a later PR's CI result.

## Reproduction

Run from the repository root, using a new report directory. The existing image is sufficient when its
Dockerfile/requirements have not changed; build it first on a fresh machine. On this Windows machine use
`docker --context desktop-linux compose` if the default context is not the Linux engine.

```powershell
docker compose run --rm -T --pull never --entrypoint python evaluar -m unittest discover -s tests -p 'test_match_viewer*.py' -v
docker compose run --rm -T --pull never --entrypoint python evaluar -m tools.match_viewer.benchmark
node --test tests/match_viewer_playback.test.mjs

# Use the prepared host Python, and an installed Chrome if the pinned Chromium is not installed.
$env:VIEWER_PYTHON = (Resolve-Path .venv/Scripts/python.exe).Path
$env:VIEWER_BROWSER_CHANNEL = 'chrome'
node tests/match_viewer_browser.cjs

# Opt-in local verification: supplied data and an existing model CSV; aggregate-only output.
New-Item -ItemType Directory -Force salidas/viewer-acceptance-repeat | Out-Null
$env:DATOS = 'D:/mtah2027'
docker compose run --rm -T --pull never --entrypoint python modelo -m tools.match_viewer.verify --data-dir /datos --predictions /salidas/viewer-real/candidate_a.csv --out /salidas/viewer-acceptance-repeat/verification.json
```

For browser dependencies and the separate aggregate-only check against an already ready local session,
follow the [guide](../LOCAL_2D_VIEWER.md). `check_local_browser.cjs` currently writes its fixed ignored
`salidas/viewer-real/browser-verification.json`; preserve any earlier report before running it. Restrict
real inputs to local processing and share only aggregates. No official scoring is part of this acceptance.
