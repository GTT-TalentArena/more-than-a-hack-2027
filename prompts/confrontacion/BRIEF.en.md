# Common brief for the face-off (#26)

> 🇪🇸 English translation of [BRIEF.md](BRIEF.md), added afterwards for reference. The Spanish original is the frozen brief that both candidates received; it hasn't been changed.

It is the first message the LLM of each candidate receives, **identical** for both. After that, each author may
add their own prompts, but they are all stored in `prompts/confrontacion/<cand>/`. The protocol is in
[`docs/experimentos/confrontacion-candidatos.md`](../../docs/experimentos/confrontacion-candidatos.md) (English: [`.en.md`](../../docs/experimentos/confrontacion-candidatos.en.md)).

Frozen on 22 Oct 2026. If it changes, it is noted as a deviation for both candidates.

---

**Task.** For the match FC Barcelona – Athletic Club (LaLiga 2024-25), produce one label per frame of the
**tactical video** (199,319 frames, 25 fps): `H` home possession with the ball in play, `A` away possession with
the ball in play, `D` dead ball or out, `X` no answer. The full rules are in `CHALLENGE.md`, and the metric
(spellF1, which rewards complete possessions, and macroF1) in `EVALUATION.md` and
`evaluation/possession_metrics.py`.

**Inputs.** Those in `DATA.md`: automatic tracking (ATD) with players and ball, homography and Smart Tagging of the
tactical video, and the video itself; optionally, the broadcast, which isn't synchronised. Paths are obtained with
`games.asset_paths()`. There are loaders in `starter/`, a prior study in `docs/ESTUDIO_POSESION.md` and a baseline
in `starter/baseline.py` (spellF1 0.2433 on the full match).

**Data restriction (mandatory).** You can't see the match data or any extract of it. Write the code from the
documentation and test with synthetic data. I run it locally and give you back only errors and aggregate metrics.
Don't write code that prints data rows.

**Delivery.** A `solution/<cand>/` package runnable with a single command, which writes a `frame,label` CSV of
199,319 rows that passes `python evaluation/validate_submission.py`. Pin the dependencies. It must take less than
30 min on CPU. Document the method in `solution/<cand>/README.md`.

**Challenge rules.** The labels come from an algorithm, never by hand. The private ground truth can't be used.
The 5-minute public window (17 possessions) is for checking that everything works, not for tuning parameters.

**Goal.** Maximise spellF1 on the full match, which we can't measure. Reason about what generalises, not about what
scores on the 5 public minutes.
