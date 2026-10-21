# Análisis para la v4 (Claude Opus 5.5, effort max · 2026-10-21)

Hecho sin ver los datos: código de `solution/b_gpt/` (v3), documentación pública del reto
(`CHALLENGE.md`, `DATA.md`, `EVALUATION.md`, `FAQ.md`), literatura y Reglas de Juego. Los únicos
números del partido que se usan son agregados ya registrados en `ejecuciones.md`.

## 0. Punto de partida: dónde falla la v3

Agregados de la evaluación pública #4 (ventana de 5 min; GT: H 3.454 · A 2.577 · D 1.469 frames,
17 posesiones, 21 segmentos, es decir 4 tramos de `D`). Se usan para **entender** los fallos, no
para ajustar nada:

- **`D` perdido.** Precisión de `D` 0,998 y recall 0,317: lo que la v3 llama `D` casi siempre lo
  es, pero se le escapan ≈ 1.000 frames (≈ 40 s) de los 1.469 de `D`. Detecta 2 tramos de `D`
  (23 segmentos − 21 posesiones) de los 4 del GT.
- **Equipo equivocado.** Acierto de equipo con balón vivo 0,860: ≈ 34 s con el equipo cambiado,
  y 21 posesiones frente a 17, así que hay cambios H↔A de más.
- En el partido completo (sin GT): `D` 41 %, 340 posesiones.

Ojo: en la v2 vimos que los huecos sin balón que reaparecen moviéndose dentro del campo son, en su
mayoría, juego vivo. El `D` que falta tiene que estar sobre todo **donde el balón sí se ve**: el
balón que rueda hacia fuera, el que se coloca para el saque, el del lanzador de banda.

## 1. Lo que dice el reto

- El GT es **mecánico**: `D` donde el tracking corregido marca el balón muerto; si no, el equipo
  que ese tracking nombra como dueño. Un balón muerto va **desde la salida o el pitido hasta el
  saque**, aunque el tracking automático vea el balón todo el rato.
- **Cambio de posesión = un rival gana posesión controlada.** En fases disputadas o con el balón
  suelto, la posesión se queda con el último equipo. No son cambio: un toque sin control, un
  desvío que no intercepta y un duelo aéreo ganado sin control posterior.
- El tracking automático pierde el balón por oclusiones, áreas abarrotadas y balones en el aire.

## 2. Literatura y Reglas de Juego

- **Vidal-Codina et al. (2022)**, detección de eventos con tracking:
  - zona de posesión de **0,5–1 m** alrededor del jugador;
  - **zona de duelo de 1 m** alrededor del balón: con dos rivales dentro hay duelo, y **el duelo
    prevalece sobre la posesión**;
  - una **ganancia de posesión exige contacto**, medido como cambio de dirección o de velocidad
    del balón dentro de la zona; si no cambia, el balón solo pasó cerca;
  - algunos proveedores marcan el balón muerto dejándolo sin datos.
- **Link y Hoernig (2017)**: posesión individual a partir de fases de control (esfera de
  influencia, distancia, velocidad y aceleración del balón), con una red bayesiana para el grado de
  control.
- **PathCRF (Kim et al., 2026)**: infiere la posesión **sin balón**, desde las trayectorias de
  los jugadores, con un CRF y decodificación de Viterbi.
- **Reglas de Juego (IFAB)**:
  - saque de centro (Regla 8), faltas (13) y saque de puerta (16) **con el balón quieto**;
  - el balón está en juego cuando se golpea y **se mueve claramente** (Regla 8);
  - el portero puede retener el balón con las manos unos segundos (Regla 12: 6 s en 2024-25; 8 s
    y córner desde 2025-26).
- **Duración media de las paradas**: saque de banda ≈ 13 s, saque de puerta ≈ 17 s, falta ≈ 21–23 s,
  córner ≈ 27 s, saque de centro ≈ 37–46 s (estudio de PMC). En la Premier, saque de banda de
  15–18 s (The Analyst).

## 3. Casos que la v3 no cubre

