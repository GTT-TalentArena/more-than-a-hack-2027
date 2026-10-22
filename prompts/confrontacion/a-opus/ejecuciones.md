# Ejecuciones · candidato A

Solo resultados agregados (A7). Máximo 5 evaluaciones sobre la ventana pública (A8); se numeran aquí.

| # | Fecha | Commit | Comando | Resultado agregado | ¿Pública (A8)? |
|---|---|---|---|---|---|
| 1 | 2026-10-21 | sin commit (v1.0, árbol de trabajo) | `python -m solution.a_opus --out evaluation/results/a_opus.csv` + `validate_submission.py` | Válido, 199.319 filas, 13 s. 162 posesiones (media 17,8 s, mediana 13,3 s); 115 paradas (54,7 % de los frames puntuados, mediana 21,4 s); solo 48 cambios H↔A directos; posesión viva de H 65,0 %. Modelo sin balón: 84,8 % / 82,4 % con datos no vistos. 53 de 59 ventanas `SET PIECES` con un saque decodificado | no |
| 2 | 2026-10-21 | sin commit (v1.1, árbol de trabajo) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_1.csv` + `validate_submission.py` (antes, `a_opus.csv` de la v1.0 renombrado a `gtt_comet_v1_0.csv`) | Válido. El log agregado de la v1.1 no se devolvió al LLM | no |
| 3 | 2026-10-21 | sin commit (v1.0 y v1.1) | `python evaluation/run_evaluation.py` (sin `--bootstrap`) | Ventana pública (17 posesiones). **v1.1:** spellF1 0,4800 · macroF1 0,8318 · 13 posesiones (media 18,6 s frente a 14,2 s) · transF1@25 0,1622. **v1.0:** spellF1 0,4414 · macroF1 0,7997 · 12 posesiones · transF1@25 0,0556. `baseline_smooth50`: 0,3256 · 0,6207. Diferencia v1.0 → v1.1 dentro de la banda de ruido (~0,04) | **sí · n.º 1 (v1.0) y n.º 2 (v1.1)** |
| 4 | 2026-10-21 | sin commit (v1.1 + `--log`) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_1.csv --log evaluation/reports/gtt_comet_v1_1_log.txt` | Mismo SHA-256 que la ejecución 2 (`a669fb61…`): reproducible (C1). 184 posesiones (media 18,2 s, mediana 13,2 s), 108 paradas (47,2 %), 76 cambios H↔A directos; balón visible en el 91 % de los frames vivos y en el 24 % de los `D`; ventanas `SET PIECES` de ~35 s con el saque a una mediana de 7 s; curva λ 3/4/5/6/8 → 196/184/173/162/150 posesiones. El LLM leyó el log del fichero y el JSON agregado de la ejecución 3 (no los `*_transitions.csv`) | no |

| 5 | 2026-10-22 | sin commit (v1.2) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_2.csv --log evaluation/reports/gtt_comet_v1_2_log.txt` (Jimy) | 185 posesiones, 114 paradas (49,1 %), 71 cambios H↔A; modelo sin balón 87,9 % / 83,8 % (pico en desfase 0); sin retraso del balón (corrección 0); ausencia: huecos ≥ 2 s = 40,6 % de los frames, el 87,7 % en `D` → +0,042 nats/frame | no |
| 6 | 2026-10-22 | sin commit (v1.2) | `run_evaluation.py --results <solo v1.2> --bootstrap 1000` (lo ejecutó el LLM; solo imprime agregados) | Ventana pública: **spellF1 0,4800** (bootstrap 5–95 % 0,293–0,667) · macroF1 0,8331 · transF1@25 0,2162 (latencia media +7,2) · 13 posesiones frente a 17 · alive/dead F1 0,961 · acierto de equipo 0,871 | **sí · n.º 3 (v1.2)** |

| 7 | 2026-10-22 | sin commit (v1.3) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_3.csv --log evaluation/reports/gtt_comet_v1_3_log.txt` (Jimy) | 197 posesiones, 114 paradas (49,0 %), 83 cambios H↔A. **Solo 70 toques detectados** (umbral 24,9 m/s²): el detector por aceleración no encaja con el balón suavizado del ATD real. Reinicios tras hueco: 2 | no |
| 8 | 2026-10-22 | sin commit (v1.3) | `run_evaluation.py --results <solo v1.3> --bootstrap 1000` (LLM; solo agregados) | Ventana pública idéntica a la v1.2: **spellF1 0,4800** · macroF1 0,8331 · transF1@25 0,2162 · 13 posesiones (los cambios de la v1.3 no tocan esos 5 minutos) | **sí · n.º 4 (v1.3)** |

| 9 | 2026-10-22 | sin commit (v1.4) | `python -m solution.a_opus --out evaluation/results/gtt_comet_v1_4.csv --log evaluation/reports/gtt_comet_v1_4_log.txt` (Jimy) | 203 posesiones, 114 paradas (49,0 %), 89 cambios H↔A; toques por cambio de velocidad a ±6: 422 picos, 213 asignados (umbral 5,29 m/s): balón suavizado a escala de ~1 s | no |
| 10 | 2026-10-22 | sin commit (v1.5) | ídem con `gtt_comet_v1_5` (Jimy) | 214 posesiones (mediana 10,4 s), 113 paradas (49,3 %), 101 cambios H↔A; escala de toques elegida ±25, pero umbral de 12,09 m/s inflado por balones aéreos: 315 asignados | no |
| 11 | 2026-10-22 | sin commit (v1.6) | ídem con `gtt_comet_v1_6` (Jimy) | 219 posesiones (mediana 10,4 s), 113 paradas (49,3 %), 106 cambios H↔A; toques a ±25 con referencia de balón raso: umbral 8,83 m/s, 622 asignados (H 424 / A 198) | no |
| 12 | 2026-10-22 | sin commit (v1.6) | `run_evaluation.py --results <solo v1.6> --bootstrap 1000` (LLM; solo agregados) | Ventana pública: **spellF1 0,5250** (bootstrap 5–95 % 0,338–0,713) · macroF1 0,8391 · transF1@25 0,2564 (latencia media +3,8, mediana −1) · 15 posesiones frente a 17 · spellF1@0,7 0,375 · alive/dead F1 0,955 · acierto de equipo 0,899 | **sí · n.º 5 (v1.6)** |

**Evaluaciones públicas usadas:** 5 de 5. No quedan más. Las versiones siguientes solo pueden validarse con el log
sin etiquetas y con el sintético.

**Entrega para la comparación:** el código de las ejecuciones 11 y 12 (v1.6.0) es el del commit `6456aab`. Después
solo se fusionó `main` (infraestructura común) y se añadieron documentación y `configs/candidate_a.json`, sin cambios
en el modelo. CSV de referencia de la v1.6: SHA-256
`ab640ee8694f259697393d822b0a6665a017878b5b29d12715f59ec8a4dbc6d5` (Python 3.11.3, numpy 2.4.6, Windows 11). Se cuenta una por versión puntuada, aunque las dos fueran en el mismo
comando (lectura conservadora de A8). Los cambios de la v1.1 se decidieron con el log sin etiquetas de la ejecución
n.º 1, antes de puntuar nada.
