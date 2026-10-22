# P1 · Conservar temporalmente el estado cuando falta el balón

> Issue [#13](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/13). Autor de implementación: Alejandro Molines. Contrato v1 sin cambios; código nuevo en inglés.
>
> Estado: implementación y pruebas sintéticas; diagnóstico y comparación con tracking real pendientes. No es un resultado de competición ni modifica los candidatos A/B.

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

## Comparación pendiente con datos reales

Registrar commit limpio, entorno, hashes, configuración, dataset/ventana, run ID y duración. `results/candidato.diagnostics.json` y `run.json` conservan diagnóstico agregado; `reports/candidato.json` y `scoreboard.csv` contienen las métricas oficiales. Datos y resultados completos permanecen en `salidas/`, ignorado por Git.

| Variante | Split | spellF1 | macroF1 | Fragmentación | Posesiones | % X |
|---|---|---|---|---|---|---|
| smooth50 oficial | Público | 0.3256 publicado | 0.6207 publicado | Pendiente de registrar | Pendiente de registrar | Pendiente de registrar |
| hold desactivado, mismo lector | Público | No medido con datos reales | No medido | No medido | No medido | No medido |
| hold 25, mismo lector | Público | No medido con datos reales | No medido | No medido | No medido | No medido |

La diferencia con smooth50 no puede atribuirse solo al hold: también cambian suavizado, máscaras y abstención. La comparación controlada es hold 0 frente a hold 25; fuera de sus límites, la etiqueta X y el relleno temporal pueden hacer iguales algunos resultados temporales pese a distintas etiquetas por frame. No equiparar ningún resultado público al 0.2433 privado.

## Aceptación y evidencia

- Implementado: ausencia no fuerza D; reinicio por parte; hold configurable; validación de entradas; diagnóstico agregado; registro y pruebas sin datos restringidos.
- Pendiente: diagnóstico real, comparación reproducible y análisis de mejoras/errores nuevos; revisión de Jimy para estado y Nico para máscaras/alineación; CI de la nueva rama.
- Fuera de alcance: P2 detecta interrupciones, P3 confirma control, P4 decodifica temporalmente y P6 trata huecos avanzados.

No cerrar #13 solo por disponer de los archivos.

## Verificación local del 22 de octubre de 2026

Última ejecución: **29 tests superados** (12 nuevos de P1 y 17 de P0), en 65,934 s, con Python 3.12.14 / NumPy 2.3.5 / pandas 3.0.1 en Windows. El test integrado usa tracking totalmente inventado, genera el CSV completo y verifica validación, repetición, diagnóstico, fragmentación y reinicio entre partes. No mide calidad real del modelo.

En la primera ejecución falló una vez el test existente de concurrencia de P0. Se añadió captura de stdout/stderr para facilitar diagnóstico; diez repeticiones aisladas y la última ejecución completa pasaron. La causa del fallo intermitente no está confirmada: no se presenta como corregida y debe vigilarse en CI.

Docker no está arrancado en este equipo; no se ha ejecutado el contenedor ni GitHub Actions en esta entrega. No hay datos reales en `data/`, por lo que el diagnóstico del partido y la comparación siguen pendientes. Contrato, baseline y métricas oficiales sin cambios; sin commit ni push.
