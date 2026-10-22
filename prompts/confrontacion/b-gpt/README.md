# Registro del candidato B — b-gpt

Registro de la sección D del [protocolo de confrontación](../../../docs/experimentos/confrontacion-candidatos.md).

| Campo | Declaración |
|---|---|
| Autor | Edu (hxst1) |
| Rama | `cand/b-gpt`, creada desde `main` |
| Paquete | `solution/b_gpt/` |
| Herramienta | OpenAI Codex |
| Versión del cliente instalada | `codex-cli 0.163.0`, comprobada con `codex --version` el 2026-10-21 |
| Modelo utilizado | **ChatGPT-6 Astra**, confirmado por Edu al cerrar la sesión |
| Identificador de modelo en la configuración local | `gpt-6-astra` |
| Nivel de razonamiento utilizado | **`high`**, confirmado por Edu; coincide con la configuración local |
| Versión/snapshot exacto del modelo servido | No se muestra en la información de la interfaz disponible para este registro; no se inventa un identificador de snapshot |
| Presupuesto | **8 h de tiempo activo** |
| Sesión 1 | 2026-10-21, de **20:15 a 21:06**, Europe/Madrid |
| Tiempo activo consumido | **0 h 51 min de 8 h**, según [horas.md](horas.md) |
| Tiempo restante | **7 h 9 min** |
| Commit del candidato al abrir este registro | `ce9c575` |
| Evaluaciones públicas usadas | **1 de 5** |
| Repetición local #2 | Completada por Edu: **8.545 s**, SHA-256 idéntico al primer CSV y validación oficial correcta; no pública |

Edu confirmó ChatGPT-6 Astra, razonamiento `high`, utilizado a través de Codex.
La comprobación local anterior leyó únicamente los campos `model`, `model_provider`,
`model_reasoning_effort` y `profile`, sin credenciales ni historial de otras conversaciones.
La versión del cliente y el alias del modelo son datos distintos de un snapshot fechado:
la declaración no permite inventar este último.
La [documentación oficial de razonamiento](https://developers.openai.com/api/docs/guides/reasoning)
describe el ajuste de esfuerzo; no certifica qué modelo atendió esta conversación.

## Comando de entrega

Desde la raíz de `more-than-a-hack-2027`, con las dependencias fijadas instaladas y
`MTAH_DATA_DIR` configurado por el participante:

```bash
python -m solution.b_gpt --out evaluation/results/<nombre>.csv
```

`<nombre>` se sustituye por el nombre elegido. La inferencia sobre datos reales la
ejecuta exclusivamente el participante en su entorno local; no el agente LLM.

## Incidencia de Python comunicada al abrir el registro

Edu comunicó `/usr/bin/python: No module named pip` al intentar instalar las dependencias.
No se ha instalado software ni modificado el candidato para responder a esa incidencia.
Se reutilizaron inicialmente las dependencias del entorno de `control_v1`.
Al cerrar la sesión se creó el entorno en `solution/b_gpt/.venv/`, con el mismo Python
y las seis versiones fijadas de dependencias locales, sin descargas. Se comprobaron
las versiones y la importación de NumPy y pandas antes y después de la limpieza.
La carpeta anterior `solution/control_v1/`, sin trackear, fue eliminada por indicación
de Edu, sin abrir sus archivos de resultados. El entorno actual se activa así:

```bash
git switch cand/b-gpt
source solution/b_gpt/.venv/bin/activate
export MTAH_DATA_DIR="$HOME/mtah2027"
python -m solution.b_gpt --out evaluation/results/b_gpt.csv
```

El entorno queda ignorado por Git; el paquete entregado sigue siendo `solution/b_gpt/`.
No implica que el error de `pip` del Python del sistema haya sido reparado.

Posteriormente Edu comunicó un error genérico al leer XML. Tras definir
`MTAH_DATA_DIR` mediante `export`, confirmó que el comando devolvió una respuesta.
No fue necesario modificar el lector ni el método. No se recibieron ni abrieron
los archivos del partido ni sus resultados por frame para resolver la incidencia.

## Contenido y alcance

- [prompts.md](prompts.md): mensajes de usuario completos, en orden, incluido el contexto
  automático inicial y la petición de crear este registro; respuestas resumidas.
- [horas.md](horas.md): sesión del 2026-10-21 cerrada con 0 h 51 min de tiempo activo.
- [ejecuciones.md](ejecuciones.md): evaluación pública #1 y comprobaciones sintéticas identificables.
- [desviaciones.md](desviaciones.md): las dos desviaciones declaradas por Edu.

Este registro se construye retrospectivamente a partir de la conversación disponible.
La fecha contextual es 2026-10-21, zona Europe/Madrid; no hay sellos horarios de cada
mensaje ni un cronómetro histórico de actividad accesible al agente. Los horarios
y el tiempo activo de sesión fueron confirmados por Edu al cerrarla.

El cierre actual modifica el registro y elimina la versión anterior sin trackear,
conservando las dependencias en el entorno de b_gpt. No cambia el código versionado,
los parámetros, el método ni los resultados del candidato vigente.
No incluye materiales restringidos ni predicciones por frame.
