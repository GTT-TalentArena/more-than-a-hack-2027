# Run log

> 🇪🇸 English translation of [ejecuciones.md](ejecuciones.md).

| # | Date | Commit | Command | Aggregate result | Public (A8)? |
|---|---|---|---|---|---|
| 1 | 2026-10-21 | no commit | public evaluation with bootstrap 1000 | spellF1 0.3895, macroF1 0.6620, 21 possessions, 13.6 s on average | Yes, #1 |
| 2 | 2026-10-21 | no commit | `python -m unittest solution.control_v1.test_synthetic -v` | First suite: 20 tests; 18 passed and 2 skipped for lack of pandas. Synthetic only. | No |
| 3 | 2026-10-21 | no commit | `python -m unittest solution.control_v1.test_synthetic -v` | Extended suite: 22 tests; 20 passed and 2 skipped for lack of pandas. Synthetic only. | No |
| 4 | 2026-10-21 | no commit; content recorded later in `ce9c575` | `solution/control_v1/.venv/bin/python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics -v` | 34 tests passed in 14.117 s; official validation on synthetic data and two complete synthetic CSVs with identical SHA-256. | No |
| 5 | 2026-10-21 | no commit; content recorded later in `ce9c575` | `solution/control_v1/.venv/bin/python -m solution.b_gpt --synthetic --out <synthetic_tmp>/synthetic.csv`, followed by `solution/control_v1/.venv/bin/python evaluation/validate_submission.py <synthetic_tmp>/synthetic.csv` | Both commands exited with code 0; 5.301 s together; peak memory reported by the candidate 221.14 MiB; stdout limited to five aggregates. | No |
| 6 | 2026-10-21 | `d91b063` in the working tree when the issue was reported | `python -m solution.b_gpt --out evaluation/results/b_gpt.csv` | Edu reported `Cannot read XML input or invalid XML syntax.`; no metrics were obtained. | No |
| 7 | 2026-10-21 | Code from `ce9c575`; exact run commit not confirmed, later changes documentation only | `python -m solution.b_gpt --out evaluation/results/b_gpt.csv`, with `MTAH_DATA_DIR` set | 354 possessions; mean duration 11.953446327683617 s; median 6.779999999999999 s; D 33.40677464638008 %; X 0.0 %. Full-match aggregates reported by Edu. | No |

Public evaluations used: 1 of 5

Row 7 includes the aggregate output sent after confirming that `export`
solved the issue. No extra run is assumed because the command was pasted
again. With the 158,857 published frames at 25 fps, these numbers correspond
to about 3.343 possessions/minute, 70.525 minutes predicted live and 35.379 minutes `D`
within the halves. They are arithmetic checks, not accuracy measures.
A mean larger than the median is consistent with a skewed distribution of
durations, but on its own it does not identify wrong fragmentation or merging.
The full and per-half baseline aggregates for the requested comparison are missing;
the CSV was not consulted and no parameter was changed.

Row 1 was run by Edu locally and reported to the agent only through
aggregates. It belongs to `control_v1`, before it was packaged as `b_gpt`; it has not been
counted again because of the rename. The literal command line of that
evaluation is not known, so Edu's description is kept.

The same message included the baseline as a reference: spellF1 0.3256,
macroF1 0.6207, 26 possessions, 10.8 s on average; 90 % CI of spellF1 `[0.214, 0.447]`.
The candidate had a 90 % CI of `[0.242, 0.537]`. No CSV or GT was opened for this record.

Rows 2–5 are development checks identified in the conversation,
run only on synthetic data. The numbering of those rows identifies
entries of the retrospective record; it does not give them a time
relative to evaluation #1, which is not recorded. Synthetic tests do not use up A8.
`<synthetic_tmp>` stands for a temporary directory created for that test;
it is not the match data folder.

During development, synthetic measurements were also taken with throwaway scripts:
generation/inference/writing of 199,319 frames and 46 slots, 3.88 s and 178.7 MiB;
reading a synthetic ATD of that size, 4.54 s and 138.0 MiB. They are not public
scores or measurements on the match. The full lines of those scripts were not
kept as versioned executables and no commands are made up here to reproduce them.

## Repeated inference to check determinism

The first full inference reported by Edu is entry 7 of the record
above. The repeat requested when closing the session is identified as **local run
#2 (not public)**. This numbering of real inferences is independent of the
numbering of historical entries and of the A8 public evaluations.

Local run #2 is **completed according to the results reported by Edu**.
The agent did not run the inference or open the CSVs: it records the hashes, times and
aggregates sent by the participant. This format and determinism check
does not consult the GT and does not use up A8.

| Local # | Date | Reference commit | Command | Aggregate result | Public (A8)? |
|---|---|---|---|---|---|
| 1 | 2026-10-21 | Code from `ce9c575`; see historical entry 7 | `python -m solution.b_gpt --out evaluation/results/b_gpt.csv` | 354 possessions; mean 11.953446327683617 s; median 6.779999999999999 s; D 33.40677464638008 %; X 0.0 % within the halves. SHA-256 reported together with the repeat. | No |
| 2 | 2026-10-21 | `819efb2`, the version available when the repeat was requested; method of `ce9c575` unchanged | `time python -m solution.b_gpt --out evaluation/results/b_gpt_r2.csv` | 8.545 s real, 9.05 s user CPU, 0.19 s system, 108 % CPU; same five aggregates; identical SHA-256; official validator OK, 199319 rows, indices 0..199318. | No |

SHA-256 reported for **both** files (`b_gpt.csv` and `b_gpt_r2.csv`):

```text
60ea141519a8978cfb840496d7c39f040b40fba3b0610a81fd1a68160f822f6d
```

The validator reported, over **the whole video**, H 64304 (32.3 %), A 41484 (20.8 %),
D 53069 (26.6 %) and X 40462 (20.3 %), with 354 possessions of rounded mean 12.0 s.
This does not contradict the candidate's summary: the latter uses only the 158857
frames of the published halves, where D is 33.40677464638008 % and X is 0.0 %.
The 40462 X frames match the published unscored extension.

These results support the byte-for-byte reproducibility of the two reported local
runs, the output contract and an inference time under
30 minutes on Edu's machine. They do not prove the accuracy of the labels or allow
estimating the full-match spellF1. The run time is not added as
a new session to the active-hours log declared by the participant.

Commands of this check, run only by Edu from the root:

```bash
source solution/b_gpt/.venv/bin/activate
export MTAH_DATA_DIR="$HOME/mtah2027"
time python -m solution.b_gpt --out evaluation/results/b_gpt_r2.csv
sha256sum evaluation/results/b_gpt.csv evaluation/results/b_gpt_r2.csv
python evaluation/validate_submission.py evaluation/results/b_gpt_r2.csv
```

`time` uses the zsh shell timer, without requiring `/usr/bin/time`. The original CSV
is kept. Only the hashes, the time and the validator's aggregate output were returned
to the agent; the CSV files and their per-frame content stay local.
