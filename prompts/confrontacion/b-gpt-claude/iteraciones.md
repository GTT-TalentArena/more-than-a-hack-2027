# Iteraciones del candidato B (v0 y variante + Claude)

Una fila por evaluación pública (A8, máximo 5, cupo compartido entre la v0 y la variante). Pedida por Alejandro para la comparación.

| Iteración | Versión · commit | Cambio respecto a la anterior | 1. spellF1 público [IC 90 %] | 2. macroF1 público | 3. Posesiones ventana (GT 17) | 4. % D partido completo | 5. Posesiones partido completo |
|---|---|---|---|---|---|---|---|
| 1 | v0 (solo Codex) · `1c96afa` (tag `b-gpt-v0`) | — (primera versión) | 0.3895 [0.242, 0.537] | 0.6620 | 21 | 33.41 % | 354 |
| 2 | v1 (+ Claude) · `02bda8f` | Balón perdido tras salir del campo = parada | 0.3895 | 0.6620 | 21 | 35.19 % | 347 |
| 3 | | | | | | | |
| 4 | | | | | | | |
| 5 | | | | | | | |

Referencias: `baseline_smooth50` en la ventana pública = spellF1 0.3256 [0.214, 0.447] · macroF1 0.6207 · 26 posesiones.

**Cómo leerla.**
- 1–3 son la ventana pública de 5 min: diferencias de spellF1 por debajo de ~0,06 equivalen a una sola posesión (ruido).
- 4–5 son del partido completo y no usan GT. La referencia del % D es el tiempo efectivo de LaLiga (≈ 54 min; Barça 2024/25 ≈ 57,8 min) sobre ≈ 106 min puntuados, es decir ≈ 45–49 % de D. Es una referencia de dirección, no un objetivo de ajuste: el GT marca D según el tracking corregido, que puede no coincidir con el árbitro.
- El criterio principal de Alejandro es la revisión ciega en vídeo; esta tabla solo muestra la evolución.
