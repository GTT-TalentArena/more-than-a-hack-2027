# Confrontación de candidatos: protocolo (#26, sección 1)

> Acordado el 21-O-2026 en llamada por Jimy (candidato A), Edu (candidato B) y Alejandro (evaluador neutral).
> El brief común está en [`prompts/confrontacion/BRIEF.md`](../../prompts/confrontacion/BRIEF.md).
>
> Lo redactó el autor del candidato A con Opus, y lo revisaron en la llamada los otros dos. Cualquier cambio
> posterior se registra como desviación en la sección D.

Dos candidatos independientes estiman H/A/D/X para el partido del reto: el **A**, desarrollado por Jimy con Claude
Opus 5.5, y el **B**, desarrollado por Edu con ChatGPT-6 Astra. Este documento fija las reglas **antes de escribir
código** y los criterios **antes de ver ninguna puntuación**.

---

## A. Acuerdos

| # | Tema | Acuerdo |
|---|---|---|
| A1 | **Evaluador neutral** | Alejandro; Nico de suplente |
| A2 | **Calendario de la ronda 1** | Brief congelado el **22-O** · candidatos congelados el **29-O 23:59** · comparación del **30 al 31-O** · decisión para #17 el **1-N** |
| A3 | **Tiempo por candidato** | **8 h de tiempo activo** cada uno, apuntadas en un registro de horas. Lo que se pase se anota como desviación |
| A4 | **Herramienta** | Cada uno usa la mejor herramienta agéntica de su proveedor: Claude Code + Opus 5.5 (effort max) y ChatGPT-6 Astra con su agente de código. Se declaran modelo, versión y ajustes de razonamiento |
| A5 | **Cuánto interviene el humano** | **El LLM escribe todo el código.** El humano da instrucciones, ejecuta en local y devuelve resultados permitidos (A7). Puede corregir a mano cosas triviales (rutas, typos), pero debe anotarlas |
| A6 | **Entradas comunes** | `main` tal como esté el 22-O: kit del reto (`starter/`, `games.py`, `evaluation/`, docs), el estudio `docs/ESTUDIO_POSESION.md` y el brief. Los dos pueden usar tracking, homografía, Smart Tagging y vídeo táctico, procesados en local |
| A7 | **Qué puede volver al LLM** | Tracebacks sin datos, métricas agregadas (spellF1/macroF1 públicos, número y duración de posesiones, porcentajes) y descripciones en palabras. **Nunca**: filas, frames, extractos ni capturas (T&C del reto, ver `FAQ.md`) |
| A8 | **Uso de la ventana pública** | Se puede puntuar para comprobar que todo funciona, con un **máximo de 5 evaluaciones públicas** por candidato, todas registradas. No se eligen hiperparámetros con ella |
| A9 | **Datos externos** (Sportec/DFL…) | Permitidos para los dos si se declaran y la licencia está comprobada |
| A10 | **Separación** | Ramas `cand/a-opus` y `cand/b-gpt`; nadie mira la rama del otro ni comenta su enfoque hasta la congelación. No se fusionan en `main` hasta que termine la comparación |
| A11 | **Entrega de cada candidato** | `solution/<cand>/` con un comando `python -m solution.<cand> --out <csv>`, `requirements` fijados y < 30 min en un portátil sin GPU. Debe generar 199.319 filas y pasar `validate_submission.py` |
| A12 | **Criterio de decisión** | Sección C |

---

## B. Brief común

En [`prompts/confrontacion/BRIEF.md`](../../prompts/confrontacion/BRIEF.md). Es el primer mensaje de los dos
candidatos, sin cambios.

---

## C. Criterios de comparación

Fijados antes de ver ninguna puntuación. Los aplica el evaluador neutral, en este orden:

1. **Elegibilidad.** El evaluador reproduce el CSV desde la rama congelada (mismo hash en dos ejecuciones), el CSV
   pasa la validación y se respetaron el tiempo y las restricciones. Si un candidato no es elegible, el respaldo es
   el otro o `baseline_smooth50`.
2. **Plausibilidad.** Se comparan número de posesiones, duración mediana y porcentaje de `D` y de `X` en el partido
   completo con los de la referencia (baseline y lo que dice el estudio). Un candidato con el doble de posesiones
   que una cifra razonable tiene el spellF1 limitado por construcción.
3. **Revisión ciega de discrepancias (criterio principal).** Se agrupan los intervalos donde A y B difieren. Se
   sortea una muestra fija de **40 intervalos**, estratificada por tipo (equipo, equipo/D, fronteras). Pablo los
   revisa en el vídeo local **sin saber qué candidato es cada uno** y marca cuál acierta (o ninguno o ambiguo).
   Gana el que acierte significativamente más (test de signos, p < 0,1). La revisión solo sirve para evaluar: no
   se corrige ninguna etiqueta del CSV, y se declara en el documento técnico.
4. **Ventana pública.** spellF1 y macroF1 con `--bootstrap 1000`. Solo cuenta si los intervalos **no** se solapan.
   Si se solapan, no desempata.
5. **Si nada decide** → resultado inconcluso. Para #17 se lleva el más simple y robusto (menos parámetros, más fácil
   de reproducir), y la combinación queda como ronda 2.

---

## D. Registro

Lo lleva cada autor y lo entrega al congelar su candidato:

- `prompts/confrontacion/<cand>/`: todos los prompts en orden, con fecha. Las respuestas, resumidas o enlazadas.
- Registro de horas: inicio y fin de cada sesión, tiempo activo y qué se hizo.
- Ejecuciones: commit, comando, resultado agregado y si fue una de las evaluaciones públicas de A8.
- Desviaciones del protocolo.

Nada de esto incluye datos del partido ni derivados frame a frame.