| # | Caso | Qué hace la v3 | Qué dicen el reto, las reglas o la literatura | Riesgo de sobreajuste |
|---|---|---|---|---|
| 1 | **Duelo**: jugadores de los dos equipos a ≤ 1 m del balón | El rival un poco más cercano acumula evidencia y puede cambiar la posesión | Reto: en fases disputadas se mantiene el último equipo. Literatura: el duelo prevalece, con radio de 1 m | **Bajo**: regla escrita en el reto y parámetro de la literatura |
| 2 | **Balón colocado** para un saque, visible y quieto | Solo es `D` si además los jugadores están casi parados (< 1,2 m/s durante 2 s); con jugadores moviéndose, cuenta como vivo | Reglas 8, 13 y 16: se saca con el balón quieto. En juego, fuera de las manos del portero, el balón no se queda quieto segundos | **Bajo–medio**: hay que excluir al portero con el balón en las manos (área grande) |
| 3 | **Salida de `D` con el balón aún quieto** | Puede salir de `D` si los jugadores corren y hay alguien cerca del balón | Regla 8: en juego cuando se golpea y se mueve claramente | **Bajo** |
| 4 | **Saque junto a la línea y balón perdido justo después** (banda o córner ya sacado) | El hueco cuenta como `D` (`lost_at_line`) aunque el balón ya esté en juego | El balón entró en el campo: el saque ya se hizo | **Bajo**: elimina un `D` falso posible |
| 5 | **Balón que reaparece junto a la línea en carrera** (extremo pegado a la banda) | El hueco previo cuenta como `D` (`back_at_line`) | Un saque de banda o de córner reaparece en manos o colocado, no en carrera | **Bajo** |
| 6 | **Portero que suelta el balón y juega** (reaparece lento y enseguida se mueve) | `back_still` marca el hueco como `D` | Un balón colocado para un saque sigue quieto varios segundos | **Bajo** |
| 7 | **Ganar la posesión sin contacto** (el pase pasa cerca de un rival) | Solo baja el peso de los balones rápidos | Literatura: exige cambio de dirección o velocidad | **Medio**: el ruido del balón dificulta medir el cambio; sus umbrales están en material suplementario |
| 8 | **Equipo que saca tras una salida** (regla del último toque) | Lo decide el jugador más cercano tras el saque | Saca el rival del último que tocó | **Bajo**, pero con poco impacto: el que saca suele estar pegado al balón |
| 9 | **Balón aéreo proyectado fuera** de la banda lejana (perspectiva de la cámara) | Cuenta como fuera si pasa 0,35 m de la línea | Un balón en el aire se proyecta más lejos de la cámara de lo que está | **Hipótesis**: comprobar con rebotes «fuera → dentro en < 1 s» por lado |
| 10 | **Posesión durante huecos con juego vivo** (≈ 7 min en la v3) | Mantiene el último equipo hasta que reaparece el balón | PathCRF infiere la posesión desde las trayectorias | **Alto**, y coste alto: fuera de la v4 |
| 11 | **Penalti** (balón quieto en el área) | Igual que el caso 2, pero dentro del área | Raro (0–1 por partido) | Fuera de alcance |

## 4. Propuestas, ordenadas por fundamento

1. **P1 · Duelo = se mantiene el último equipo.** Con un jugador de cada equipo a ≤ 1 m del balón,
   la evidencia de control se anula: nadie puede ganar la posesión en un duelo. Solo puede ganarla
   quien salga de él con el balón. Cubre el caso 1.
2. **P2 · Los saques se hacen con el balón quieto.**
   - **(a)** Un balón visto quieto durante ≥ 2 s es evidencia de parada aunque los jugadores se
     muevan, salvo en el área grande fuera del área chica, donde puede tenerlo el portero en las
     manos.
   - **(b)** No se sale de `D` mientras el balón siga quieto: la parada termina cuando se golpea.

   Cubre los casos 2 y 3.
