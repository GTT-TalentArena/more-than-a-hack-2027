# Data contract · P0 v1

> 🇪🇸 Translated from the Spanish original, [CONTRATO_DATOS.md](CONTRATO_DATOS.md).

> Team integration design decision, 22 October 2026.
>
> Status: integration contract v1. P0 includes validators for frames, positions and masks in `solution/contract.py`, configurable generation and a command adapter. Nico/Jimy/Pablo's signals are target interfaces: their production and conformance still need to be checked. The challenge's official definitions take precedence over this document.

## 1. Principles

1. A single time reference: the **tactical** video.
2. A missing observation doesn't mean a dead ball or a zero coordinate.
3. Signals are evidence, not true labels.
4. The prediction generator doesn't receive ground truth; the evaluator consumes it separately.
5. The original data is kept locally and normalised in adapters, without rewriting the official loaders.
6. The agreed interface of candidates A/B isn't changed during a frozen round.

## 2. Time and indices

For BAR-ATH, `games.GAMES` and `games.source_frames()` are used as the source of constants: 199,319 tactical frames and 25 fps. Don't scatter these numbers through the code.

| Field | Type | Rule |
|---|---|---|
| `frame` | integer | `0 <= frame < n_frames`; tactical video index |
| `time_s` | derived float | `frame / fps`, from the start of the video, not from kick-off |
| `start_frame` | integer | Start, included |
| `end_frame` | integer | End, excluded; an interval contains `start_frame <= frame < end_frame` |

The output covers **the whole video**, not just the five public minutes nor just the periods of play. Don't trim or shift rows to evaluate.

### Required conversions

- Delivered tactical ATD: `frame = frame_id - 1`. Synthetic examples: 1 → 0, 26 → 25.
- Tactical homography: its `frame` column already starts at 0.
- Smart Tagging: `int(round(seconds * fps))`, like the official loader; Python rounds ties to even. Its intervals are half-open.
- Don't apply the per-half offsets from `games.py` to this ATD: they describe another source counter, not the index of the delivered ATD.
- Broadcast has its own timeline. In v1 it isn't mixed with tactical; any future use requires an explicit, verified mapping.

Reject duplicated, out-of-range or unordered indices. If observations are missing, keep the full grid of frames and mark the absence; don't compress time. An unexpectedly misaligned source file must produce a diagnostic, not an invented offset correction.

## 3. Coordinates

The original normalised positions are kept to apply homographies. For physical distances, the common interface uses metres:

```python
x_m = x_normalized * pitch_length_m
y_m = y_normalized * pitch_width_m
```

Dimensions: read `games.GAMES[game]["pitch"]`; currently `(105.3, 68.0)`.

The origin `(0, 0)` is the same as in the ATD's normalised system; `x` runs along the length and `y` along the width. It is **not assumed** that H always attacks towards `+x`, and axes are not flipped per half. Tactical orientation, if needed, will be an independent, verified signal.

Positions outside the pitch rectangle can be real. Don't clip them to the bounds: we would lose evidence of the ball going out. Reject observed infinities or non-numeric values; apply other plausibility filters only with documented rules.

Homography: pass normalised coordinates to `starter.load_homography.project()`, not metres. An invalid matrix isn't used; its reprojection error isn't a probability.

## 4. Teams, slots and absences

- Teams: `H` and `A`, taken from metadata; not deduced from the shirt number or an arbitrary column position.
- A `slot_id` identifies a slot in the export; it **doesn't guarantee a stable player identity**. Don't accumulate per-person statistics without resolving identity.
- `ball_observed` and `player_observed` indicate valid presence in the source, not real physical presence.
- In memory, an unknown coordinate → `NaN`, with mask `False`. In JSON → `null`, never the non-standard literal `NaN`.
- An interpolated observation is kept distinct: `*_observed=False`, `*_available=True`, `*_imputed=True`. Don't present it as an original measurement.
- Without interpolation: `available == observed` and `imputed == False`.
- Neither `(0, 0)` nor `D` is used as an automatic substitute for missing data.

## 5. Normalised tracking interface

Initial in-memory format: a dictionary of NumPy arrays. No Parquet file, database or new framework is required. If a cache is persisted, it is local and ignored by Git.

