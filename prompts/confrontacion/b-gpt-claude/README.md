# Variante B + Claude (v1)

| campo | valor |
|---|---|
| Qué es | Candidato B v0 (tag `b-gpt-v0`, commit `1c96afa`: solo Codex, ChatGPT-6 Astra high) **más mejoras escritas por Claude** |
| Rama | `cand/b-gpt-claude`, sacada del tag `b-gpt-v0` |
| Operador | Edu (`hxst1`) |
| Herramienta | Claude Code |
| Modelo | Claude Opus 5.5 (`claude-opus-5-5`, contexto de 1M), effort **medium** |
| Aprobación | Alejandro (evaluador neutral, A1), por WhatsApp el 2026-10-21 a las 21:33: «Me parece bien · Muy buena idea» |
| Comando de entrega | `python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv` |
| Paquete | `solution/b_gpt/` (mismo paquete; el cambio está descrito en su README, sección «Variante v1») |

Objetivo: comparar tres resultados en la ronda 1 — **A** (Opus), **B v0** (solo GPT) y **B + Claude** — y medir si una IA mejora lo que hizo la otra. La v0 se conserva intacta en su tag.

Mismas restricciones que el resto del protocolo (A5–A8): Claude no ha visto los datos del partido ni ningún CSV de etiquetas reales; solo código, documentación y datos sintéticos. Edu ejecuta en local y devuelve solo agregados.

Registro: [prompts.md](prompts.md) · [horas.md](horas.md) · [ejecuciones.md](ejecuciones.md) · [desviaciones.md](desviaciones.md)