3. **P3 · Reglas de línea con dirección** (corrige la v3):
   - un balón perdido junto a la línea **moviéndose hacia dentro a > 2 m/s** es un saque ya hecho:
     juego vivo;
   - un balón que reaparece junto a la línea **a > 2 m/s** es juego, no un saque;
   - un balón que reaparece quieto solo cuenta como `D` si **sigue quieto ≥ 1 s**.

   Cubre los casos 4, 5 y 6.
4. **P4 · Contacto para ganar la posesión** (caso 7). Solo si los diagnósticos muestran muchos
   cambios de equipo de ida y vuelta en < 3 s.
5. **P5 · Regla del último toque** (caso 8). Baja prioridad.
6. **P6 · Perspectiva en la banda lejana** (caso 9). Solo si el diagnóstico la muestra.

Fuera de la v4: inferir la posesión sin balón (caso 10) y los penaltis (caso 11).

## 5. Diagnósticos sin GT y criterio para decidir (fijado antes de verlos)

Se añaden a `evidence_totals.v4_diagnostics` del `.summary.json`. Son solo recuentos y minutos, y
no cambian ninguna etiqueta: el CSV de la v3 queda idéntico.

| Propuesta | Diagnóstico | Entra en la v4 si… |
|---|---|---|
| P1 | `duels` (minutos de duelo, cambios H↔A a ≤ 0,5 s de un duelo) y `structure` (idas y vueltas < 3 s) | ≥ 20 % de los cambios H↔A de la v3 ocurren a ≤ 0,5 s de un duelo |
| P2 | `still_ball_by_zone` (minutos con el balón quieto ≥ 1 s etiquetados vivos, por zona) y `dead_exits` (salidas de `D` con el balón quieto y minutos hasta que se mueve) | suman ≥ 1 min etiquetado vivo fuera de la zona del portero |
| P3 | `line_gaps` (huecos `D` por línea perdidos yendo hacia dentro rápido, reaparecidos rápido o que se mueven en < 1 s) | suman ≥ 0,5 min |
| P6 | `out_episodes` (salidas por lado y rebotes «fuera → dentro» en < 1 s) | un lado tiene ≥ 3 veces más rebotes que el opuesto |
| Referencia | `structure.dead_runs` (número y duración de los tramos `D`) | Comparar con la literatura: ≈ 100–130 paradas de 13–27 s |

**Evaluación pública #5 (la última).** La v4 solo se evalúa si sus diagnósticos muestran el efecto
buscado sin efectos colaterales:
- `D` entre 41 % y 49 %;
- no más cambios H↔A que la v3;
- determinista.

Criterio ya fijado: si la v4 no logra **spellF1 ≥ 0,3895 y macroF1 ≥ 0,6901**, se congela la v3.
Pasar ese umbral solo descarta un empeoramiento: con 17 posesiones, no prueba una mejora.

## Fuentes

- Vidal-Codina, Evans, El Fakir, Billingham (2022). *Automatic event detection in football using tracking data*. Sports Engineering. https://arxiv.org/abs/2202.00804
- Link, Hoernig (2017). *Individual ball possession in soccer*. PLOS ONE. https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225
- Kim et al. (2026). *PathCRF: Ball-Free Soccer Event Detection via Possession Path Inference from Player Trajectories*. https://arxiv.org/abs/2602.12080
- IFAB, Reglas de Juego (reproducción de The FA): Regla 8 https://www.thefa.com/football-rules-governance/lawsandrules/laws/football-11-11/law-8---the-start-and-restart-of-play · Regla 13 https://www.thefa.com/football-rules-governance/lawsandrules/laws/football-11-11/law-13---free-kicks · Regla 16 https://www.thefa.com/football-rules-governance/lawsandrules/laws/football-11-11/law-16---the-goal-kick
- Regla del portero de 8 s (IFAB, 2025): https://www.tntsports.co.uk/football/what-is-the-eight-second-goalkeeper-rule-how-long-can-goalkeepers-hold-the-ball-when-will-the-rule-come-into-place_sto20086781/story.shtml
- Duración de las paradas: https://pmc.ncbi.nlm.nih.gov/articles/PMC10442814/table/T3 · https://theanalyst.com/articles/premier-league-rules-throw-ins-goal-kicks-ball-in-play