| Key | Shape / type | Description |
|---|---|---|
| `frame` | `(N,)`, int64 | Exact sequence `0..N-1` |
| `ball_xy_m` | `(N, 2)`, float64 | Ball position; absences as NaN |
| `ball_observed` | `(N,)`, bool | Valid measured ball |
| `ball_available` | `(N,)`, bool | Usable coordinate, observed or imputed |
| `ball_imputed` | `(N,)`, bool | Estimated coordinate, not measured |
| `player_xy_m` | `(N, S, 2)`, float64 | Positions per slot |
| `player_observed` | `(N, S)`, bool | Valid measurement mask |
| `player_available` | `(N, S)`, bool | Usable position |
| `player_imputed` | `(N, S)`, bool | Estimated position |
| `slot_id` | `(S,)`, string | Slot identifier in the export |
| `slot_team` | `(S,)`, string | `H`, `A` or unknown; unknowns excluded from the team vote |

`N` comes from the tactical source; `S` from the metadata, not fixed at 22 or 46. The adapter validates shapes and consistency between masks and coordinates. It must avoid duplicating whole arrays unnecessarily.

## 6. Module signals

The model receives aligned `(N,)` signals. Each numeric signal includes a validity mask. Missing value → NaN and validity false. A score in `[0,1]` is an **evidence strength**, not a calibrated probability unless explicitly shown.

| Group | Proposed fields | Producer |
|---|---|---|
| Distances | `nearest_H_m`, `nearest_A_m`, `distance_valid` | Nico |
| Contact/control | `control_H_score`, `control_A_score`, `control_valid` | Jimy |
| Dead ball | `dead_score`, `restart_score`, `dead_valid`, `restart_valid` | Pablo |
| Smart Tagging | `tag_H_score`, `tag_A_score`, `tag_dead_score`, `tag_valid` | Pablo |

A team distance is only valid if there is a ball and at least one usable player from that team. If the teams have different coverage, the adapter exposes per-team masks and `distance_valid` requires both for an H/A comparison.

Optional modules can be missing entirely: the model must declare it in its configuration and not turn their absence into negative evidence. No comparison by distance is made when the distance isn't valid. Thresholds and weights belong to the configuration, not to this contract.

The original Smart Tagging is kept as `{code, start_frame, end_frame, tags}` events from the official loader. Rasterising into signals is done by an adapter with a documented overlap policy: in v1, combine evidence of the same type with max, keep contradictory H/A evidence and let the model resolve it. Don't copy those intervals directly into the final CSV.

## 7. Model and output

Target internal interface:

```python
def predict(inputs, config):
    """Returns an (N,) array of H/A/D/X labels."""
```

The initial baseline can read the authorised data directly through its official code. It doesn't need to pretend it consumes signals that don't exist yet; the adapter documents which inputs it really uses.

Mandatory external contract:

```csv
frame,label
0,H
1,H
2,X
```

A purely synthetic, incomplete example, not a real submission. The real submission has the exact header, 199,319 rows, consecutive indices and only `H/A/D/X`. The official validator decides its validity.

v1 doesn't impose football decisions such as a minimum duration or a universal fill rule: those are P1–P7 hypotheses. It does forbid confusing absence with a dead ball. `X` isn't free: macroF1 penalises it; for temporal metrics the evaluator fills abstentions according to its rules. Use its counts, without rebuilding a different metric in P0.

## 8. Compatibility with candidates A/B

The current protocol in #26 requires `python -m solution.<cand> --out <csv>`. Keep it. P0 can run that command with an argument list without `shell=True`, collect the CSV and pass it to validation/evaluation.

The configuration is recorded separately if the candidate doesn't accept `--config` yet. Don't claim an option was applied if its implementation doesn't consume it. Don't share code between candidates before the freeze or change the budget to introduce this contract. Any change to the brief is agreed and recorded for both.

## 9. Privacy and evolution

Don't publish normalised tracking, per-frame signals, full predictions, caches, images or real disagreement intervals without checking that sharing them is allowed. Keep them local in `salidas/` or outside the repo. Share only permitted aggregate evidence and synthetic examples. The official baseline is an exception deliberately kept as a reference: it assigns D when it doesn't see the ball; P0 doesn't correct it so as not to change the reference algorithm. Improved models must handle that limitation according to P1/P2.

Versioning: `contract_version: "1.0"` in new configurations and records. An incompatible change bumps the major version and requires an explicit adapter or migration. The names defined here are the initial decision; if a module can't meet them, record the discrepancy and resolve it before integrating it, don't silently change units.

## References

- [Official data](../DATA.md), [FAQ](../FAQ.md), [evaluation](../EVALUATION.md).
- [ATD loader](../starter/load_atd.py), [homography](../starter/load_homography.py), [Smart Tagging](../starter/load_smart_tagging.py).
- [Current A/B protocol](experimentos/confrontacion-candidatos.en.md).
