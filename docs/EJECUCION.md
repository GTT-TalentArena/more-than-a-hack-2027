# Ejecutar P0 · Generar, validar, evaluar y registrar

> Issue [#12](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/12). Contrato: [CONTRATO_DATOS.md](CONTRATO_DATOS.md). Verificación y cierre: [P0.md](P0.md).

## 1. Desde dónde ejecutar

Todos los comandos parten de la raíz del repo. En el equipo de Alejandro:

```powershell
Set-Location "D:\amolines\Documents\AMolines\TArena\more-than-a-hack-2027"
```

Datos autorizados fuera de Git, en una carpeta con `tactical/`. Ningún comando del generador recibe ground truth. El evaluador utiliza únicamente la referencia pública.

## 2. Docker: vía común del equipo

Con Docker arrancado y Compose v2:

```powershell
docker compose build
docker compose run --rm evaluar
```

Esto evalúa los cuatro baselines públicos sin descargar vídeos ni tracking. `baseline_smooth50` debe dar aproximadamente spellF1 `0.3256` y macroF1 `0.6207`. Las pruebas comprueban los cuatro baselines con tolerancia `0.0001` frente a las cifras publicadas redondeadas.

### Probar el circuito completo sin datos

```powershell
docker compose run --rm modelo modelo --config configs/smoke_constant.json --repetir
```

Genera una etiqueta D constante para todo el vídeo, valida, evalúa, repite y registra. Es un **modelo de prueba deliberadamente inútil**, no un candidato de competición. Su mala puntuación produce advertencia, no error técnico.

### Generar baseline con datos reales locales

Sustituir esta ruta de ejemplo por la carpeta autorizada real:

```powershell
$env:DATOS = "D:/datos/mtah2027"
docker compose run --rm modelo modelo --config configs/baseline_smooth50.json --repetir
```

`window: 50` significa suavizado de ±50 frames. El modo baseline configurable reutiliza el algoritmo oficial, incluida su limitación de interpretar ausencias como D; no es la solución de P1.

Para regenerar los cuatro y comparar con los publicados:

```powershell
docker compose run --rm baseline baseline --repetir
```

Las diferencias de bytes con los publicados dan código 4. Si solo cambian CRLF/LF, diagnosticarlo comparando etiquetas; no ocultar la diferencia. No editar los CSV públicos para que la prueba pase.

### Evaluar CSV entregados por compañeros

Guardar los CSV únicamente en `salidas/mis-csv/`:

```powershell
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv --bootstrap 1000
```

Un CSV inválido hace fallar el conjunto, aunque otros sean válidos. Una métrica baja queda registrada. Para activar expresamente el antiguo control de calidad:

```powershell
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv --exigir-referencia
```

No usar este control para elegir el ganador A/B: el público tiene solo 17 posesiones. Respetar también el presupuesto de evaluaciones del protocolo #26.

## 3. Python sin Docker

Python 3.11 recomendado para igualar la imagen; instalar dependencias en un entorno local:

```powershell
py -3.11 -m venv .venv
.\.venv\Scripts\python.exe -m pip install -r docker/requirements.lock
.\.venv\Scripts\python.exe docker/pipeline.py evaluar
.\.venv\Scripts\python.exe docker/pipeline.py modelo --config configs/smoke_constant.json --repetir
.\.venv\Scripts\python.exe -m unittest discover -s tests -v
```

No hace falta activar el entorno ni cambiar políticas de PowerShell. Si `py` no existe, usar la ruta del Python instalado. La entrega se ha comprobado también con el runtime local indicado en [P0.md](P0.md); eso no sustituye la ejecución pendiente en Docker.

Con datos locales:

```powershell
.\.venv\Scripts\python.exe docker/pipeline.py modelo `
  --config configs/baseline_smooth50.json `
  --data-dir "D:/datos/mtah2027" --repetir
```

Validar sin evaluar:

```powershell
.\.venv\Scripts\python.exe evaluation/validate_submission.py salidas/mis-csv/candidato.csv
```

## 4. Configuración y nuevos modelos

Las configuraciones se validan estrictamente; no se permiten opciones ignoradas. Ejemplo mínimo:

```json
{
  "contract_version": "1.0",
  "model": "baseline",
  "parameters": {"window": 50},
  "seed": 0,
  "evaluation": {"split": "public-5min", "bootstrap": 0}
}
```

Modelos disponibles: `baseline`, `constant` (solo pruebas) y `module`. Para un candidato que respeta el brief existente, configurar:

```json
{
  "contract_version": "1.0",
  "model": "module",
  "parameters": {"module": "solution.candidate_a"},
  "seed": 0,
  "evaluation": {"split": "public-5min", "bootstrap": 0}
}
```

El nombre es un ejemplo: el módulo debe existir antes de usarlo. El adaptador llama a `python -m solution.candidate_a --out <csv>` sin cambiar su interfaz. La ubicación de los datos se comunica por `MTAH_DATA_DIR`. No se inyecta la semilla: `seed_applied: null` significa que debe declararla el candidato. Para baseline/constant se registra `false`, porque no la necesitan. No afirmar que se ha aplicado una opción que el módulo no consume.

No abrir ni fusionar enfoques A/B antes de la congelación. Para nuevos modelos internos ampliar el adaptador y sus tests; seguir el contrato de señales sin modificar métricas oficiales.

## 5. Salidas y reproducibilidad

Cada ejecución crea una carpeta exclusiva bajo `salidas/` con fecha UTC, UUID y modo:

| Archivo | Contenido |
|---|---|
| `config.json` | Configuración efectiva del modo modelo |
| `results/` | Copia exacta de predicciones evaluadas y referencia |
| `run.json` | Commit, cambios pendientes, entorno, configuración, hashes, métricas, duración y estado |
| `comparacion.md` | Resumen agregado frente a smooth50 |
| `scoreboard.csv`, `reports/` | Informes oficiales; pueden incluir detalle restringido |
| `*.log` | Generación, evaluación, repetición o error |

`runs.jsonl` se añade bajo bloqueo entre procesos; `run.json` individual es la fuente de verdad. El registro se guarda también ante fallos controlados y excepciones de ejecución. Si falla escribirlo, el proceso devuelve error. No existe garantía frente a corte eléctrico o terminación forzada del proceso.

Para baseline se identifican por hash el XML y el ATD utilizados. Para módulos externos se registra el bundle táctico disponible, no se afirma conocer qué archivos consumió realmente su código; el candidato debe documentarlo. El hash del código oficial y de la GT pública también queda registrado. Las rutas y los manifiestos son locales.

Una ejecución con cambios sin commit es exploratoria: antes de publicar evidencia final, crear el commit y repetir desde un árbol limpio con el mismo entorno y entradas.

## 6. Códigos de salida

| Código | Significado |
|---|---|
| 0 | Ejecución técnicamente correcta; revisar advertencias |
| 1 | Configuración incorrecta, error del modelo/evaluador o del registro |
| 2 | CSV inválido, carpeta sin CSV o intento de suplantar la referencia |
| 3 | Faltan entradas obligatorias del baseline |
| 4 | Reproducción no idéntica cuando se ha comprobado |
| 5 | Métrica pública baja **solo con `--exigir-referencia`** |

`$LASTEXITCODE` permite consultar el resultado del último comando en PowerShell. Un error de argumentos de CLI puede salir antes de crear una ejecución; no hay todavía configuración válida que registrar.

## 7. Interpretación y privacidad

spellF1 mide posesiones completas; macroF1 clasifica por frame. Usar recuentos y duraciones del evaluador. El validador sin GT puede contar X como huecos y dar cifras distintas: las métricas temporales oficiales rellenan abstenciones según sus reglas.

`0.2433` es el resultado **publicado** del baseline en el partido completo privado. No compararlo con `0.3256` público ni dar por alcanzado el hito con un candidato nuevo sin evaluación oficial.

No subir `salidas/`, datos, frames, señales o predicciones a GitHub ni a LLMs externos. Tampoco publicar logs o registros completos sin revisión. Compartir solo código, documentación, fixtures sintéticos y evidencia agregada permitida. Revisar nombres/rutas incluso en `comparacion.md` antes de compartirla.
