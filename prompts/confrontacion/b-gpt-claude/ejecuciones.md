# Ejecuciones (variante B + Claude)

| # | Fecha | Commit | Comando | Resultado agregado | ¿Pública (A8)? |
|---|---|---|---|---|---|
| s1 | 2026-10-21 | (este commit) | `python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics` | 37 pruebas OK (34 de la v0 + 3 nuevas); la nueva prueba principal falla con la v0 | No (sintético) |
| s2 | 2026-10-21 | (este commit) | `python -m solution.b_gpt --synthetic` ×2 | mismo SHA-256 en las dos; validador oficial OK (199.319 filas); ~4,6 s | No (sintético) |
| 1 | 2026-10-21 | `02bda8f` | `python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv` (Edu, datos reales) | 347 posesiones · media 11,87 s · mediana 6,84 s · D 35,19 % · X 0 % (mitades puntuadas) · `out_of_play_gap_frames` 6.787 · validador OK · 8,55 s | No |
| 2 | 2026-10-21 | `02bda8f` | igual, con `--out …/b_gpt_claude_r2.csv` | mismo SHA-256 que la #1 (`68f2ed57…`) · 8,46 s | No |
| 3 | 2026-10-21 | `02bda8f` | evaluación pública con Docker (`docker/pipeline.py evaluar`, bootstrap 1000) sobre `b_gpt_claude.csv` | spellF1 **0.3895** · macroF1 0.6620 · 21 posesiones · 13,6 s — **idéntico a la v0** en la ventana pública | **Sí, #2 del candidato B** |
| 4 | 2026-10-21 | `fedc89e` | igual que la #1, con diagnósticos `dead_time_diagnostics` (Edu, datos reales) | mismo SHA-256 (`68f2ed57…`): los diagnósticos no cambian etiquetas · huecos sin balón: < 5 s 0,17 min; 5–10 s 53 tramos / 6,23 min (3,41 vivos); 10–30 s 60 / 17,84 (5,99 vivos); > 30 s 19 / 18,88 (3,21 vivos) · fases lentas < 1 / 1,5 / 2 m/s: 18,4 / 37,7 / 42,3 min (0,5 / 8,5 / 12,0 vivos) | No |
| s3 | 2026-10-21 | (este commit) | tests sintéticos y `--synthetic` ×2 (v2) | 39 pruebas OK; la nueva de huecos largos falla con la v1; mismo SHA-256 en las dos ejecuciones; validador OK | No (sintético) |

Comparación con la v0 (registro de b-gpt): 354 → 347 posesiones, D 33,41 % → 35,19 %, media 11,95 → 11,87 s. Sin GT: no indica si acierta más.

Cupo público compartido con el candidato B (decisión de Alejandro, 21:45): **2 de 5 usadas** en total (#1 la v0, #2 esta v1); quedan 3.

Lectura fijada antes de evaluar: diferencias < ~0,06 de spellF1 son una posesión en esta ventana. Resultado: la v1 **no se distingue** de la v0 en la ventana pública (el cambio no actúa en esos 5 min); su posible efecto está en el resto del partido y solo lo puede valorar la revisión ciega.
