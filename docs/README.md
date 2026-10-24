<a href="https://gtt-talentarena.github.io">
  <img alt="GTT — Més que dades (more than data). Football analytics team at More than a Hack 2027." src="https://raw.githubusercontent.com/GTT-TalentArena/.github/main/profile/assets/banner.svg" width="100%">
</a>

# GTT — TalentArena

**Turning football data into meaningful insights.**

We are GTT, a five-member team participating in **More than a Hack 2027**, the football analytics hackathon at
Talent Arena in Barcelona. Our team combines data analysis, algorithm development, evaluation and engineering to
explore how data can help us better understand football.

> **Current focus:** estimating team possession frame by frame from automatic tracking data and pitch homography.

<sub><code>01 — THE CHALLENGE</code></sub>

## Who has _the ball?_

The initial challenge asks which team has possession of the ball in every frame of a football match, using the
tracking data and homography provided by the organisers. Every frame gets one label: `H` home, `A` away, `D` dead
ball or `X` no answer. Ranking is by `spellF1` — whole possessions recovered — with the baseline at **0.2433**.

Our objective is to build a reliable, reproducible and measurable solution, validate our assumptions, and improve it
through controlled experiments.

<img alt="Animated, simulated tracking: 22 players and the ball, with the possession label switching between home, away and dead ball." src="https://raw.githubusercontent.com/GTT-TalentArena/.github/main/profile/assets/pitch.svg" width="100%">

<sub>Simulated players, not match data.</sub>

<sub><code>02 — THE SQUAD</code></sub>

## The _squad._

| # | Player | Role | Links |
| :-- | :-- | :-- | :-- |
| 01 | **Jimy** | _Pending_ | [GitHub](https://github.com/jimy-k4) · [Portfolio](https://jimy-portfolio.vercel.app/en) · [LinkedIn](https://www.linkedin.com/in/juan-llinares-mauri) |
| 02 | **Edu** | _Pending_ | [GitHub](https://github.com/hxst1) · [Portfolio](https://edu-ruiz-portfolio.vercel.app/) · [LinkedIn](https://www.linkedin.com/in/edu-ruiz-cantos) |
| 03 | **Alejandro Molines** | _Pending_ | [GitHub](https://github.com/AlejandroMolines) · [LinkedIn](https://www.linkedin.com/in/alejandro-molines-00524822b/) |
| 04 | **Nico** | _Pending_ | [GitHub](https://github.com/n1co2611) · [Portfolio](https://nicolashidalgo.es/) · [LinkedIn](https://www.linkedin.com/in/nicolashidalgosalinas/) |
| 05 | **Pablo** | _Pending_ | TBD |

<sub><code>03 — LOG</code></sub>

## Project log

The team log at **[gtt-talentarena.github.io/log](https://gtt-talentarena.github.io/log/)** is our notebook on the
**possession model**: what we study, the improvements we find and the tests we run in this repository. It is not a
changelog of the website.

How we work:

1. **Study first**, in a Markdown file under [`docs/`](.) of this repository. Everything is written in English
   (see [CONTRIBUTING.md](../CONTRIBUTING.md)); the earlier studies were written in Spanish and have an English
   version next to them.
2. When it is clear, and **before writing any code**, publish what we found and the proposed improvements as a log
   entry in English, linking that file.
3. Then code and test here, and log every experiment and iteration with its result — including the failures —
   linking the commit or pull request.

Current focus: H/A/D/X rules, possession changes, temporal continuity, hysteresis, minimum duration, smoothing, and
the state of the art. To add an entry (by hand or with an LLM), follow the instructions at the top of
[`lib/log.ts`](https://github.com/GTT-TalentArena/gtt-talentarena.github.io/blob/main/lib/log.ts) in the website
repository. Aggregate metrics and conclusions only: never match data.

<sub><code>04 — APPROACH</code></sub>

## Technical approach

TBD

## Repository structure

TBD — the upstream layout is described in the [root README](../README.md#what-is-in-this-repository).

### P0 · Integration and evaluation

[Status and verification](P0.en.md) · [Data contract](CONTRATO_DATOS.en.md) · [Run guide](EJECUCION.en.md) · [Docker environment](DOCKER.en.md).

P2: [experimental stoppage and restart detector](experimentos/P2_DEAD_BALL.en.md): signals, tests and a controlled comparison.

Studies and experiments: [possession model study](ESTUDIO_POSESION.en.md) · [P1 hold](experimentos/P1_HOLD.en.md) · [temporal control](experimentos/CONTROL_TEMPORAL.en.md) · [candidate face-off protocol](experimentos/confrontacion-candidatos.en.md).

Local tools: [2D match viewer](LOCAL_2D_VIEWER.md), with a fully synthetic animated example, loopback-only tracking playback and optional model labels (#34).

The original Spanish versions sit next to each English file (same name without `.en`).

> 🇬🇧 The P0 and P2 lines above were originally in Spanish: «P0 · Integración y evaluación — Estado y verificación · Contrato de datos · Guía de ejecución · Entorno Docker. P2: detector experimental de interrupciones y reinicios, señales, pruebas y comparación controlada.»

## Development principles

- **Reproducible** _by default._ — Every number we report regenerates from the repository with one command.
- **Measure** _before we believe._ — `spellF1` and `macroF1` on the public window, plus our own validation.
- **Know why** _it fails._ — Tracking gaps, identity switches, an invisible ball: we study the failure modes.
- **Built** _together._ — Small pull requests, written decisions, shared notebooks. Five people, one codebase.

## Project status

**Status:** Initial challenge — development in progress.

This repository is **public**, as the rules require for the submission repository. The match data is never committed:
`data/` is git-ignored, and so is anything that could reconstruct it ([RULES.md](../RULES.md#the-data)).

## About More than a Hack

More than a Hack 2027 brings together football analytics, technology and real match data at Talent Arena.

- [Official challenge website](https://landing.mobileworldcapital.com/more-than-a-hack-2027)
- [Project guide](GUIA_PROYECTO.en.md) ([Spanish original](GUIA_PROYECTO.md))
- [GTT organisation on GitHub](https://github.com/GTT-TalentArena)
- [GTT website](https://gtt-talentarena.github.io)

---

<p align="center"><i>Més que dades.</i> · <b>GTT — TalentArena</b></p>
