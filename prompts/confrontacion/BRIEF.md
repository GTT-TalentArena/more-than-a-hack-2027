# Brief común de la confrontación (#26)

Es el primer mensaje que recibe el LLM de cada candidato, **idéntico** para los dos. Después, cada autor puede
añadir sus propios prompts, pero todos se guardan en `prompts/confrontacion/<cand>/`. El protocolo está en
[`docs/experimentos/confrontacion-candidatos.md`](../../docs/experimentos/confrontacion-candidatos.md).

Congelado el 22-O-2026. Si se cambia, se anota como desviación en los dos candidatos.

---

**Tarea.** Para el partido FC Barcelona – Athletic Club (LaLiga 2024-25), produce una etiqueta por frame del
**vídeo táctico** (199.319 frames, 25 fps): `H` posesión local con el balón en juego, `A` posesión visitante con
el balón en juego, `D` balón parado o fuera, `X` sin respuesta. Las reglas completas están en `CHALLENGE.md`, y la
métrica (spellF1, que premia posesiones completas, y macroF1) en `EVALUATION.md` y
`evaluation/possession_metrics.py`.

**Entradas.** Las de `DATA.md`: tracking automático (ATD) con jugadores y balón, homografía y Smart Tagging del
vídeo táctico, y el propio vídeo; opcionalmente, la retransmisión, que no está sincronizada. Las rutas se obtienen
con `games.asset_paths()`. Hay loaders en `starter/`, un estudio previo en `docs/ESTUDIO_POSESION.md` y un baseline
en `starter/baseline.py` (spellF1 0,2433 en el partido completo).

**Restricción de datos (obligatoria).** No puedes ver los datos del partido ni ningún extracto. Escribe el código a
partir de la documentación y prueba con datos sintéticos. Yo lo ejecuto en local y te devuelvo solo errores y
métricas agregadas. No escribas código que imprima filas de datos.

**Entrega.** Un paquete `solution/<cand>/` ejecutable con un solo comando, que escriba un CSV `frame,label` de
199.319 filas que pase `python evaluation/validate_submission.py`. Fija las dependencias. Debe tardar menos de
30 min en CPU. Documenta el método en `solution/<cand>/README.md`.

**Reglas del reto.** Las etiquetas salen de un algoritmo, nunca a mano. No se puede usar la ground truth privada.
La ventana pública de 5 minutos (17 posesiones) sirve para comprobar que todo funciona, no para ajustar parámetros.

**Objetivo.** Maximizar el spellF1 del partido completo, que no podemos medir. Razona qué generaliza, no qué puntúa
en los 5 minutos públicos.
