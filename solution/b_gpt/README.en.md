# b_gpt

> 🇪🇸 English translation of [README.md](README.md). The Spanish original is kept unchanged.

Deterministic CPU candidate: geometric control evidence, dead-ball cues,
weak Smart Tagging and Viterbi at 25 fps. It is not an LLM and does not call external
services. This first version keeps the algorithm and every parameter of
`control_v1`; it changes the packaging and adds aggregate diagnostics without ground truth.
Later versions are recorded as commits on **`cand/b-gpt`**, not as
new folders. It is not published to `main` or the website.

## Variant v1: v0 + Claude's improvement

This branch (`cand/b-gpt-claude`) starts from v0 frozen in the tag **`b-gpt-v0`** (Codex
only, ChatGPT-6 Astra high) and adds changes v1, v2, v3 and v4, written by Claude Code
(Claude Opus 5.5, effort medium) with Alejandro's approval as judge. Its own
record is in `prompts/confrontacion/b-gpt-claude/`.

**Ball lost after leaving the pitch = stoppage.** A ball that has gone out cannot come back
into play without a restart (Laws 9 and 15–17). v0 only detected the ball going out while it *saw*
the ball outside; if the tracking lost it right afterwards —the usual case when it leaves the frame—
and the players kept moving, as in a throw-in or a goal kick, it kept the
possession. Now, if the ball was clearly seen out (persistently, as in v0, or
more than `clear_out_m` = 1 m past the line) and then disappears, the whole gap counts
as stoppage evidence with the same weight as a ball seen out, and players
running do not count against it. The gap ends when the ball is located again and
never lasts longer than `stop_lookback_s` (45 s). The rest of the method and the parameters are
identical to v0.

Reason: Smart Tagging only annotates part of the restarts, so many stoppages
(unannotated throw-ins and goal kicks) can only be detected with the tracking. Nothing has
been chosen with the public window. `evidence_totals.out_of_play_gap_frames` reports in the
`.summary.json` how many frames the change affects.

