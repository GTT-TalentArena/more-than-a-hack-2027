# Ejecuciones (variante B + Claude)

| # | Fecha | Commit | Comando | Resultado agregado | ¿Pública (A8)? |
|---|---|---|---|---|---|
| s1 | 2026-10-21 | (este commit) | `python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics` | 37 pruebas OK (34 de la v0 + 3 nuevas); la nueva prueba principal falla con la v0 | No (sintético) |
| s2 | 2026-10-21 | (este commit) | `python -m solution.b_gpt --synthetic` ×2 | mismo SHA-256 en las dos; validador oficial OK (199.319 filas); ~4,6 s | No (sintético) |

Pendiente: primera ejecución con los datos reales (Edu, en local) y comprobación de determinismo con dos ejecuciones.

Evaluaciones públicas usadas por esta variante: 0. Pendiente de Alejandro si tiene cupo propio o comparte las 5 del candidato B.
