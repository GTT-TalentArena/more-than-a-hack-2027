# P1 · Conservar temporalmente el estado cuando falta el balón

> Issue [#13](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/13). Autor de implementación: Alejandro Molines. Contrato v1 sin cambios; código nuevo en inglés.
>
> Estado: implementación, pruebas y primera comparación pública con tracking real verificadas. Resultado: mejora pequeña de macroF1, sin mejora de spellF1 o fragmentación; revisión de compañeros y CI de P1 pendientes de confirmar. No es un resultado oficial del partido completo ni modifica los candidatos A/B.

## Hipótesis, fijada antes de resultados reales

La ausencia de observación del balón no demuestra una interrupción. Conservar brevemente la última hipótesis de equipo podría evitar interrupciones artificiales, pero puede retrasar recuperaciones reales. Se fija provisionalmente un límite de **25 frames (1 s)**, no ajustado con la ventana pública. Se compara con límite 0 para aislar el efecto de la conservación.

## Implementación

- `solution/hold.py`: lectura ATD táctica, máscara `ball_observed`, asignación por jugador válido más cercano, hold causal y diagnóstico agregado.
- `configs/baseline_hold.json`: límite 25; `baseline_hold_disabled.json`: límite 0, iguales restantes decisiones.
- `solution/predict.py` y `docker/pipeline.py`: integración en el mismo circuito P0, manifiesto de entradas, diagnóstico en `run.json` y métricas de fragmentación/abstenciones del evaluador oficial.
- `tests/test_hold.py`: ejemplos íntegramente inventados y circuito completo con CSV de 199.319 filas sintéticas.

Se validan coordenadas finitas en ambos ejes; jugadores inválidos y slots de equipo desconocido no votan. El slot no se interpreta como identidad estable. Distancias en metros según las dimensiones de `games.py`. ATD usa `frame_id - 1`; no se alteran los loaders ni el baseline oficial.

El jugador más cercano es una **hipótesis de baseline**, no una prueba de control. No hay umbral de control calibrado en P1 ni detección de interrupciones reales: corresponden a P3/P2. Una observación utilizable permite cambiar al equipo recién observado, sin usar la reaparición para reescribir el hueco previo.

| Caso | Política |
|---|---|
| Estado válido H/A y ausencia de observación utilizable | Repetir como máximo 25 frames |
| Límite agotado | X hasta nueva evidencia |
| Inicio de parte sin evidencia | X; no se inventa equipo ni D |
| Cambio de parte / fuera de partes | Reiniciar; fuera de partes emitir X |
| Balón visible sin jugador válido de equipo conocido | No hay nueva hipótesis; mismo límite de conservación |
| Evidencia válida de D aportada por otro módulo | La función hold puede aceptarla; el lector nearest-player de P1 no la produce |

Sin suavizado, para no esconder ausencias o introducir etiquetas a través del descanso. Los bloques publicados se leen de `games.half_video_blocks()`. No se confunden con el saque inicial: la segunda parte incluye un tramo puntuado previo al saque. P1 no resuelve D en ese tramo.

**X no elimina el error temporal:** el evaluador rellena abstenciones para sus métricas temporales y las penaliza en macroF1. Un límite de hold no limita cuánto arrastra el evaluador la etiqueta anterior. Por eso se registran también abstenciones, fragmentación y limitaciones; no se promete mejora de spellF1.

## Ejecutar localmente

Desde la raíz del repo, con el entorno de [P0](../EJECUCION.md). Sustituir las rutas de ejemplo; nunca copiar tracking a documentación o a un LLM externo.

Diagnóstico agregado sin consumir una evaluación pública:

```bash
python -m solution.hold --data-dir /ruta/a/datos --out salidas/p1-gap-summary.json
```

El JSON no sobrescribe archivos existentes. Incluye por parte porcentaje sin balón, número de huecos, mediana, p90, máximo y distribución de duraciones. Separa ausencia del balón de imposibilidad de asignar equipo. Excluye descanso y frames fuera de partes; los bloques pueden incluir tiempo parado, por lo que **no** es un porcentaje de ausencia sobre juego activo.

Generación y evaluación con registro P0:

```bash
python docker/pipeline.py modelo --config configs/baseline_hold.json --data-dir /ruta/a/datos --repetir
python docker/pipeline.py modelo --config configs/baseline_hold_disabled.json --data-dir /ruta/a/datos --repetir
```

Docker (PowerShell):

```powershell
$env:DATOS = "D:/datos/mtah2027"
docker compose run --rm modelo modelo --config configs/baseline_hold.json --repetir
```

Pruebas:

```bash
python -m unittest discover -s tests -v
```

No comparar variantes ejecutando barridos sobre el público. Coordinar el presupuesto de evaluaciones con #26. No fusionar esta mejora unilateralmente en un candidato independiente durante la ronda.

## Comparación con datos reales · 22 de octubre de 2026

Fuente: registros e informes agregados de las dos ejecuciones realizadas por Alejandro en Arch Linux con Docker y copiados localmente para revisión. Se han leído `run.json`, el diagnóstico agregado y los campos agregados de `reports/candidato.json`. No ha sido necesario leer tracking, vídeos, CSV de predicciones ni intervalos reales por frame. Los archivos originales no se incorporan a Git.

Condiciones verificadas:

- Mismo commit `606e64142baf12469b34fe156095a4fd59757976`; ambas ejecuciones declaran árbol limpio.
- Mismos manifiestos de entradas, hashes del evaluador y GT pública, entorno y semilla declarada. Los modelos son deterministas y no utilizan la semilla.
- Python 3.11.17, NumPy 2.4.6, pandas 3.0.6, Linux/Arch x86_64, usando el entorno Docker del proyecto.
- Misma evaluación `public-5min`, 7.500 frames puntuados y 17 posesiones de referencia; `bootstrap: 0`.
- Configuraciones efectivas verificadas contra su hash: solo cambia `max_hold_frames` de 0 a 25. No hay suavizado en ninguna variante hold.
- Ambas terminan con `codigo_salida: 0`, `estado: ok` y `determinista: true`. Esto verifica funcionamiento/repetición declarada por el pipeline, no calidad futbolística.

| Variante | spellF1 público | macroF1 público | Fragmentación | Posesiones | Duración media (s) | X en frames públicos |
|---|---|---|---|---|---|---|
| smooth50 oficial, evaluado en ambas ejecuciones | 0.3255813953 | 0.6207331924 | 1.4285714286 | 26 | 10.8031 | 0 / 7.500 (0 %) |
| hold 0 | 0.0441379310 | 0.4573235834 | 6.0952380952 | 128 | 2.34375 | 885 / 7.500 (11,8 %) |
| hold 25 | 0.0441379310 | 0.4603944218 | 6.0952380952 | 128 | 2.34375 | 780 / 7.500 (10,4 %) |

La igualdad de spellF1 se ha comprobado también con los valores completos de los registros, no solo con la tabla redondeada. Las métricas agregadas iguales no demuestran por sí solas que todos los intervalos predichos sean idénticos.

| Variante | Run ID | SHA-256 del candidato | Duración total registrada |
|---|---|---|---|
| hold 25 | `20261022T065406.346768Z-3d98f347ed5e-modelo` | `fc128f4f8b0abd118ec2d472e70086419d97703a5aa281f6a7c16b09b1fb0d69` | 116,8 s |
| hold 0 | `20261022T065814.072224Z-833429669b5b-modelo` | `981dc2d811227f411da1d5cec558f160ce89728ff90ee16d2140975d3e94bf33` | 125,6 s |

Los tiempos incluyen el circuito y la repetición, no solo inferencia. Dos ejecuciones secuenciales no permiten concluir que una variante sea más rápida. Los hashes anteriores se transcriben del registro; no se han vuelto a leer las predicciones para recalcularlos.

### Diagnóstico agregado de ausencias

Se usan los bloques publicados de las partes, **incluyendo sus interrupciones** y el tramo previo al segundo saque inicial. Se excluyen descanso y frames fuera de esos bloques. Por tanto, estas cifras no representan exclusivamente juego activo. Los recuentos de ausencia de equipo coinciden con los de ausencia de balón en este lector y estas ejecuciones.

| Bloque | Frames | Sin balón | Porcentaje | Huecos | Mediana (s) | P90 (s) | Máximo (s) |
|---|---|---|---|---|---|---|---|
| Primera parte | 79.467 | 32.304 | 40,65 % | 69 | 11,56 | 43,328 | 138,64 |
| Segunda parte | 79.390 | 32.339 | 40,73 % | 81 | 9,80 | 25,56 | 221,48 |

Total: 64.643 frames sin balón de 158.857 frames de los bloques (40,69 %), distribuidos en 150 huecos: 17 de hasta un segundo, 1 de más de uno y hasta cinco segundos y **132 de más de cinco segundos (88 % de los huecos)**. No sumar ni promediar las medianas de ambas partes como si fueran una mediana global.

Con hold 25 se conservan explícitamente 3.398 frames antes abstinentes (135,92 s repartidos por el partido; no una posesión continua). Equivale al 5,26 % de los frames sin observación. El porcentaje X en los bloques completos pasa de 40,6926 % a 38,5535 %. En la ventana pública, las abstenciones disminuyen en 105 frames (4,2 s), de 11,8 % a 10,4 %; no confundir estas ventanas.

### Interpretación y decisión

- MacroF1 aumenta `0.0030708384` (aproximadamente 0,307 puntos porcentuales), sin intervalos calculados y sobre una muestra pequeña: no se declara mejora generalizable.
- spellF1, fragmentación y número de posesiones no mejoran. El relleno de X del evaluador temporal es una explicación compatible con este resultado: tanto la conservación explícita como la abstención pueden acabar arrastrando el estado previo. No se ha comparado el detalle temporal por frame.
- La mayoría de huecos supera ampliamente el horizonte de un segundo. P1 v1 solo cubre una fracción de las ausencias; aumentar el límite sin evidencia podría arrastrar errores durante recuperaciones o interrupciones reales. Este diagnóstico no demuestra que deba aumentarse.
- La fragmentación alta permanece. El lector nearest-player sin suavizado puede cambiar de equipo con frecuencia; comprobar sus causas requiere revisión futbolística local. No atribuirla exclusivamente a las ausencias ni afirmar que una solución concreta ya la corrige.
- **Decisión:** conservar P1 como componente básico reproducible y experimento de resultado mixto, no sustituir smooth50 por esta variante ni seguir ajustando parámetros sobre el público. Coordinar control, interrupciones y estabilidad temporal con P3/P2/P4; los huecos avanzados corresponden a P6.

La diferencia con smooth50 no puede atribuirse solo al hold: también cambian suavizado, máscaras y abstención. La comparación controlada es hold 0 frente a hold 25; fuera de sus límites, la etiqueta X y el relleno temporal pueden hacer iguales algunos resultados temporales pese a distintas etiquetas por frame. No equiparar ningún resultado público al 0.2433 privado.

## Aceptación y evidencia

- Implementado: ausencia no fuerza D; reinicio por parte; hold configurable; validación de entradas; diagnóstico agregado; registro y pruebas sin datos restringidos.
- Comprobado con registros reales: diagnóstico agregado, comparación controlada, CSV aceptado, determinismo y procedencia de resultados. Limitaciones y resultado mixto documentados; aún no hay análisis visual local de errores concretos.
- Pendiente: revisión de Jimy para estado y Nico para máscaras/alineación; si hace falta, Pablo revisa ejemplos localmente sin publicar extractos; CI de P1 y revisión de la PR pendientes de confirmar. No se han solicitado revisiones ni publicado cambios en esta actualización documental.
- Fuera de alcance: P2 detecta interrupciones, P3 confirma control, P4 decodifica temporalmente y P6 trata huecos avanzados.

No cerrar #13 solo por disponer de los archivos.

## Verificación local del 22 de octubre de 2026

Última ejecución: **29 tests superados** (12 nuevos de P1 y 17 de P0), en 65,934 s, con Python 3.12.14 / NumPy 2.3.5 / pandas 3.0.1 en Windows. El test integrado usa tracking totalmente inventado, genera el CSV completo y verifica validación, repetición, diagnóstico, fragmentación y reinicio entre partes. No mide calidad real del modelo.

En la primera ejecución falló una vez el test existente de concurrencia de P0. Se añadió captura de stdout/stderr para facilitar diagnóstico; diez repeticiones aisladas y la última ejecución completa pasaron. La causa del fallo intermitente no está confirmada: no se presenta como corregida y debe vigilarse en CI.

La comprobación sintética anterior se hizo en Windows sin Docker arrancado. Posteriormente Alejandro ejecutó las dos variantes con Docker en Arch y aportó los registros reales descritos arriba; por ello el diagnóstico y la comparación ya no están pendientes. GitHub Actions de P1 no se ha comprobado en esta revisión. Contrato, baseline y métricas oficiales sin cambios; esta actualización documental no hace commit ni push.
