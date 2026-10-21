# Registro de ejecuciones

| # | Fecha | Commit | Comando | Resultado agregado | ¿Pública (A8)? |
|---|---|---|---|---|---|
| 1 | 2026-10-21 | sin commit | evaluación pública con bootstrap 1000 | spellF1 0.3895, macroF1 0.6620, 21 posesiones, 13.6 s de media | Sí, #1 |
| 2 | 2026-10-21 | sin commit | `python -m unittest solution.control_v1.test_synthetic -v` | Primera batería: 20 tests; 18 pasaron y 2 omitidos por falta de pandas. Solo sintéticos. | No |
| 3 | 2026-10-21 | sin commit | `python -m unittest solution.control_v1.test_synthetic -v` | Batería ampliada: 22 tests; 20 pasaron y 2 omitidos por falta de pandas. Solo sintéticos. | No |
| 4 | 2026-10-21 | sin commit; contenido registrado después en `ce9c575` | `solution/control_v1/.venv/bin/python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics -v` | 34 tests pasados en 14.117 s; validación oficial sobre sintéticos y dos CSV sintéticos completos con SHA-256 idéntico. | No |
| 5 | 2026-10-21 | sin commit; contenido registrado después en `ce9c575` | `solution/control_v1/.venv/bin/python -m solution.b_gpt --synthetic --out <temporal_sintetico>/synthetic.csv`, seguido de `solution/control_v1/.venv/bin/python evaluation/validate_submission.py <temporal_sintetico>/synthetic.csv` | Ambos comandos terminaron con código 0; 5.301 s en conjunto; memoria máxima reportada por el candidato 221.14 MiB; stdout limitado a cinco agregados. | No |

Evaluaciones públicas usadas: 1 de 5

La fila 1 fue ejecutada por Edu en local y comunicada al agente únicamente mediante
agregados. Corresponde a `control_v1`, antes de su empaquetado como `b_gpt`; no se ha
contado de nuevo por el cambio de nombre. No se conoce la línea de comandos literal
de esa evaluación, por lo que se conserva la descripción facilitada por Edu.

La misma comunicación incluyó el baseline como referencia: spellF1 0.3256,
macroF1 0.6207, 26 posesiones, 10.8 s de media; IC 90 % de spellF1 `[0.214, 0.447]`.
El candidato tuvo IC 90 % `[0.242, 0.537]`. No se abrió ningún CSV ni GT para este registro.

Las filas 2–5 son comprobaciones de desarrollo identificadas en la conversación,
realizadas exclusivamente con datos sintéticos. La numeración de esas filas sirve
para identificar entradas del registro retrospectivo, no para atribuirles una hora
respecto de la evaluación #1 que no consta. Los tests sintéticos no consumen A8.
`<temporal_sintetico>` representa un directorio temporal creado para esa prueba;
no es la carpeta de datos del partido.

Durante el desarrollo también se hicieron mediciones sintéticas con scripts efímeros:
generación/inferencia/escritura de 199.319 frames y 46 slots, 3.88 s y 178.7 MiB;
lectura de un ATD sintético de ese tamaño, 4.54 s y 138.0 MiB. No son puntuaciones
públicas ni mediciones sobre el partido. Las líneas completas de esos scripts no
quedaron como ejecutables versionados y no se inventan comandos para reproducirlas aquí.
