# GTT: possession labelling for BAR–ATH (Phase 1 technical document)

> **Draft of 3 November 2026. Remove this block before submitting.** It assumes the recommendation in #47 is accepted:
> the variant `candidate_a_dfl` from #56. Before the freeze (#22):
> - update the commit and the hash in section 8;
> - resolve every **[TEAM]** marker;
> - save a copy named after the team, as `SUBMISSION.md` asks.

## 1. Approach

The ranking metric scores whole possessions, not frames, so we do not classify frames one by one. We compute evidence
per frame from the tracking and then find the single best H/A/D sequence for each half with an exact Viterbi decoder:

```
maximise   Σ_t evidence(state_t, t)  −  λ · (number of state changes)      with every stoppage ≥ 2 s
```

We chose this over voting and hysteresis because it removes flicker without imposing a minimum possession length. On
five synthetic matches, with the same evidence:

| Decoder | spellF1 | False possessions under 2 s | Real short possessions kept (of 627) |
|---|---:|---:|---:|
| **Viterbi** | **0.783** | 17 | 214 |
| Hysteresis | 0.761 | 195 | 298 |
| Majority vote | 0.659 | 722 | 267 |

The model has three kinds of evidence:

- **Team evidence (H or A).** A control kernel on the distance from the ball to each team's nearest player, gated by
  the relative speed of ball and player. Touches, detected as a change in the ball's velocity next to one team's
  player, add a small amount. Smart Tagging phases add a weak prior.
- **Dead-ball evidence (D or alive).** Ball out of the pitch, exit followed by a gap, still ball on a restart spot, kick
  after a still ball, slow reappearance, collective player speed, long ball absence, kick-off formation and `SET PIECES`
  windows. Team evidence never counts against `D`: the player taking a throw-in is as close to the ball as a dribbler.
- **Ball-free team model.** A logistic regression on team shape and movement, used where there is no ball or no clear
  control. It was **trained on other matches only** (section 3).

It runs in under 30 seconds on a CPU, and it is deterministic.

We tried a second, independently written candidate (B). It stays in the repository as a reference and is not used.

## 2. Assets

| Asset | Use |
|---|---|
| Tactical ATD | **Used**: the main input |
| Smart Tagging | **Used** as input: `SET PIECES` as stoppage evidence, phases as a weak team prior (at most 0.06 nats per frame) |
| Homography | **Dropped**: the ATD is already in pitch coordinates |
| Tactical video | **Dropped**: not an input, and nothing was trained or tuned on it. **[TEAM]** Confirm that nobody checked model output against the video |
| Broadcast | **Dropped**: not synchronised, and its homography is missing in a third of the frames |
| Public ground truth | Not an input. See section 6 for how it was used during development |
| Private ground truth | Never available or used |
| DFL/IDSSE open data | **Used** to train the ball-free model and to evaluate |
| Metrica sample data | **Dropped**: we found no licence file |
| SkillCorner open data | **Dropped**: its labels are another model's output, and the camera differs |
| PFF FC World Cup 2022 | **Dropped**: terms of use not confirmed |
| Our own restart detector (P2) | **Dropped**: available in the code but off. It did not improve the synthetic results |

## 3. Training data

