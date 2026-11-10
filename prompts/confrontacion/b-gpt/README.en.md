# Candidate B record — b-gpt

> 🇪🇸 English translation of [README.md](README.md). The Spanish files in this folder are the protocol record and are left unchanged; each one has an `.en.md` translation next to it.

Record for section D of the [face-off protocol](../../../docs/experimentos/confrontacion-candidatos.md)
(English: [`confrontacion-candidatos.en.md`](../../../docs/experimentos/confrontacion-candidatos.en.md)).

| Field | Statement |
|---|---|
| Author | Edu (hxst1) |
| Branch | `cand/b-gpt`, created from `main` |
| Package | `solution/b_gpt/` |
| Tool | OpenAI Codex |
| Installed client version | `codex-cli 0.163.0`, checked with `codex --version` on 2026-10-21 |
| Model used | **ChatGPT-6 Astra**, confirmed by Edu when closing the session |
| Model identifier in the local configuration | `gpt-6-astra` |
| Reasoning level used | **`high`**, confirmed by Edu; matches the local configuration |
| Exact version/snapshot of the served model | Not shown in the interface information available for this record; no snapshot identifier is made up |
| Budget | **8 h of active time** |
| Session 1 | 2026-10-21, from **20:15 to 21:06**, Europe/Madrid |
| Active time used | **0 h 51 min of 8 h**, according to [horas.md](horas.md) ([English](horas.en.md)) |
| Time left | **7 h 9 min** |
| Candidate commit when this record was opened | `ce9c575` |
| Public evaluations used | **1 of 5** |
| Local repeat #2 | Completed by Edu: **8.545 s**, SHA-256 identical to the first CSV and official validation passed; not public |

Edu confirmed ChatGPT-6 Astra, reasoning `high`, used through Codex.
The earlier local check read only the `model`, `model_provider`,
`model_reasoning_effort` and `profile` fields, with no credentials and no history from other conversations.
The client version and the model alias are different things from a dated snapshot:
the statement does not allow making the latter up.
The [official reasoning documentation](https://developers.openai.com/api/docs/guides/reasoning)
describes the effort setting; it does not certify which model served this conversation.

## Submission command

From the root of `more-than-a-hack-2027`, with the pinned dependencies installed and
`MTAH_DATA_DIR` set by the participant:

```bash
python -m solution.b_gpt --out evaluation/results/<name>.csv
```

`<name>` is replaced with the chosen name. Inference on real data is run only by the
participant in their local environment, not by the LLM agent.

## Python issue reported when the record was opened

Edu reported `/usr/bin/python: No module named pip` when trying to install the dependencies.
No software was installed and the candidate was not changed in response to that issue.
At first the dependencies of the `control_v1` environment were reused.
When the session was closed, the environment was created in `solution/b_gpt/.venv/`, with the same Python
and the six pinned versions of local dependencies, with no downloads. The versions
and the NumPy and pandas imports were checked before and after the clean-up.
The earlier untracked folder `solution/control_v1/` was deleted at Edu's request,
without opening its result files. The current environment is activated like this:

```bash
git switch cand/b-gpt
source solution/b_gpt/.venv/bin/activate
export MTAH_DATA_DIR="$HOME/mtah2027"
python -m solution.b_gpt --out evaluation/results/b_gpt.csv
```

The environment is ignored by Git; the delivered package is still `solution/b_gpt/`.
This does not mean the `pip` error of the system Python was fixed.

Later Edu reported a generic error when reading XML. After setting
`MTAH_DATA_DIR` with `export`, Edu confirmed that the command returned an answer.
Neither the reader nor the method had to change. No match files or per-frame results
were received or opened to solve the issue.

## Contents and scope

- [prompts.md](prompts.md) ([English](prompts.en.md)): full user messages, in order, including the initial
  automatic context and the request to create this record; answers summarised.
- [horas.md](horas.md) ([English](horas.en.md)): the 2026-10-21 session, closed with 0 h 51 min of active time.
- [ejecuciones.md](ejecuciones.md) ([English](ejecuciones.en.md)): public evaluation #1 and identifiable synthetic checks.
- [desviaciones.md](desviaciones.md) ([English](desviaciones.en.md)): the two deviations declared by Edu.

This record is built retrospectively from the available conversation.
The context date is 2026-10-21, Europe/Madrid time zone; there are no timestamps for each
message and no historical activity timer available to the agent. The times
and the session's active time were confirmed by Edu when closing it.

The current close-out changes the record and deletes the earlier untracked version,
keeping the dependencies in the b_gpt environment. It does not change the versioned code,
the parameters, the method or the results of the current candidate.
It contains no restricted material and no per-frame predictions.
