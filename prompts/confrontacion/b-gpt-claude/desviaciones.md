# Desviaciones (variante B + Claude)

- **Variante fuera del diseño original.** El protocolo enfrenta A (Opus) contra B (GPT); esta variante mezcla los dos proveedores a propósito. Aprobada por Alejandro (evaluador, A1) el 2026-10-21 a las 21:33. La v0 de B se conserva intacta en el tag `b-gpt-v0`.
- **Herencia de la v0.** La v0 ya declara en su registro que algunos prompts a Codex se redactaron con ayuda de Claude.
- **Cupo público y horas.** Decidido por Alejandro el 2026-10-21 (21:45–21:46): esta variante **comparte** las 5 evaluaciones públicas del candidato B (quedan 4) y sus horas **cuentan dentro** de las 8 h del B.
- **Separación (A10).** Claude no ha mirado la rama `cand/a-opus` ni conoce el enfoque del candidato A.
- **v3 inspirada por la ventana pública.** La regla de la v3 (un hueco sin balón solo es parada si empieza o acaba como un saque) se pensó **después** de ver el desglose agregado de la evaluación pública #3 (precisión y recall de D). Es una regla de fútbol, no un parámetro ajustado, y la propuesta del caso «jugador de espaldas que tapa el balón» la aportó Edu; aun así, existe riesgo de sobreajuste a las 17 posesiones públicas. Criterio fijado antes de evaluarla: si no mejora claramente a la v1, la versión final de la variante es la v1.
- **Cambio de effort (22:18).** Para la v4, Edu subió el effort de Claude Code de **medium** a **max** (mismo modelo, Opus 5.5). Se intentó cambiar a Fable 5.1, pero no estaba disponible. v1–v3 se hicieron con effort medium.
- **Todo en local.** Por indicación del equipo, nada de esta variante (ramas, tag, registro) se sube a GitHub hasta nuevo aviso.