| | |
|---|---|
| Dataset | DFL/IDSSE open data (Bassek, Rein, Weber and Memmert, 2025), figshare [10.6084/m9.figshare.28196177](https://doi.org/10.6084/m9.figshare.28196177) v1, CC BY 4.0 |
| Matches used to train | `J03WMX`, `J03WOH`, `J03WOY`, `J03WPY`, `J03WQQ` (Bundesliga and 2. Bundesliga, 2022/23) |
| Labels | The dataset's per-frame `BallPossession`, on frames where `BallStatus` is active. Provided by the DFL. We labelled nothing |
| Amount | 133,065 frames (one in three of the live frames with valid features) |
| Input degradation | Tracking degraded to resemble automatic tracking: `full` profile, seed 47 (section 5) |
| From the provided game | **Nothing.** The team created no hand labels on any match |

File hashes and the leave-one-match-out results are stored with the model in `solution/a_dfl/weights.py`.
`python -m solution.a_dfl.train` regenerates that file. Retraining on another platform (Linux in Docker, against the
original on Windows) changes the coefficients by at most 1e-12. On four DFL runs, the retrained model gave CSVs
identical to the shipped model's. The submission uses the committed coefficients, so it does not depend on retraining.

The model is antisymmetric under swapping the teams, with no intercept, so it carries no preference for the home side
of the training matches. Its weight is fixed at 1.00, set by leave-one-match-out agreement on those matches (87.5%).

### Values estimated at run time

Some values are measured from the input of the match being labelled, with no labels, ground truth or video. They are
the part of the system closest to the organisers' rule on tuning, so we list them all:

| Value | How it is measured |
|---|---|
| Ball lag behind the players | Speed of carried balls (no correction was applied on this match in the run we logged) |
| Control radius | Median distance from slow balls to their nearest player, clamped to a fixed range |
| Touch scale and threshold | Window with the most peaks near a player; 95th percentile of free ground balls |
| Still-ball threshold | Position noise of the ball |
| Stopped or moving play | Two-component Gaussian mixture on collective speed |
| Smart Tagging codes | Polarity and reliability, by agreement with frames where proximity clearly names a team |
| Long ball absence | Association between long gaps and `D` in a first decoding pass |

## 4. Possession rules

| Situation | What the model does |
|---|---|
| **Loose ball, flight or occlusion** | Evidence is zero and possession stays with the last team. The change is placed at the new team's first touch |
| **Duel** | With both teams close, the evidence cancels out, so nothing changes |
| **Touch, deflection or clearance without control** | Does not change possession alone: a touch is worth 1.5 nats and a change costs 3 |
| **Fast pass next to an opponent** | Not control: the relative-speed gate removes it |
| **Interception or reception** | Changes possession once control follows, dated at the first contact |
| **Short possessions** | No minimum length, but a flicker inside a possession needs 6 nats of evidence |
| **Ball not visible** | Not a stoppage by itself: possession is held, and the ball-free model can move it. Only a long absence counts towards `D` |
| **Ball out** | `D` from the dated crossing of the line |
| **Stoppage end** | As late as the evidence allows: the kick after a still ball or the touch after a slow reappearance |
| **Stoppage length** | At least 2 s |
| **Each half** | Decoded separately, and nothing carries across |

**Use of `X`.** Only outside the two scored halves. Every scored frame gets `H`, `A` or `D` (0% `X` on scored frames),
because `X` repeats the previous label in the metric and would be costly at a change of possession.

## 5. Evaluation

We have no score on the full match, and nothing below predicts one.

**Held-out matches.** Two DFL matches, `J03WN1` and `J03WR9`, were kept out of training and development. The plan and
the decision rule were fixed in advance and published. Tracking was degraded in four ways (ball gaps on 41% of frames,
crowded gaps, fragmented anonymous tracks and position noise), each with three seeds. We compared the model against the
same pipeline with the ball-free model trained on the match itself:

| Held-out match (degraded profiles) | Self-trained model available | spellF1 self-trained | spellF1 ours | macroF1 self-trained | macroF1 ours |
|---|---|---:|---:|---:|---:|
| `J03WN1` | One half only | 0.3339 | 0.3585 | 0.8111 | 0.8217 |
| `J03WR9` | Both halves | 0.4285 | 0.4294 | 0.8413 | 0.8431 |

External training costs nothing measurable here, but it has not been shown to improve the model. On the `full`
profile, the 90% interval of the paired difference includes zero for one seed of three. Where the self-trained version
has its model in both halves, the two tie. These figures use DFL's definition of possession, and two matches do not
establish generalisation. Details: `docs/experimentos/ISSUE_47_ALTERNATIVE_TO_A.md`.

**Development matches, leave one match out.** spellF1 0.4382 for ours, 0.4247 self-trained and 0.3747 without any
ball-free model.

**Provided game, without ground truth.** 216 possessions, median 10.9 s, 49.3% `D` on scored frames. These are
plausibility checks, not accuracy.

## 6. Development history

We want this to be read plainly, because parts of it predate the organisers' clarification of 3 November 2026.

- **LLM use.** The model code was written with LLMs (Claude Opus 5.5; ChatGPT-6 Astra and Claude for the unused
  candidate B). They received documentation, code, synthetic data and aggregate logs, not match data. **[TEAM]** Confirm
  this for every member.
- **Self-training.** Versions up to v1.6 trained the ball-free model on the provided match's tracking, with
  automatically generated targets. The submitted model replaces that fit with the externally trained model, plus a
  guard that turns it off in a half whose attack direction is undetermined. Everything else is v1.6.
- **Public window.** The public ground truth is not an input, and we did not train on it. Candidate A was scored on it
  five times as planned and at least twice more by accident, as recorded in `prompts/confrontacion/a-opus/`. The
  aggregate detail guided which components to work on (late boundaries, missing possessions). The records state that
  no parameter value was chosen by the public score. Candidate B's records show that public results influenced which
  of its versions to keep.
- **Constants and the provided match.** Versions v1.0 to v1.6 were revised after reading aggregate logs from the
  provided match. For example, the change cost went from 5 to 3, and the touch detector was redesigned twice, because
  the logged counts were far from what synthetic matches gave. Those changes were tested on synthetic matches. The
  constants were not re-estimated on external data afterwards.

The full record is in `prompts/confrontacion/` and has not been rewritten. A blind video review that we had planned was
withdrawn without being carried out. **[TEAM]** Confirm that no part of it was done.

## 7. Limitations

- **Short possessions.** Almost none under 2 s is detected, and about half of those between 2 and 5 s. This is the
  largest known gap.
- **Fouls and offsides.** There is no whistle in the tracking, so these stoppages start late, by about 3 s on synthetic
  matches.
- **Aerial balls.** The ATD projects them onto the ground. The speed gate limits the damage but does not remove it.
- **Domain gap.** The ball-free model learned from corrected optical tracking of another league, with another
  definition of possession. We can only measure agreement with ball proximity on the provided game (88.5% and 86.9%).
- **Team balance.** A model with no team preference cannot use one-sidedness specific to this match.
- **Invented football scenarios.** On our 68 acceptance probes, the model's output matches the self-trained version on
  all 68. That version passes 12, fails 20, and the remaining 36 are diagnostic only. Failures include a real 1.2 s
  recovery, which can decode as a stoppage.
- **No unused matches left.** Any further change would need new validation data.

With more time, we would work on stronger control evidence for short possessions, re-estimate the constants on
external tracking closer to the ATD, and test on more than two held-out matches.

## 8. Reproduction

Requirements: Docker and the match data bundle. No GPU. Dependencies are pinned in `docker/requirements.lock`.

```bash
git clone https://github.com/GTT-TalentArena/more-than-a-hack-2027.git
cd more-than-a-hack-2027
git checkout <FROZEN_TAG>
mkdir -p salidas
export GTT_UID=$(id -u) GTT_GID=$(id -g) DATOS=/path/to/data   # the folder that contains tactical/
docker compose build modelo
docker compose run --rm --entrypoint python modelo -m solution.predict \
    --config configs/candidate_a_dfl.json --out /salidas/GTT.csv
docker compose run --rm --entrypoint python modelo evaluation/validate_submission.py /salidas/GTT.csv
sha256sum salidas/GTT.csv
```

Expected at commit `14902d8`: SHA-256 `a090254caabcbbbc67a9569b9a5a9439aa3d643e5a41988af61e737dcc97fd97`, in 14–27 s on
an AMD Ryzen 5 3600 with 31 GB of RAM, Python 3.11.17, NumPy 2.4.6 and pandas 3.0.6. Two runs from a clean clone gave
the same file. **[TEAM]** Have another member repeat it at the frozen tag.

To regenerate the evidence, using DFL data only (it never mounts the match data):

```bash
docker compose build heldout
docker compose run --rm heldout fetch
docker compose run --rm heldout convert
docker compose run --rm heldout run --heldout --matches J03WN1 J03WR9 \
    --model a=configs/candidate_a.json --model v=configs/candidate_a_dfl.json
docker compose run --rm heldout report --a a=configs/candidate_a.json --variant v=configs/candidate_a_dfl.json
```
