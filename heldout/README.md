# Held-out evaluation on other games (issue #47)

Runs any model of this repository on the **DFL/IDSSE open data** (7 Bundesliga and 2. Bundesliga matches,
CC BY 4.0) and scores it against the DFL's own per-frame ball status and possession. The plan it implements,
including what counts as a win, is [`docs/experimentos/ISSUE_47_ALTERNATIVE_TO_A.md`](../docs/experimentos/ISSUE_47_ALTERNATIVE_TO_A.md).

The challenge game never goes through here, and the `heldout` Docker service does not mount it.

## How it works

1. **fetch**: downloads the 21 DFL files (2.6 GB) from figshare, checking each MD5.
2. **convert**: reads them with kloppy (`only_alive=False`) into one array file per match: positions in the
   challenge's metres and orientation, speeds recomputed in m/s, and the labels (targets only).
3. **run**: for each match, profile and seed, degrades the positions (plan §1.2), writes a **bundle in the
   challenge's file format** (EPTS XML + TXT, an empty Smart Tagging file), and runs each model through P0
   (`python -m solution.predict`) with the data folder pointed at that bundle. Models are not modified and
   cannot tell the bundle from the challenge data, except that it has no tagging. Each DFL half is placed at the
   start of the matching challenge half; the remaining frames have no tracking and are not scored.
4. **report**: applies the decision rule (plan §3.6) to the recorded runs.

Everything lands under `salidas/heldout/` (git-ignored): raw files, arrays, ground truth, predictions and
`results.jsonl` with one line per run (hashes of the observation, the ground truth, the bundle files, the config
and the CSV).

**No stale results.** A run is reused only when its match, profile, seed and model name **and** two identities
match (`heldout/identity.py`): the model's (its config, its source files, P0 and `games.py`) and the harness's
(`heldout/`, the official metric code, Python/numpy/pandas versions). Change any of them and the run is redone and
recorded separately. `report` only counts runs of the current identities, and refuses to recommend ("incomplete
evaluation: no recommendation", exit code 3) unless every match × profile × seed of the protocol is there for both
models, with the same observations and ground truth for both and prediction files that still match their hashes.

## Commands

```bash
docker compose build heldout
docker compose run --rm heldout fetch
docker compose run --rm heldout convert
python -m unittest heldout.tests        # or inside the image, see below

# Development matches (the default): use these while building a variant
docker compose run --rm heldout run --model a=configs/candidate_a.json --model v=configs/<variant>.json

# Final comparison only (Thursday 29): the two reserved matches
docker compose run --rm heldout run --heldout --matches J03WN1 J03WR9 \
    --model a=configs/candidate_a.json --model v=configs/<variant>.json
docker compose run --rm heldout report --a a=configs/candidate_a.json --variant v=configs/<variant>.json
```

Tests inside the image: `docker compose run --rm --entrypoint python heldout -m unittest heldout.tests`.

## Rules this keeps

- **Reserved matches** (`J03WN1`, `J03WR9`) need `--heldout`. Do not run, look at or tune on them while
  developing: they are the only evidence that does not come from data we already used.
- **Targets never reach a model**: degradation and bundles are built from positions only; a test checks that
  shuffling or removing the labels leaves the observation byte-identical.
- **No DFL events** are used: they are human-coded and would be a near-oracle input the challenge game does not
  have.
- **Scores here are not challenge scores**: DFL's possession definition is not our ground truth's. Only paired
  comparisons between models on the same runs mean anything.
