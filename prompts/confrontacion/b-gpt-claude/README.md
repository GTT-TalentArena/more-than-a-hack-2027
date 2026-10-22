# Variante B + Claude (v1)

| campo | valor |
|---|---|
| Qué es | Candidato B v0 (tag `b-gpt-v0`, commit `1c96afa`: solo Codex, ChatGPT-6 Astra high) **más mejoras escritas por Claude** |
| Rama | `cand/b-gpt-claude`, sacada del tag `b-gpt-v0` |
| Operador | Edu (`hxst1`) |
| Herramienta | Claude Code |
| Modelo | Claude Opus 5.5 (`claude-opus-5-5`, contexto de 1M). Effort **medium** hasta las 22:18 del 2026-10-21 (v1–v3); **max** desde las 22:18 (v4) |
| Aprobación | Alejandro (evaluador neutral, A1), por WhatsApp el 2026-10-21 a las 21:33: «Me parece bien · Muy buena idea» |
| Comando de entrega | `python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv` |
| Paquete | `solution/b_gpt/` (mismo paquete; el cambio está descrito en su README, sección «Variante v1») |

Versiones de la variante: **v1** (`02bda8f`, balón perdido tras salir del campo = parada) y **v2** (huecos largos sin balón = parada). Detalle en el README del paquete.

Objetivo: comparar tres resultados en la ronda 1 — **A** (Opus), **B v0** (solo GPT) y **B + Claude** — y medir si una IA mejora lo que hizo la otra. La v0 se conserva intacta en su tag.

Mismas restricciones que el resto del protocolo (A5–A8): Claude no ha visto los datos del partido ni ningún CSV de etiquetas reales; solo código, documentación y datos sintéticos. Edu ejecuta en local y devuelve solo agregados.

Análisis de la v4: [analisis-v4.md](analisis-v4.md) · Iteraciones: [iteraciones.md](iteraciones.md)

**Resultado de la comparación (22-O):** Alejandro eligió el candidato A. En la ventana pública, A v1.6: spellF1 0.5250 · macroF1 0.8391; B v4: 0.4000 · 0.6983. Resultados por versión: [resultados.csv](resultados.csv).

Registro: [prompts.md](prompts.md) · [horas.md](horas.md) · [ejecuciones.md](ejecuciones.md) · [desviaciones.md](desviaciones.md)
