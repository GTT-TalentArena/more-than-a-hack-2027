# Registro de ejecuciones

| # | Fecha | Commit | Comando | Resultado agregado | ¿Pública (A8)? |
|---|---|---|---|---|---|
| 1 | 2026-10-21 | sin commit | evaluación pública con bootstrap 1000 | spellF1 0.3895, macroF1 0.6620, 21 posesiones, 13.6 s de media | Sí, #1 |
| 2 | 2026-10-21 | sin commit | `python -m unittest solution.control_v1.test_synthetic -v` | Primera batería: 20 tests; 18 pasaron y 2 omitidos por falta de pandas. Solo sintéticos. | No |
| 3 | 2026-10-21 | sin commit | `python -m unittest solution.control_v1.test_synthetic -v` | Batería ampliada: 22 tests; 20 pasaron y 2 omitidos por falta de pandas. Solo sintéticos. | No |
| 4 | 2026-10-21 | sin commit; contenido registrado después en `ce9c575` | `solution/control_v1/.venv/bin/python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics -v` | 34 tests pasados en 14.117 s; validación oficial sobre sintéticos y dos CSV sintéticos completos con SHA-256 idéntico. | No |
| 5 | 2026-10-21 | sin commit; contenido registrado después en `ce9c575` | `solution/control_v1/.venv/bin/python -m solution.b_gpt --synthetic --out <temporal_sintetico>/synthetic.csv`, seguido de `solution/control_v1/.venv/bin/python evaluation/validate_submission.py <temporal_sintetico>/synthetic.csv` | Ambos comandos terminaron con código 0; 5.301 s en conjunto; memoria máxima reportada por el candidato 221.14 MiB; stdout limitado a cinco agregados. | No |
| 6 | 2026-10-21 | `d91b063` en el espacio de trabajo al comunicar la incidencia | `python -m solution.b_gpt --out evaluation/results/b_gpt.csv` | Edu comunicó `Cannot read XML input or invalid XML syntax.`; no se obtuvieron métricas. | No |
| 7 | 2026-10-21 | Código de `ce9c575`; commit exacto de ejecución no confirmado, cambios posteriores solo de documentación | `python -m solution.b_gpt --out evaluation/results/b_gpt.csv`, con `MTAH_DATA_DIR` definido | 354 posesiones; duración media 11.953446327683617 s; mediana 6.779999999999999 s; D 33.40677464638008 %; X 0.0 %. Agregados del partido completo comunicados por Edu. | No |

Evaluaciones públicas usadas: 1 de 5

La fila 7 incorpora la salida agregada enviada después de confirmar que `export`
resolvía la incidencia. No se presupone una ejecución adicional por volver a pegar
el comando. Con los 158.857 frames a 25 fps publicados, estos números corresponden
a unos 3,343 posesiones/minuto, 70,525 minutos predichos vivos y 35,379 minutos `D`
dentro de las mitades. Son comprobaciones aritméticas, no medidas de exactitud.
La media mayor que la mediana es compatible con una distribución asimétrica de
duraciones, pero por sí sola no identifica fragmentación o fusión incorrecta.
Faltan los agregados del baseline completo y por mitad para la comparación solicitada;
no se consultó el CSV ni se modificó ningún parámetro.

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

## Repetición de inferencia para comprobar determinismo

La primera inferencia completa comunicada por Edu figura en la entrada 7 del registro
anterior. La repetición solicitada al cerrar la sesión se identifica como **ejecución
local #2 (no pública)**. Esta numeración de inferencias reales es independiente de la
numeración de entradas históricas y de las evaluaciones públicas A8.

La ejecución local #2 está **completada según los resultados comunicados por Edu**.
El agente no ejecutó la inferencia ni abrió los CSV: registra los hashes, tiempos y
agregados enviados por el participante. Esta comprobación de formato y determinismo
no consulta la GT y no consume A8.

| # local | Fecha | Commit de referencia | Comando | Resultado agregado | ¿Pública (A8)? |
|---|---|---|---|---|---|
| 1 | 2026-10-21 | Código de `ce9c575`; véase entrada histórica 7 | `python -m solution.b_gpt --out evaluation/results/b_gpt.csv` | 354 posesiones; media 11.953446327683617 s; mediana 6.779999999999999 s; D 33.40677464638008 %; X 0.0 % en las mitades. SHA-256 comunicado junto a la repetición. | No |
| 2 | 2026-10-21 | `819efb2`, versión disponible al solicitar la repetición; método de `ce9c575` sin cambios | `time python -m solution.b_gpt --out evaluation/results/b_gpt_r2.csv` | 8.545 s reales, 9.05 s de CPU de usuario, 0.19 s de sistema, 108 % CPU; mismos cinco agregados; SHA-256 idéntico; validador oficial OK, 199319 filas, índices 0..199318. | No |

SHA-256 comunicado para **ambos** archivos (`b_gpt.csv` y `b_gpt_r2.csv`):

```text
60ea141519a8978cfb840496d7c39f040b40fba3b0610a81fd1a68160f822f6d
```

El validador informó, sobre **todo el vídeo**, H 64304 (32.3 %), A 41484 (20.8 %),
D 53069 (26.6 %) y X 40462 (20.3 %), con 354 posesiones de media redondeada 12.0 s.
No contradice el resumen del candidato: este último usa exclusivamente los 158857
frames de las mitades publicadas, donde D es 33.40677464638008 % y X es 0.0 %.
Los 40462 frames X coinciden con la extensión publicada no puntuada.

Estos resultados respaldan la reproducibilidad byte a byte de las dos ejecuciones
locales comunicadas, el contrato de salida y un tiempo de inferencia inferior a
30 minutos en el equipo de Edu. No prueban la exactitud de las etiquetas ni permiten
estimar el spellF1 del partido completo. El tiempo de ejecución no se suma como
una sesión nueva al registro de horas activas declarado por el participante.

Comandos de esta comprobación, ejecutados exclusivamente por Edu desde la raíz:

```bash
source solution/b_gpt/.venv/bin/activate
export MTAH_DATA_DIR="$HOME/mtah2027"
time python -m solution.b_gpt --out evaluation/results/b_gpt_r2.csv
sha256sum evaluation/results/b_gpt.csv evaluation/results/b_gpt_r2.csv
python evaluation/validate_submission.py evaluation/results/b_gpt_r2.csv
```

`time` utiliza el medidor del shell zsh, sin requerir `/usr/bin/time`. El CSV original
se conserva. Solo los hashes, el tiempo y la salida agregada del validador se devolvieron
al agente; los archivos CSV y su contenido por frame permanecen en local.
