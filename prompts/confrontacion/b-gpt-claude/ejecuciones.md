# Ejecuciones (variante B + Claude)

| # | Fecha | Commit | Comando | Resultado agregado | ¿Pública (A8)? |
|---|---|---|---|---|---|
| s1 | 2026-10-21 | (este commit) | `python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics` | 37 pruebas OK (34 de la v0 + 3 nuevas); la nueva prueba principal falla con la v0 | No (sintético) |
| s2 | 2026-10-21 | (este commit) | `python -m solution.b_gpt --synthetic` ×2 | mismo SHA-256 en las dos; validador oficial OK (199.319 filas); ~4,6 s | No (sintético) |
| 1 | 2026-10-21 | `02bda8f` | `python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv` (Edu, datos reales) | 347 posesiones · media 11,87 s · mediana 6,84 s · D 35,19 % · X 0 % (mitades puntuadas) · `out_of_play_gap_frames` 6.787 · validador OK · 8,55 s | No |
| 2 | 2026-10-21 | `02bda8f` | igual, con `--out …/b_gpt_claude_r2.csv` | mismo SHA-256 que la #1 (`68f2ed57…`) · 8,46 s | No |

Comparación con la v0 (registro de b-gpt): 354 → 347 posesiones, D 33,41 % → 35,19 %, media 11,95 → 11,87 s. Sin GT: no indica si acierta más.

Cupo público compartido con el candidato B (decisión de Alejandro, 21:45): **1 de 5 usadas** en total (la #1, de la v0); quedan 4.
