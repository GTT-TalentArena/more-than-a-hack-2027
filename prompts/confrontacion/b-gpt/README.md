# Registro del candidato B — b-gpt

Registro de la sección D del [protocolo de confrontación](../../../docs/experimentos/confrontacion-candidatos.md).

| Campo | Declaración |
|---|---|
| Autor | Edu (hxst1) |
| Rama | `cand/b-gpt`, creada desde `main` |
| Paquete | `solution/b_gpt/` |
| Herramienta | OpenAI Codex, agente de código de esta conversación |
| Versión del cliente instalada | `codex-cli 0.163.0`, comprobada con `codex --version` el 2026-10-21 |
| Modelo declarado por el protocolo | ChatGPT-6 Astra |
| Identificador de modelo en la configuración local | `gpt-6-astra` |
| Nivel de razonamiento en la configuración local | `high` |
| Versión/snapshot exacto del modelo servido | No expuesto al agente; pendiente de confirmación si la interfaz lo proporciona |
| Ajuste efectivo de esta conversación | Pendiente de confirmación por Edu; la configuración local no demuestra que no exista una selección distinta por sesión |
| Presupuesto | **8 h de tiempo activo** |
| Tiempo activo consumido | Pendiente de completar por Edu en [horas.md](horas.md); no se interpreta como 0 h |
| Commit del candidato al abrir este registro | `ce9c575` |
| Evaluaciones públicas usadas | **1 de 5** |

La comprobación de configuración leyó únicamente los campos `model`, `model_provider`,
`model_reasoning_effort` y `profile` de la configuración local de Codex, sin credenciales
ni historial de otras conversaciones. El cliente instalado, el alias configurado y el
modelo efectivo de una sesión son datos distintos: no se inventa un snapshot ni se
presenta el ajuste por defecto como una verificación de todas las llamadas anteriores.
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
Se comprobó que el entorno local usado anteriormente sigue disponible en
`solution/control_v1/.venv/`, con NumPy 2.3.5 y pandas 2.3.3. Puede activarse para ejecutar
el nuevo paquete con ese intérprete:

```bash
git switch cand/b-gpt
source solution/control_v1/.venv/bin/activate
export MTAH_DATA_DIR="$HOME/mtah2027"
python -m solution.b_gpt --out evaluation/results/b_gpt.csv
```

Esto reutiliza el entorno existente; el paquete entregado sigue siendo `solution/b_gpt/`.
No implica que el error de `pip` del Python del sistema haya sido reparado.

Posteriormente Edu comunicó un error genérico al leer XML. Tras definir
`MTAH_DATA_DIR` mediante `export`, confirmó que el comando devolvió una respuesta.
No fue necesario modificar el lector ni el método. No se recibieron ni abrieron
los archivos del partido ni sus resultados por frame para resolver la incidencia.

## Contenido y alcance

- [prompts.md](prompts.md): mensajes de usuario completos, en orden, incluido el contexto
  automático inicial y la petición de crear este registro; respuestas resumidas.
- [horas.md](horas.md): sesión del 2026-10-21 y campos pendientes de confirmación.
- [ejecuciones.md](ejecuciones.md): evaluación pública #1 y comprobaciones sintéticas identificables.
- [desviaciones.md](desviaciones.md): las dos desviaciones declaradas por Edu.

Este registro se construye retrospectivamente a partir de la conversación disponible.
La fecha contextual es 2026-10-21, zona Europe/Madrid; no hay sellos horarios de cada
mensaje ni un cronómetro histórico de actividad accesible al agente. Se ha solicitado
a Edu la información faltante, sin deducir horas activas de commits o fechas de ficheros.

La creación del registro modifica exclusivamente estos cinco documentos de texto.
No cambia el código, los parámetros, el método ni los resultados del candidato.
No incluye materiales restringidos ni predicciones por frame.
