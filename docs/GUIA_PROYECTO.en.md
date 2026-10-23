# More than a Hack 2027

> 🇪🇸 Translated from the Spanish original, [GUIA_PROYECTO.md](GUIA_PROYECTO.md).

## Project guide - Phase 1: Ball Possession

> **Team:** [GTT-TalentArena](https://github.com/GTT-TalentArena)  
> **Repository:** [more-than-a-hack-2027](https://github.com/GTT-TalentArena/more-than-a-hack-2027)  
> **Goal:** detect who has possession of the ball in every frame.

---

## Executive summary

| Item | Detail |
|---|---|
| Match | FC Barcelona vs Athletic Club |
| Reference video | Tactical video |
| Total frames | **199,319** |
| Frame rate | 25 fps |
| Output | CSV with one label per frame |
| Main metric | **spellF1** |
| Team | 3 to 5 members |
| Stated deadline | **17 November 2026** |

> **Key idea:** the ranking rewards complete, coherent possessions, not just isolated per-frame hits.

---

## 1. Goal and labels

Every frame of the tactical video has to get a label:

| Label | Meaning |
|---|---|
| `H` | Barcelona has possession and the ball is in play |
| `A` | Athletic Club has possession and the ball is in play |
| `D` | Dead ball or out of play |
| `X` | The system chooses not to answer |

The video has 199,319 frames. A possession is a maximal, continuous run of `H` or of `A`; the `D` periods are stoppages.

```text
H H H H A A A D D H H
```

This represents three possessions: Barcelona, Athletic Club, and Barcelona again after a stoppage.

There are no official labels such as `contested`, `transition` or `loose ball`.

---

## 2. Match and data

- Barcelona is the home team: `H`.
- Athletic Club is the away team: `A`.

### Tactical video

It is the main source:

- 199,319 frames.
- 25 fps and 1920x1080 resolution.
- Automatic tracking of players and ball.
- Homography between image and pitch.
- Tactical Smart Tagging.
- 46 tracking slots.
- The ball appears in about 57% of all frames.

### Broadcast video

It is optional, has about 164,488 frames and a different timeline, with cuts and replays. If it is used, the team has to synchronise it with the tactical video.

> The submission is always indexed to the tactical video. A file of about 164,000 rows will be rejected.

### Local data layout

```text
data/
|-- tactical/
|   |-- BAR-ATH_tactical.mp4
|   |-- BAR-ATH_tactical_atd.xml
|   |-- BAR-ATH_tactical_atd.txt
|   |-- BAR-ATH_tactical_homography.csv
|   `-- BAR-ATH_tactical_smart_tagging.xml
`-- broadcast/
    |-- BAR-ATH_broadcast.mp4
    |-- BAR-ATH_broadcast_atd.xml
    |-- BAR-ATH_broadcast_atd.txt
    `-- BAR-ATH_broadcast_homography.csv
```

### Data rules

- Don't upload them to GitHub.
- Don't redistribute them.
- Don't include them in public documentation.
- Don't publish trimmed videos, exported tracking or reconstructable derivatives.
- Keep `data/` excluded through `.gitignore`.

---

## 3. Tracking limitations

The tracking is automatic and uncorrected:

- There are no real player identities.
- The 46 slots don't necessarily represent 46 people.
- A slot can switch player.
- There can be gaps, duplicates and identity switches.
- Coordinates are normalised between 0 and 1.
- The ball is missing in about **41% of the evaluated frames**.

That's why the solution has to work with collective information: team, positions, distances, speed, pitch zones and temporal continuity.

---

## 4. Definition of possession

A possession changes when a player from the opposing team gains control of the ball.

### Doesn't necessarily mean a change

- A simple touch.
- A rebound.
- A deflection of a pass.
- Winning an aerial duel without then controlling the ball.

### Possible control signals

- The player keeps the ball for several seconds.
- The team completes several consecutive passes.
- The situation stays stable for several frames.
- The distance to the nearest player clearly favours one team.

> The public ground truth takes precedence over any theoretical interpretation.

---

## 5. Scored frames

The evaluated intervals are:

- First half: `11,185-90,651`.
- Second half: `110,808-190,197`.

The interval `110,808-113,741` is scored as `D`, because the second half hasn't started yet. The rest of the frames before, during half-time and after the match are not scored.

---

## 6. Metrics

### `spellF1`

It is the main metric and decides the ranking. It compares predicted and real possessions as time intervals using IoU at the thresholds `0.3`, `0.4`, `0.5`, `0.6` and `0.7`.

A solution can have a good `macroF1` and a bad `spellF1` if it keeps changing label and creates many artificial possessions.

### `macroF1`

It is the mean of the per-frame F1 of `H`, `A` and `D`. It is reported as the first tie-breaker, but it isn't the main metric.

### Reference baseline

```text
spellF1 = 0.2433
```

Our initial goal is to beat that result.

---

## 7. Handling `X`

`X` means the system doesn't want to give an answer it can't back up.

- In `macroF1`, an `X` inside a scored zone counts as a miss.
- In `spellF1`, the evaluator fills it with the last valid label of that half.
- An `X` inside a stable possession can be useful.
- An `X` right at a transition can drag the previous label along and be harmful.
- Outside the scored zones it has no cost.
- Cells must never be left empty: write `X`.

---

## 8. Rules

### Allowed

- Any language and framework.
- Classical models, machine learning and pretrained models.
- LLMs and commercial APIs, if the organisers can inspect them.
- External data.
- Our own detector, tracking or event recognition.
- Improving or replacing the provided automatic data.

### Forbidden

- Labelling the video by hand.
- Manually correcting the CSV frame by frame.
- Using the private ground truth or data derived from it.
- Submitting a file that the repository can't regenerate exactly.
- Depending on a private model or a dataset the organisers can't access.
- Publishing the match data or reconstructable derivatives.

Manually labelling a small amount of data to train or validate a model is allowed, but the final labels must come from the algorithm.

### LLM restriction

The videos, datasets, confidential information, restricted material or extracts that would allow them to be reconstructed must not be uploaded to external cloud LLM services. For those materials we must use local processing or check the service's conditions beforehand.

---

## 9. Code included

| Path | Function |
|---|---|
| `games.py` | Constants, paths, frames, pitch and alignment |
| `evaluation/possession_metrics.py` | Metrics, segments, matching and validation |
| `evaluation/run_evaluation.py` | Evaluation of the CSVs in `evaluation/results/` |
| `evaluation/validate_submission.py` | Validation of the CSV contract |
| `starter/baseline.py` | Player nearest the ball and temporal smoothing |
| `starter/load_atd.py` | Loads the tracking |
| `starter/load_smart_tagging.py` | Loads Smart Tagging |
| `starter/load_homography.py` | Loads the homography |
| `starter/*.ipynb` | Tutorials from the data to the first submission |

### Baseline

1. Finds the player nearest the ball.
2. Assigns possession to their team.
3. If it doesn't see the ball, it uses `D`.
4. Applies a temporal majority vote.

It doesn't use video, Smart Tagging, homography, a trained model, possession state or specific logic for restarts.

---

## 10. Requirements and commands

### Requirements

- Python 3.8 or later.
- `numpy` and `pandas` for evaluation and the baseline.
- Additional dependencies from `requirements-starter.txt` for notebooks and visualisation.
- The documentation especially mentions `kloppy` and `matplotlib`.

### Installation and evaluation

```bash
pip install -r requirements.txt
python starter/baseline.py
python evaluation/run_evaluation.py
python evaluation/validate_submission.py my_submission.csv
```

Recommended notebook order:

1. `01_smart_tagging.ipynb`
2. `02_tracking_atd.ipynb`
3. `03_first_submission.ipynb`

---

## 11. Submission format

```csv
frame,label
0,X
1,X
2,D
3,D
4,H
...
199318,X
```

| Requirement | Condition |
|---|---|
| Header | Exactly `frame,label` |
| Rows | Exactly 199,319 data rows |
| Frames | `0` to `199318`, in order |
| Labels | Only `H`, `A`, `D` or `X` |
| Cells | None empty |
| Encoding | UTF-8 |
| Index | Don't include an index column |

A malformed file is skipped and gets zero. Validate exactly the file you are going to upload.

---

## 12. Deliverables

### 1. Possession file

Full CSV with 199,319 rows.

### 2. Public repository

It must contain:

- Source code.
- Pinned dependencies.
- Installation and run instructions.
- A command to regenerate the CSV.
- Everything needed to reproduce the submission exactly.

It must not contain the match data.

### 3. Technical document

It must explain:

- The approach and why it was chosen.
- Assets used and discarded.
- Rules for possession changes.
- Handling of rebounds, duels, loose balls and restarts.
- Use of `X`.
- Limitations.
- Installation, running and reproduction.

---

## 13. Team repository

The best option is to work on a fork of the official repository inside the team's organisation.

Local path:

```text
D:\amolines\Documents\AMolines\TArena\more-than-a-hack-2027
```

Recommended structure:

```text
more-than-a-hack-2027/
|-- data/                 # local, never uploaded
|-- evaluation/
|-- starter/
|-- solution/
|   |-- main.py
|   |-- features.py
|   |-- possession_model.py
|   `-- postprocess.py
|-- docs/
|   `-- GUIA_PROYECTO.md
|-- requirements.txt
`-- README.md
```

Work with a branch for each experiment and review the changes before merging them into `main`.

---

## 14. Work plan

### Phase 1 - Environment

- Confirm the team fork.
- Install dependencies.
- Download the data and put it in `data/`.
- Run the baseline.

### Phase 2 - Understanding

- Review the tracking and the frames without the ball.
- Visualise positions.
- Analyse Smart Tagging.
- Understand the homography.
- Check the alignment.
- Study the 17 public segments.

### Phase 3 - Solution

Consider temporal continuity, hysteresis, minimum duration, previous state, restarts, lost ball, distances, speed, collective position, Smart Tagging and pitch zones.

### Phase 4 - Evaluation

- Use the public window to check format and alignment.
- Don't choose hyperparameters only by the public score.
- Measure the number and duration of possessions.
- Prioritise `spellF1`.
- Validate every CSV.

### Phase 5 - Submission

- Freeze dependencies.
- Test from a clean environment.
- Regenerate the CSV from scratch.
- Run `validate_submission.py`.
- Check that no private data is published.
- Prepare the technical document and the form.

---

## 15. Final checklist

- [ ] The public repository can regenerate the submission.
- [ ] `data/` is ignored.
- [ ] No videos, tracking, XML, private CSVs or derivatives are published.
- [ ] The private ground truth isn't used.
- [ ] The final labels are generated by the algorithm.
- [ ] The CSV has exactly 199,319 rows.
- [ ] Frames go from `0` to `199318` in order.
- [ ] Only `H`, `A`, `D` and `X` appear.
- [ ] There are no empty cells.
- [ ] `validate_submission.py` returns `OK`.
- [ ] The technical document explains the method, data, rules and limitations.
- [ ] The team has between 3 and 5 people.

---

## The question that should guide our solution

> **Has possession really changed, or are we looking at noise, a rebound, a temporary tracking loss or a contested ball?**

The metric rewards coherent possessions. That's why designing a good temporal model of states and transitions matters more than necessarily using a huge model.

---

## Official sources

- [CHALLENGE.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/CHALLENGE.md)
- [DATA.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/DATA.md)
- [EVALUATION.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/EVALUATION.md)
- [RULES.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md)
- [SUBMISSION.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/SUBMISSION.md)
- [FAQ.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/FAQ.md)
