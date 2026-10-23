# Docker: ejecutar, validar y comparar de forma reproducible

> 🇬🇧 **English version:** [DOCKER.en.md](DOCKER.en.md). This document was written in Spanish; the translation is kept in sync.

Entorno común del equipo (issue [#24](https://github.com/GTT-TalentArena/more-than-a-hack-2027/issues/24)). Con un solo comando:

1. **valida** cada CSV con el validador oficial,
2. lo **puntúa** con el evaluador oficial contra el GT público,
3. lo **compara** con `baseline_smooth50` (spellF1, macroF1, nº y duración de posesiones),
4. **registra** la ejecución: commit, configuración, versiones, hash SHA-256 de cada CSV y métricas.

No reimplementa ninguna métrica: llama a `evaluation/validate_submission.py` y `evaluation/run_evaluation.py`.

> **Regla de datos (T&C):** los datos del partido nunca entran en la imagen ni en git. Se montan en solo lectura desde tu disco. Lo que generes en `salidas/` puede contener predicciones del partido entero: no lo subas ni lo pegues en un LLM. Comparte solo métricas agregadas (la tabla de `comparacion.md`) o el traceback de un error.

## Qué hay

| fichero | qué hace |
|---|---|
| `Dockerfile` | Python 3.11.17 (imagen fijada por digest) + `numpy`/`pandas` con versión exacta (`docker/requirements.lock`) + git. **No lleva código ni datos.** |
| `.dockerignore` | El contexto de construcción solo incluye `docker/requirements.lock`; todo lo demás se queda fuera. |
| `compose.yaml` | Monta el repo en solo lectura en `/app`, los datos en solo lectura en `/datos` y `./salidas` para los resultados. Corre con tu usuario, no como root. |
| `docker/pipeline.py` | Punto de entrada común: `evaluar`, `baseline` y `modelo` configurable. |
| `.github/workflows/docker.yml` | CI: imagen, referencias públicas, pruebas P0 y códigos de error. |

Como el código se monta y no se copia, **no hace falta reconstruir la imagen al cambiar código**: solo al cambiar `Dockerfile` o `docker/requirements.lock`.

## Requisitos

- Docker con Compose v2 (`docker compose version`). En Windows y macOS, Docker Desktop.
- Para `baseline`: los datos del reto descargados en una carpeta tuya, fuera del repo (por ejemplo `~/mtah2027`, con `tactical/` dentro).

## Uso

### 1. Construir (una vez)

```bash
docker compose build
```

### 2. Evaluar los CSV públicos (sin datos)

```bash
docker compose run --rm evaluar
```

Puntúa los cuatro baselines de `evaluation/results/`. Debe salir `baseline_smooth50` con **spellF1 0.3256** y macroF1 0.6207. Si sale otro número, el entorno está mal.

### 3. Evaluar tus CSV

Copia tus CSV a una carpeta dentro de `salidas/` y apunta el pipeline a ella. Se añade `baseline_smooth50` como referencia:

```bash
mkdir -p salidas/mis-csv && cp /ruta/a/GTT.csv salidas/mis-csv/
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv
docker compose run --rm evaluar evaluar --resultados /salidas/mis-csv --bootstrap 1000   # con intervalos
```

### 4. Regenerar el baseline con los datos del partido (solo en local)

```bash
DATOS=~/mtah2027 docker compose run --rm baseline                       # Linux / macOS
DATOS=~/mtah2027 docker compose run --rm baseline baseline --repetir    # y comprobar determinismo
```

```powershell
$env:DATOS = "D:/datos/mtah2027"; docker compose run --rm baseline     # Windows (PowerShell)
```

Regenera los cuatro baselines y comprueba:
- que **coinciden byte a byte** con los publicados en `evaluation/results/`;
- con `--repetir`, que **dos ejecuciones dan el mismo CSV**;

y luego los evalúa. Sin `DATOS` se usa `./data` del repo.

## Salidas

Cada ejecución crea `salidas/<fecha>-<modo>/`:

El ID incluye microsegundos y un sufijo aleatorio para evitar sobrescrituras. `run.json` se escribe atómicamente y `runs.jsonl` se añade bajo bloqueo entre procesos.

| fichero | contenido |
|---|---|
| `comparacion.md` | tabla contra `baseline_smooth50`: **es lo que se comparte** |
| `run.json` | el registro de esta ejecución |
| `scoreboard.csv`, `reports/` | salida del evaluador oficial |
| `evaluacion.log`, `baseline.log` | lo que se imprimió en pantalla |
| `results/` | los CSV exactos que se evaluaron (privado) |

Y una línea por ejecución en `salidas/runs.jsonl`:

```json
{"id": "20261021T164236Z-evaluar", "modo": "evaluar", "split": "public-5min",
 "commit": "b151c03…", "cambios_sin_commitear": false,
 "entorno": {"python": "3.11.17", "numpy": "2.4.6", "pandas": "3.0.6"},
 "config": {"resultados": "evaluation/results", "bootstrap": 0},
 "csv": [{"nombre": "baseline_smooth50", "sha256": "6d4e04b8…", "valido": true,
          "metricas": {"spellF1": 0.3256, "macroF1": 0.6207, "posesiones": 26, "duracion_media_s": 10.8, …}}],
 "duracion_s": 4.4, "codigo_salida": 0}
```

`baseline` añade `coincide_con_publicados` y, con `--repetir`, `determinista`. Si hay cambios sin commitear, el pipeline lo avisa y lo apunta: ese resultado no se podrá reproducir desde un commit.

## Cómo leer los números

- **Split:** todo lo de aquí es la **ventana pública de 5 min** (17 posesiones, 14,2 s de media). El **0,2433** del hito es el partido completo, que solo puntúa la organización: no compares números de splits distintos.
- **`X`:** el evaluador rellena cada `X` con la última etiqueta no-X de la misma parte antes de contar posesiones. Dentro de una posesión no cuesta nada; en un cambio de posesión arrastra la etiqueta vieja.
- **Ruido:** en la ventana pública, una posesión fallada mueve unos 6 puntos de spellF1. Antes de creerte una mejora, ejecuta con `--bootstrap 1000`.
- La ventana pública sirve para comprobar el **formato y la alineación**, no para elegir modelo (ver `docs/GUIA_PROYECTO.md`).

## Códigos de salida

| código | significado |
|---|---|
| 0 | todo bien |
| 1 | error inesperado (traceback en pantalla y en los `.log`) |
| 2 | algún CSV es inválido, o no hay CSV |
| 3 | faltan los datos del partido |
| 4 | la repetición o la comparación exacta con el baseline publicado no coincide |
| 5 | candidato válido bajo smooth50 **solo con `--exigir-referencia`**; por defecto es advertencia, no fallo técnico |

Un CSV inválido **no** se salta en silencio: aparece marcado ❌ en la tabla, con su motivo, y el proceso termina con 2. Si a la vez hay CSV inválidos y CSV por debajo de la referencia, gana el 2.

## Problemas frecuentes

- **`permission denied` en `salidas/` (Linux):** el contenedor usa el UID/GID 1000. Si `id -u` te da otro número: `GTT_UID=$(id -u) GTT_GID=$(id -g) docker compose run --rm evaluar` (o expórtalas en tu `.zshrc`/`.bashrc`). En macOS y Windows no hace falta.
- **`Faltan los datos del partido`:** revisa que `DATOS` apunte a la carpeta que contiene `tactical/`, con ruta absoluta (`~/…` vale escrito así en la propia línea del comando).
- **Windows:** usa rutas con `/` en `DATOS`, y comparte la unidad en Docker Desktop (Settings → Resources → File sharing).
- **Cambiar dependencias:** edita `requirements.txt`, regenera `docker/requirements.lock` con el comando de su cabecera y `docker compose build`.

## P0: modelos configurables y pruebas

```bash
docker compose run --rm modelo modelo --config configs/smoke_constant.json --repetir
docker compose run --rm --entrypoint python evaluar -m unittest discover -s tests -v
```

La configuración constante es solo una prueba técnica sin datos. Para un baseline con entradas reales usar `configs/baseline_smooth50.json` y definir `DATOS`. Ver [EJECUCION.md](EJECUCION.md) para el contrato de nuevos modelos, registros y límites de privacidad.

La referencia se identifica por hash del fichero público, no solo por el prefijo del nombre. Una métrica pública baja no selecciona el ganador; el código 5 es un control opcional. Los candidatos A/B conservan su interfaz pactada.

Pendiente para #22: valorar una imagen final con código fijado a un commit y verificarla desde una instalación limpia.