**v2 · Long gaps without the ball = stoppage.** Full-match diagnostics without GT
(`evidence_totals.dead_time_diagnostics`, Edu's run) show that in this tracking the
ball is almost never missing for a short time (< 0.2 min of gaps under 5 s in the whole match),
but it is missing in **132 stretches of ≥ 5 s adding up to ~43 min**: a number similar to the stoppages of
a match and a duration that, added to the `D` already detected outside them, gives ≈ 47 % `D`,
in line with LaLiga's effective playing time. Vidal-Codina et al. (2022) describe providers
that mark the dead ball by leaving it without data. v1 labelled 12.6 min of those
stretches as live. Now, with the players tracked (≥ 8), a stretch without the ball of **≥ `long_gap_s` = 10 s**
is strong stoppage evidence and one of **≥ `medium_gap_s` = 5 s**, moderate; players
running do not count against it. If ball and players are missing at the same time it is a data cut, not
a stoppage. The thresholds come from the duration of a restart (quick throw-in 5–10 s;
free kicks, goal kicks and corners, more than 10 s), not from any score.

**v3 · Only the gaps that start or end like a restart.** On the public window v2
raised `D` recall (0.26 → 0.41) but lowered its precision (≈ 1.0 → 0.59): not every long gap
is a stoppage. A player with their back to the camera shielding or dribbling the ball, or a ball
lost in the air, also make it disappear with play live. v3 replaces v2's
rule: a gap of ≥ 5 s (with players tracked) is only stoppage evidence if the ball **was lost
next to a line** (≤ `clear_out_m`), **reappears still** (< 0.65 m/s, as in v0: placed
for a free kick, a goal kick or a kick-off), **reappears next to a line** (throw-in,
corner) or the gap lasts **more than `very_long_gap_s` = 30 s**. If it reappears moving inside the
pitch, it is treated as live play, as in v1. The idea came after seeing the breakdown of
public evaluation #3 (deviation declared in the record).

**v4 · A touch is not a change of possession** (Claude, effort max). The full-match diagnostics without GT
showed 70 "back-and-forths" of less than 3 s (1.8 s on average): team B
"has" the ball for an instant between two stretches of team A, and they add up to 58 % of the H↔A changes.
`CHALLENGE.md` says that a touch without control, a deflection or a duel without control afterwards are not
a change of possession, and suggests as a control signal that a player retains the ball for a few
seconds. Now an opponent stretch of **less than `min_change_s` = 3 s** between two stretches of the same
team, **with no stoppage in between**, goes back to the team that had the ball; the shortest first,
so a chain of flickers merges with the surrounding team. Stretches next to a stoppage are not
touched. No `D` changes. Analysis and decision in
`prompts/confrontacion/b-gpt-claude/analisis-v4.md` ([English](../../prompts/confrontacion/b-gpt-claude/analisis-v4.en.md)).

Command for this variant (does not overwrite v0's CSV):

```bash
python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv
```

## Running locally

From the root of `more-than-a-hack-2027`, with Python 3.11–3.14:

```bash
python -m pip install -r solution/b_gpt/requirements.txt
export MTAH_DATA_DIR="$HOME/mtah2027"
python -m solution.b_gpt --out evaluation/results/b_gpt.csv
```

Installing the dependencies in a virtual environment is recommended. All direct
and transitive dependencies are pinned. Only the installation needs the network; inference
uses the CPU, with no GPU, downloads, training or external calls.

The inference command is run **only by the participant, locally**. An LLM
agent must not open the data or the match CSVs, or run this command on them.
The development and testing of this delivery used only documentation,
public code and synthetic data. `~/mtah2027` was not accessed.

The match inputs come from `games.asset_paths(source="tactical")`, which
respects `MTAH_DATA_DIR`; `--data-dir` sets another local root. ATD,
metadata and Smart Tagging are read. Homography, video, broadcast and GT are not read.

The comparator is `evaluation/results/baseline_smooth50.csv`, by its location in the
repository. It is a prediction, not an `asset_paths` asset. Another
CSV of that baseline can be given with `--baseline /path/baseline_smooth50.csv`. If it is missing or does not
meet the contract, the command fails with a sanitised error; it does not silently replace
the baseline or skip the comparison.

Outputs:

- The given CSV: `frame,label`, **199,319 data rows**, indices `0…199318` and
  labels `H/A/D/X`. It is validated with the official function after being written.
- A file with the same name and the `.summary.json` extension: parameters, versions,
  code fingerprint, time, memory, aggregate evidence and diagnostics of **both** CSVs.
- A single JSON line on stdout: number of possessions, mean and median duration,
  `D` percentage and `X` percentage, within the published halves.

There are no rows, coordinates, time series or individual events in the diagnostics
or on stdout. Errors leave out input values and local variables. The per-frame
CSV is the local deliverable; it must not be shared with an LLM. To validate it separately:

```bash
python evaluation/validate_submission.py evaluation/results/b_gpt.csv
```

The CSV is byte-for-byte deterministic with the same inputs, code and dependencies.
The JSON contains run time and memory, which may vary; these fields do not
take part in the labels or the CSV hash.

## Method and reasons for the parameters

The reader checks each frame ID and the number of slots, applies `frame_id - 1` and
converts normalised coordinates to metres. Slots only give team
membership: they are not player identities. Each half is processed separately according to
`games.half_video_blocks`; outside them `X` is written.

**Control.** The shortest distance to the ball is computed for each team. The evidence
depends on the absolute proximity, the difference from the opponent, the ball's
speed and the reliability of the observation. A closer opponent who is several
metres from a ball in the air does not automatically become the owner. A missing
ball gives zero control evidence and is not the same as `D`.

**Stoppages.** Ball out of the pitch, still ball with collective stillness,
and missing ball with prolonged collective stillness are combined. A ball moving inside the
pitch and active players give evidence against. The automatic phases are
weak cues: the defensive ones favour the opponent, `N/A` does not become a
team and overlaps are combined by maximum, not by adding correlated observations.

**Restarts.** `SET PIECES` intervals bound a search for the start of movement.
If there is evidence, the stretch compatible with a stoppage is searched backwards. The first
`Kick Off (Start)` makes it possible to detect the stretch before each half's kick-off, without hand-writing
any kick-off frame. A restart interval is not labelled `D` as a whole.

**Sequence.** Viterbi optimises evidence per second minus switching costs. Switching
H↔A requires evidence for the target; entering/leaving `D` requires compatible cues.
Gaps do not allow a change to be moved arbitrarily back to the start of an
occlusion. There is no target number of possessions and no imposed minimum duration.

The values are heuristic, fixed before the public evaluation; they are not calibrated
estimates or proven optimal values. They are kept unchanged:

| Parameter | Value | Physical or structural reason |
|---|---:|---|
| Control radius | 2 m | Reach close to the player; smooth decay, not assignment by proximity at any distance. |
| Team separation scale | 1.5 m | Damp contests with similar distances. |
| Fast speed scale | 9 m/s | A fast ball near a player may be a pass, not control. |
| Maximum speed for filtering jumps | 55 m/s | Conservative threshold for extreme isolated jumps, not for clipping normal passes. |
| Maximum interpolation | 0.24 s; confidence 0.3 | Cover very brief losses without inventing trajectories in long occlusions. |
| Speed from displacement | about 0.24 s | Reduce coordinate noise without smoothing the labels. |
| Out-of-pitch margin | 0.35 m; persistence 0.16 s | Prevent noise on the line from creating one-frame stoppages. |
| Still ball / still players | <0.65 / <1.2 m/s | Cues of placing or waiting, always combined. |
| Stillness persistence | 2 s; 3 s if the ball is missing | Absence is a more ambiguous signal and needs longer support. |
| Valid players for activity | at least 8 | Avoid reading a few tracks or an empty frame as collective stillness. |
| Weight control / automatic phase | 4.0 / 0.55 | Close geometry stronger than a correlated, temporally imprecise phase annotation. |
| H↔A cost / with D | 0.65 / 0.9 | Penalise fragmentation; a false stoppage splits a possession even if the same team comes back. |
| Restart search | interval ±2 s | Allow for the temporal imprecision of the automatic annotations. |
| Earlier stoppage search | up to 45 s | Allow for the preparation of free kicks/corners without extending the search indefinitely. |
| Team after a restart with no team | next control within 2 s | A hypothesis local to the restart; do not propagate a far future control. |

The weights are relative energies, not probabilities. For example, with a maximum advantage
of 4 per second, an isolated episode of one team has to overcome two costs of 0.65;
this allows clear controls of around a third of a second, but needs more
duration if the evidence is weak. It does not amount to erasing all short possessions.
The details and the remaining explicit thresholds are in `config.py` and `model.py`.

## Full-match diagnostics

In `.summary.json`, `full_match_diagnostics` contains `b_gpt` and `baseline_smooth50`,
each with `full_match`, `by_half` and `whole_video`. It does not use the public or the private GT.

- `possessions_per_minute`: number of possessions divided by the video time of
  the published halves. It includes stoppages and the stretch before the second kick-off within
  that block. It does not divide by 45 minutes or by ball-in-play time.
- `duration_seconds.p10/p50/p90`: percentiles of the duration of H/A possessions;
  in the total, the possessions of both halves are pooled, without averaging percentiles.
- `percent_D`, `percent_X`: percentages over the original labels, between 0 and 100.
  `whole_video` shows separately the percentages including half-time and unscored margins.
- Possessions: `X` inside each half is filled as the scorer does, without crossing
  half-time. `n_possessions_without_X_fill` also shows the count without that filling.
  A half that is entirely `X` keeps its lack of answer.

`smart_tagging` reports totals and types: throw-ins, corners, fouls/free kicks,
goal kicks and the two kinds of kick-off. Automatic instances are counted;
they are not claimed to be distinct real events. Unknown types and midpoints
outside the halves are counted in `event_inventory` and do not enter the denominator.

Definitions fixed for **reporting**, with no effect on the predictions:

- Each interval is represented by its midpoint, independent of the restart estimated
  by the candidate, and is assigned the half that contains that point.
- `inside_dead_fraction`: midpoint inside an explicit `D` run.
- `just_after_dead_fraction`: midpoint outside `D`, up to **2 s** after the
  exclusive end of a `D` run. The exit boundary counts as zero delay.
- `coherent_midpoint_fraction`: sum of the two above, without double counting.
- `near_dead_to_live_boundary_fraction`: midpoint within ±2 s of an explicit
  `D→H/A` exit. It helps tell a located restart apart from an overly long stoppage.
- `interval_could_be_coherent_fraction`: some position of the interval meets the
  criterion. It is a more permissive check of the annotation's uncertainty,
  not a substitute for the midpoint criterion.

The fractions go from 0 to 1, with numerators and denominators. With no events,
`null` is returned, not zero. Two seconds tolerate the tagging's imprecision, described as
around one second, without accepting any far-away stoppage. It is a fixed
diagnostic tolerance; it is not selected with the public result. Coherence uses explicit `D`,
without filling `X` as a supposed stoppage and without joining halves.

**Coherence is not accuracy.** The candidate already uses Smart Tagging: it is not an
independent validation. A prediction that is always `D` can reach 100 % coherence;
that is why `D` coverage, the location of the exit to live and the distribution of
possessions are shown. None of these aggregates justifies imposing a number of possessions.

## Tests, performance and limits

Synthetic tests only, with fixtures generated without match data:

```bash
python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics -v
python -m solution.b_gpt --synthetic --out /tmp/b_gpt_synthetic.csv
```

`--synthetic` does not even call `asset_paths`: it also generates the baseline input
and does not open the real CSV. A test blocks that function to guarantee it.

**34 tests passed** with NumPy 2.3.5 and pandas 2.3.3: official CSV contract,
alignment, units, sanitised invalid inputs, occlusions, short possessions,
restarts, independence between halves, Viterbi against exhaustive search,
denominators/percentiles, coherence limits, the degenerate always-`D` case and
equivalence of the `X` filling with the evaluator. Two full runs of
199,319 synthetic frames produced identical SHA-256 hashes. The suite, which includes
several full inferences, took about 14 s in this environment.
An extra run through the public command and the official validation script
finished in **5.30 s**, with **221.1 MiB** of peak memory reported, using only
synthetic inputs. Both commands exited with code zero.

The main cost is `O(frames × slots)`, with block-wise distances and a three-state
Viterbi. No video is decoded. The goal of under 30 minutes on CPU has
a wide margin in these tests; the real match has not been timed. Installing
dependencies and especially slow storage can affect the total time.

Limitations: with 2D coordinates the ball's height and the referee's decision cannot be
observed. Stillness does not always mean a stoppage; an occlusion can contain an
unobservable change. The automatic phases and the tracking share errors. Control still
depends on the nearby player; weighting it does not by itself add semantic information
about reception, pass or clearance. It is not claimed to beat the baseline on the full match.

The analysis of the public metrics received is in [ANALYSIS.md](ANALYSIS.md) ([English](ANALYSIS.en.md)).
It is used to understand the uncertainty, not to tune thresholds. There is no
parameter search or version selection with those 17 possessions.

The result CSVs and JSONs stay local. `.gitignore` excludes
`solution/*/output/`, `solution/*/.venv/`, `__pycache__/` and the result summaries.
When returning results to an LLM, share only aggregate numbers or sanitised
errors, never CSV rows, per-frame labels, XML, coordinates or images.
