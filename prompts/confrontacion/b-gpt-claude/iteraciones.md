# Iteraciones del candidato B (v0 y variante + Claude)

Una fila por evaluación pública (A8, máximo 5, cupo compartido entre la v0 y la variante). Pedida por Alejandro para la comparación.

| Iteración | Versión · commit | Cambio respecto a la anterior | 1. spellF1 público [IC 90 %] | 2. macroF1 público | 3. Posesiones ventana (GT 17) | 4. % D partido completo | 5. Posesiones partido completo |
|---|---|---|---|---|---|---|---|
| 1 | v0 (solo Codex) · `1c96afa` (tag `b-gpt-v0`) | — (primera versión) | 0.3895 [0.242, 0.537] | 0.6620 | 21 | 33.41 % | 354 |
| 2 | v1 (+ Claude) · `02bda8f` | Balón perdido tras salir del campo = parada | 0.3895 [0.242, 0.537] | 0.6620 | 21 | 35.19 % | 347 |
| 3 | v2 (+ Claude) · `6b83b32` | Huecos largos sin balón (≥ 5 s, jugadores seguidos) = parada | 0.3122 [0.185, 0.449] ⚠️ | 0.6652 | 24 | 47.76 % | 345 |
| 4 | | | | | | | |
| 5 | | | | | | | |

Referencias: `baseline_smooth50` en la ventana pública = spellF1 0.3256 [0.214, 0.447] · macroF1 0.6207 · 26 posesiones.

**Cómo leerla.**
- 1–3 son la ventana pública de 5 min: diferencias de spellF1 por debajo de ~0,06 equivalen a una sola posesión (ruido).
- 4–5 son del partido completo y no usan GT. La referencia del % D es el tiempo efectivo de LaLiga (≈ 54 min; Barça 2024/25 ≈ 57,8 min) sobre ≈ 106 min puntuados, es decir ≈ 45–49 % de D. Es una referencia de dirección, no un objetivo de ajuste: el GT marca D según el tracking corregido, que puede no coincidir con el árbitro.
- El criterio principal de Alejandro es la revisión ciega en vídeo; esta tabla solo muestra la evolución.

**Iteración 3 (v2), resultado mixto.** En el partido completo hace lo previsto (D 35 → 48 %, en la horquilla del tiempo efectivo). En la ventana pública, D recall sube (0,257 → 0,406) pero la precisión de D cae (0,997 → 0,589): parte de los huecos largos son juego vivo según el GT, parten posesiones (21 → 24, GT 17) y spellF1 baja 0,077 (más de una posesión). macroF1 se mantiene (0,6620 → 0,6652).
