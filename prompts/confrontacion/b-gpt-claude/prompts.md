# Prompts (variante B + Claude)

Mensajes de Edu a Claude Code en esta variante, en orden. Las respuestas, resumidas.

## 1. 2026-10-21 · ~21:31
> vale si consideras que podríamos añadir alguna mejora, tienes que hacerla tu, y lo anotamos que hemos usado claude para la mejora, y asi comparamos tambien el resultado solo de codex el v0 y con la mejora el v1

**Respuesta:** Claude avisó de que mezclar proveedores cambia el protocolo y propuso una variante aparte (tag `b-gpt-v0` + rama `cand/b-gpt-claude` + registro propio), condicionada a la aprobación de Alejandro.

## 2. 2026-10-21 · 21:33
> (captura de WhatsApp) Alejandro: «Me parece bien» · «Muy buena idea»

**Respuesta:** Claude creó el tag `b-gpt-v0` y la rama, leyó el código de `solution/b_gpt/` (no los datos) y propuso un único cambio justificado por las reglas del juego: tratar como parada el hueco de tracking que sigue a una salida clara del balón del campo.

## 3. 2026-10-21 · durante la sesión
> anota la hora de entrada y salida, y el modelo, estas en Opus 5.5 y el effort no estoy seguro

> el effort esta en medium

**Respuesta:** Claude implementó el cambio con 3 tests sintéticos (el principal falla con la v0 y pasa con la v1), comprobó el determinismo con 199.319 frames sintéticos, documentó la variante y abrió este registro.

## 4. 2026-10-21 · 21:46
> (captura de WhatsApp) Alejandro: «Te quedan 4» · «Y las horas cuentan dentro»

**Respuesta:** Claude anotó en el registro que el cupo público y las horas son compartidos con el candidato B.

## 5. 2026-10-21 · evaluación pública
> (Edu pega la tabla de la evaluación pública #2 de la v1)

**Respuesta:** Claude constató que la v1 da exactamente los mismos números que la v0 en la ventana pública (0.3895 / 0.6620 / 21 posesiones), lo registró como evaluación #2 de 5 y concluyó, con el criterio fijado de antemano, que no se distingue en esa ventana.

## 6. 2026-10-21 · ~21:50
> (nueva sesión) como va  →  (Edu pega el hash y el bloque `dead_time_diagnostics` de la ejecución #4)

**Respuesta:** Claude observó que casi no hay huecos cortos sin balón y que los 132 huecos de ≥ 5 s (~43 min) encajan en número y duración con las paradas de un partido; implementó la v2 (huecos largos sin balón con jugadores seguidos = evidencia de parada; corte total de datos ≠ parada), adaptó 4 tests de la v0 que asumían lo contrario y añadió 3.

## 7. 2026-10-21 · durante la sesión
> Molines me dice, cuando hayamos hecho las 5 iteraciones me tienes que dar una tabla las 5 variables mas importantes y todas las iteraciones 1,2,3,4,5 y los valores para que se vea el cambio

**Respuesta:** Claude creó `iteraciones.md` con 5 variables (spellF1, macroF1 y posesiones públicas; % D y posesiones del partido completo).

## 8. 2026-10-21 · ~22:05
> diria que la B, lo que hay que tener en cuenta es si un jugador esta de espaldas con el valon a la camara, ahi desapareceria el valon tambien no crees? no se si se tiene en cuenta

**Respuesta:** Claude confirmó que la v2 no lo distinguía e implementó la v3: el hueco solo es parada si el balón se pierde junto a una línea, reaparece quieto o junto a una línea, o el hueco dura > 30 s; si reaparece moviéndose dentro del campo (balón tapado por un jugador o en vuelo) es juego vivo. 3 tests nuevos (el del balón tapado falla con la v2); determinismo sintético.

## 9. 2026-10-21 · 22:18 (effort max)
> No podemos subir nada aun, todo tiene que permanecer en local,
>
> Effort cambiado a max (mismo modelo, Opus 5.5). Objetivo: v4 de la variante B + Claude (rama cand/b-gpt-claude, partiendo de la v3, commit 56d1b29).
> 1. Primero, anota en prompts/confrontacion/b-gpt-claude/ (desviaciones.md, README.md y horas.md) el cambio de effort de medium a max, con la hora.
> 2. Haz un análisis sin mirar los datos: lee el código de solution/b_gpt/, la documentación pública del reto (CHALLENGE.md, DATA.md, EVALUATION.md, FAQ.md) y busca en internet literatura de detección de posesión y balón parado con tracking. Haz una lista de casos y variables de fútbol que el modelo aún no cubre (reglas del juego, reanudaciones, porteros, duelos, etc.), con la justificación de cada uno y el riesgo de sobreajuste.
> 3. Propónme las mejoras ordenadas por fundamento, antes de programarlas. Valídalas primero con diagnósticos del partido completo sin GT, que puedo ejecutar yo sin gastar evaluaciones públicas.
> 4. Solo queda 1 evaluación pública. Criterio fijado antes de usarla: si la v4 no mejora a la v3 (spellF1 ≥ 0.3895 y macroF1 ≥ 0.6901), se congela la v3.
> Reglas de siempre: no leer ni ejecutar nada con los datos del partido; código, documentación y datos sintéticos; yo ejecuto en local y te paso solo agregados; no mirar la rama cand/a-opus.

**Respuesta:** ver [analisis-v4.md](analisis-v4.md): casos no cubiertos, propuestas ordenadas por fundamento y diagnósticos sin GT para dimensionarlas antes de programarlas.

## 10. 2026-10-21 · ~22:28
> (Edu pega el hash y el bloque `v4_diagnostics` de la ejecución #9)

**Respuesta:** Claude aplicó los criterios fijados: P1 y P2 no entran, P3 y P6 cumplen pero no se aplican (desviación razonada), P4 entra. Implementó la v4 (un tramo de < 3 s del rival entre dos del mismo equipo, sin parada, vuelve al equipo que tenía el balón), adaptó 2 tests de la v0 que asumían lo contrario y añadió 4.

## 11. 2026-10-21 · ~22:40
> (Edu pega las dos ejecuciones de la v4, los hashes y el bloque de estructura)

**Respuesta:** Claude comprobó que la v4 cumple todas las expectativas fijadas antes de ejecutarla y dio paso a la evaluación pública #5.

## 12. 2026-10-21 · ~22:45
> si no me equivoco mis compañeros estan haciendo estudios crees que deveriamos lanzar las evaluaciones sin esperar los estudios de los compañeros?

**Respuesta:** Claude recomendó aplazar la evaluación #5 (la última) hasta el corte de entradas comunes del 22-O, para gastarla en la versión que se congele; en `main` solo está el estudio común ya conocido (`docs/ESTUDIO_POSESION.md`) y no hay PRs abiertas. Recordó que lo que estudie el candidato A no puede consultarse hasta la congelación (A10) y propuso preguntar a Alejandro si los estudios publicados después del 22-O cuentan en esta ronda.

## 13. 2026-10-21 · ~22:50
> (Edu pega la tabla de la evaluación pública #5 de la v4)

**Respuesta:** Claude constató que la v4 cumple el criterio fijado y pasa a ser la versión final de la variante, y explicó que las mejoras son menores que el ruido y que la v4 da menos posesiones que el GT (13 frente a 17). No ajusta el umbral de 3 s para no sobreajustar a la ventana. Registró la iteración 5 y cerró la tabla de iteraciones.
