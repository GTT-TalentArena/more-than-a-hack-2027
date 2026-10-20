<a href="https://gtt-talentarena.github.io">
  <img alt="GTT — Més que dades (more than data). Football analytics team at More than a Hack 2027." src="https://raw.githubusercontent.com/GTT-TalentArena/.github/main/profile/assets/banner.png" width="100%">
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

Every study, experiment (including the failed ones), iteration and decision goes into the team log:
**[gtt-talentarena.github.io/log](https://gtt-talentarena.github.io/log/)**.

To add an entry — by hand or with an LLM — create one Markdown file in
[`GTT-TalentArena/gtt-talentarena.github.io/content/log/`](https://github.com/GTT-TalentArena/gtt-talentarena.github.io/tree/main/content/log)
following the instructions at the top of
[`lib/log.ts`](https://github.com/GTT-TalentArena/gtt-talentarena.github.io/blob/main/lib/log.ts). Aggregate metrics
and conclusions only: never match data.

<sub><code>04 — APPROACH</code></sub>

## Technical approach

TBD

## Repository structure

TBD — the upstream layout is described in the [root README](../README.md#what-is-in-this-repository).

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
- [Project guide (ES)](GUIA_PROYECTO.md)
- [GTT organisation on GitHub](https://github.com/GTT-TalentArena)
- [GTT website](https://gtt-talentarena.github.io)

---

<p align="center"><i>Més que dades.</i> · <b>GTT — TalentArena</b></p>
