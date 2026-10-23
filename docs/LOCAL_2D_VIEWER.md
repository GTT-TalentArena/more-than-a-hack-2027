# Local 2D match viewer

Design for [issue #34](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/34).

## Design fixed before implementation

The viewer reads tactical tracking and an optional prediction CSV. It displays original observations and labels; it never changes model inference or edits a submission. A fully synthetic demo is the development and public illustration source.

Visual thesis: a dark, quiet tactics desk with an oversized pitch, warm home markers and cool away markers. Content: source and status, pitch workspace, transport controls, then a compact observation inspector. Interaction: elapsed-time playback, precise stepping and seeking, and subtle control feedback; no decorative movement of observations.

Python serves a fixed allowlist of UI assets and a read-only frame API on `127.0.0.1`. Real ATD is validated and indexed in a background thread; only requested blocks reach the browser. The browser retains a bounded cache. Files and the index are not automatically persisted. No CDN, telemetry, remote fonts or external API is required.

Constants come from `games.py`. ATD frame IDs are converted with `starter.load_atd.video_frame_of`; positions follow `solution.contract.normalized_to_metres`. Metadata layout reuses the candidate A reader behind additional strict checks, without changing candidate code. Predictions use the official submission validator. Synthetic parity tests guard adapter differences.

## Validation plan

Test invented metadata and tracking, first/last frame alignment, coordinate conversion, missing observations, finite out-of-bounds positions, malformed inputs, CSV validation, HTTP isolation and bounded block sizes. Exercise playback and seeking in a real browser with synthetic data. Run the shared suite in Docker and benchmark an invented full-length ATD. Real-match performance and teammate acceptance remain separate local checks; no real match material is opened by the development agent.

## Scope

One prediction CSV, H/A/D/X, no prediction, missing observations, two teams, play/pause, single-frame steps, timeline, frame jump and 0.25x/0.5x/1x/2x. No interpolation, trails, metrics, manual corrections, export or candidate comparison.

## Run the viewer

From the repository root, use Python 3.11 or later with the shared dependencies. Node and Docker are not required to use the UI:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r docker/requirements.lock
.\.venv\Scripts\python.exe -m tools.match_viewer --synthetic
```

Open **http://127.0.0.1:8765**. Use `--port 8768` if the port is occupied. Stop with Ctrl+C. To exercise the state without a loaded CSV:

```powershell
.\.venv\Scripts\python.exe -m tools.match_viewer --synthetic --no-predictions
```

For authorised local inputs, replace these example paths. The bundle root must contain `tactical/` with `BAR-ATH_tactical_atd.xml` and `BAR-ATH_tactical_atd.txt`. Predictions are optional:

```powershell
.\.venv\Scripts\python.exe -m tools.match_viewer --data-dir "D:\mtah2027" --predictions "D:\private-results\candidate.csv"
```

Restart the command to change inputs. Loading is asynchronous and the page reports indexing progress or a sanitised error. Real inputs are read from the configured paths, never uploaded through an external service. The API refuses other hosts and origins, serves no arbitrary files, sends no CORS permission and disables browser caching. No persistent index or browser storage is used. Changing the TXT after indexing invalidates requests and requires a restart. The initial prediction CSV is a snapshot; changing it requires a restart too.

The server deliberately binds only to loopback. Run the UI directly on the host; Docker is used for reproducible checks, not for exposing a container service on the network.

## Use and interpretation

- Play/pause with the button or Space. Step one frame with the arrows. Use the slider or enter an exact zero-based frame. Speeds: 0.25x, 0.5x, 1x and 2x. Seeking pauses playback. At the end, Play returns to frame zero; press Play again to resume. Hiding the browser tab pauses playback.
- Time is from the beginning of the tactical video, not the official match clock. `games.half_video_blocks()` identifies the halves; no axes or observations are carried across them.
- H/A/D/X are the loaded model's original labels. X is abstention, D is dead ball and no CSV means no prediction. The viewer never forward-fills labels or infers a team. A missing ball is independent of those states.
- Missing observations are hidden, including during halftime. Slots identify export tracks, not people. There are no names, shirt numbers, trails or interpolated positions.
- Finite coordinates outside the pitch are retained. A margin displays nearby observations; the inspector reports observations outside the pitch. Extremely distant observations can fall outside the viewport, without clipping their coordinates to the touchline. Invalid or partially missing coordinate pairs are rejected rather than drawn at zero.
- Scrubbing loads bounded windows and ignores stale responses from earlier seeks. Playback waits for a missing block and resets its clock at that frame; slow storage can therefore reduce playback speed. Cached playback follows elapsed time, not redraw count. The browser keeps at most four 125-frame blocks and at most two fetches (including prefetch).

## Synthetic illustration for the public log

![Animated synthetic example: two teams, ball and H/A/D/X states](assets/match-viewer-synthetic.svg)

**Every position and label above is invented.** This looping illustration is a sampled synthetic demonstration, not a recording of the real match or a performance benchmark. Missing observations disappear. Regenerate it with:

```powershell
python -m tools.match_viewer.preview
```

The illustration generator accepts no real data path. There is no real-match animation export in the UI.

## Reproduce checks

Use the existing common Docker image (or build it once). These commands use invented fixtures and committed public references, not the restricted match:

```powershell
docker compose build
docker compose run --rm --entrypoint python evaluar -m unittest discover -s tests -v
docker compose run --rm --entrypoint python evaluar -m tools.match_viewer.benchmark
node --test tests/match_viewer_playback.test.mjs
```

Browser checks optionally need Node 22+ and the pinned Playwright dev dependency. From the root:

```powershell
Push-Location tools/match_viewer
npm ci
npx playwright install chromium
Pop-Location
$env:VIEWER_PYTHON = (Resolve-Path .venv/Scripts/python.exe).Path
node tests/match_viewer_browser.cjs
```

The checks start their own synthetic servers on ports 8766 and 8767 and shut them down afterward. To use an installed Chrome instead of downloading Chromium, set `$env:VIEWER_BROWSER_CHANNEL = "chrome"`. Screenshots go only to ignored `salidas/viewer-browser/`. CI runs the browser checks and clock tests in `.github/workflows/match-viewer.yml`; the existing Docker workflow discovers the Python tests.

## Verification · 23 October 2026

- Shared Docker image: Python 3.11.17, NumPy 2.4.6, pandas 3.0.6, Linux containers on Docker Desktop engine 29.9.2. **77 shared tests pass**, including ten new viewer tests, in 50.211 s. This branch starts from `65c3c70`, before the separate P2 smoothed-restart change.
- **Three JavaScript clock tests pass**: all speeds, elapsed time, pause/resume/seek, half boundaries, last-frame clamping and exact video time.
- **Synthetic browser checks pass** on Windows, Chrome 155.0.8059.85, Playwright 1.62.1. Checked H/A/D/X, no prediction, missing ball/player, half boundaries, first/last frame, stepping, play/pause (including a delayed frame fetch), speed controls, stale seek responses and 390-pixel mobile layout. Observed **zero external requests and zero browser errors**. Desktop and mobile screenshots were visually reviewed.
- Invented full-size benchmark: **199,319 frames, 46 slots, 95,362,696 bytes**. Index: **1,594,552 bytes**, **6.017 s**. Across 100 requested windows of up to 125 frames: **5.812 ms median**, **8.098 ms p95**. Those are adapter timings on synthetic coordinates, not browser latency, real-match measurements or peak memory. The fixture is created in a temporary directory and removed afterward.

## Remaining acceptance and limits

- [ ] A team member runs loading and navigation on the authorised full match locally, records the environment, load times, responsiveness and limitations, and checks Network for external transmissions. Return only safe aggregate findings; never return observations, predictions, screenshots or match extracts to an LLM.
- [ ] Alejandro reviews privacy and integration; a different teammate follows this guide.
- [ ] GitHub CI passes on the published PR.

Until those checks are recorded, issue #34 remains open. The adapter has been checked against invented exports and the existing reader; actual export variants may need an explicit, tested adapter. There is no claim of model quality, official score improvement or real-match reconstruction accuracy. No model inference, metric or candidate configuration is changed.
