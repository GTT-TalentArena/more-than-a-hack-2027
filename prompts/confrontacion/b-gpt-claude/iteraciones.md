# Iteraciones del candidato B (v0 y variante + Claude)

Una fila por evaluación pública (A8, máximo 5, cupo compartido entre la v0 y la variante). Pedida por Alejandro para la comparación.

| Iteración | Versión · commit | Cambio respecto a la anterior | 1. spellF1 público [IC 90 %] | 2. macroF1 público | 3. Posesiones ventana (GT 17) | 4. % D partido completo | 5. Posesiones partido completo |
|---|---|---|---|---|---|---|---|
| 1 | v0 (solo Codex) · `1c96afa` (tag `b-gpt-v0`) | — (primera versión) | 0.3895 [0.242, 0.537] | 0.6620 | 21 | 33.41 % | 354 |
| 2 | v1 (+ Claude) · `02bda8f` | Balón perdido tras salir del campo = parada | 0.3895 [0.242, 0.537] | 0.6620 | 21 | 35.19 % | 347 |
| 3 | v2 (+ Claude) · `6b83b32` | Huecos largos sin balón (≥ 5 s, jugadores seguidos) = parada | 0.3122 [0.185, 0.449] ⚠️ | 0.6652 | 24 | 47.76 % | 345 |
| 4 | v3 (+ Claude) · `13ffe9b` | Solo los huecos sin balón que empiezan o acaban como un saque (balón tapado o en vuelo = juego vivo) | 0.3895 | **0.6901** [0.470, 0.822] | 21 | 41.05 % | 340 |
| 5 | v4 (+ Claude, effort max) · `8ae2aa5` | Un toque no es un cambio: tramo del rival < 3 s entre dos del mismo equipo, sin parada, vuelve al que tenía el balón | **0.4000** [0.213, 0.587] | **0.6983** [0.472, 0.836] | 13 | 41.05 % | 220 |

Referencias: `baseline_smooth50` en la ventana pública = spellF1 0.3256 [0.214, 0.447] · macroF1 0.6207 · 26 posesiones.

**Cómo leerla.**
- 1–3 son la ventana pública de 5 min: diferencias de spellF1 por debajo de ~0,06 equivalen a una sola posesión (ruido).
- 4–5 son del partido completo y no usan GT. La referencia del % D es el tiempo efectivo de LaLiga (≈ 54 min; Barça 2024/25 ≈ 57,8 min) sobre ≈ 106 min puntuados, es decir ≈ 45–49 % de D. Es una referencia de dirección, no un objetivo de ajuste: el GT marca D según el tracking corregido, que puede no coincidir con el árbitro.
- El criterio principal de Alejandro es la revisión ciega en vídeo; esta tabla solo muestra la evolución.

**Iteración 3 (v2), resultado mixto.** En el partido completo hace lo previsto (D 35 → 48 %, en la horquilla del tiempo efectivo). En la ventana pública, D recall sube (0,257 → 0,406) pero la precisión de D cae (0,997 → 0,589): parte de los huecos largos son juego vivo según el GT, parten posesiones (21 → 24, GT 17) y spellF1 baja 0,077 (más de una posesión). macroF1 se mantiene (0,6620 → 0,6652).

**Iteración 4 (v3), mejora sobre la v1 según el criterio fijado antes.** spellF1 igual (0,3895) y macroF1 +0,028 (0,6620 → 0,6901). En la ventana: precisión de D 0,998 (como la v1), recall de D 0,257 → 0,317, F1 de D 0,409 → 0,481, mismos 21 posesiones y 23 segmentos que la v1. En el partido completo, D 41,05 %. Cautela: los intervalos se solapan y la idea es posterior a la evaluación #3 (ver desviaciones).

Desglose de D en la ventana pública:

| Versión | Precisión D | Recall D | F1 D | Segmentos (GT 21) |
|---|---|---|---|---|
| v1 | 0.997 | 0.257 | 0.409 | 23 |
| v2 | 0.589 | 0.406 | 0.481 | 29 |
| v3 | 0.998 | 0.317 | 0.481 | 23 |

**Iteración 5 (v4): pasa el criterio fijado y es la versión final de la variante.** spellF1 0,3895 → 0,4000 y macroF1 0,6901 → 0,6983, ambas mejoras por debajo del ruido de la ventana. Acierto de equipo con balón vivo 0,860 → 0,873. F1 por umbral de IoU: a 0,3–0,4 sube (0,474 → 0,533); a 0,5–0,7 baja ligeramente (0,474 → 0,467, 0,316 → 0,267, 0,211 → 0,200). Posesiones en la ventana 21 → 13 (GT 17): la regla de 3 s quita cambios falsos, pero también funde algunas posesiones cortas reales. Es la principal incertidumbre de la v4. No se ajusta (no quedan evaluaciones públicas y sería sobreajustar a 17 posesiones); queda para el documento técnico y la siguiente ronda.

**Resumen de la variante:** v0 (Codex) → v4 (Codex + Claude), spellF1 0,3895 → 0,4000 y macroF1 0,6620 → 0,6983 en la ventana pública (smooth50: 0,3256 / 0,6207). Las 5 evaluaciones públicas del candidato B están usadas.
