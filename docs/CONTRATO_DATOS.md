# Contrato de datos · P0 v1

> 🇬🇧 **English version:** [CONTRATO_DATOS.en.md](CONTRATO_DATOS.en.md). This document was written in Spanish; the translation is kept in sync.

> Decisión de diseño de integración del equipo, 22 de octubre de 2026.
>
> Estado: contrato v1 de integración. P0 incluye validadores de frames, posiciones y máscaras en `solution/contract.py`, generación configurable y un adaptador de comandos. Las señales de Nico/Jimy/Pablo son interfaces objetivo: su producción y conformidad aún deben comprobarse. Las definiciones oficiales del reto prevalecen sobre este documento.

## 1. Principios

1. Una única referencia temporal: el vídeo **táctico**.
2. Una ausencia de observación no significa balón parado ni coordenada cero.
3. Las señales son evidencia, no etiquetas verdaderas.
4. El generador de predicciones no recibe ground truth; el evaluador lo consume por separado.
5. Se conservan los datos originales localmente y se normaliza en adaptadores sin reescribir los loaders oficiales.
6. No se cambia la interfaz pactada de los candidatos A/B durante una ronda congelada.

## 2. Tiempo e índices

Para BAR-ATH se usan `games.GAMES` y `games.source_frames()` como fuente de constantes: 199.319 frames tácticos y 25 fps. No dispersar estos números por el código.

| Campo | Tipo | Regla |
|---|---|---|
| `frame` | entero | `0 <= frame < n_frames`; índice de vídeo táctico |
| `time_s` | flotante derivado | `frame / fps`, desde el inicio del vídeo, no desde el saque inicial |
| `start_frame` | entero | Inicio incluido |
| `end_frame` | entero | Final excluido; un intervalo contiene `start_frame <= frame < end_frame` |

La salida cubre **todo el vídeo**, no solo los cinco minutos públicos ni solo los periodos de juego. No recortar ni desplazar filas para evaluar.

### Conversiones obligatorias

- ATD táctico entregado: `frame = frame_id - 1`. Ejemplos sintéticos: 1 → 0, 26 → 25.
- Homografía táctica: su columna `frame` ya comienza en 0.
- Smart Tagging: `int(round(seconds * fps))`, como el loader oficial; Python redondea empates al par. Sus intervalos son semiabiertos.
- No aplicar a este ATD los offsets por parte de `games.py`: describen otro contador de origen, no el índice del ATD entregado.
- Broadcast tiene su propia línea temporal. En v1 no se mezcla con tactical; cualquier uso futuro requiere un mapeo explícito y comprobado.

Rechazar índices duplicados, fuera de rango o desordenados. Si faltan observaciones, mantener la rejilla completa de frames y marcar ausencia; no comprimir el tiempo. Un fichero de fuente inesperadamente desalineado debe producir diagnóstico, no una corrección de offset inventada.

## 3. Coordenadas

Las posiciones normalizadas originales se conservan para aplicar homografías. Para distancias físicas, la interfaz común utiliza metros:

```python
x_m = x_normalized * pitch_length_m
y_m = y_normalized * pitch_width_m
```

Dimensiones: leer `games.GAMES[game]["pitch"]`; actualmente `(105.3, 68.0)`.

El origen `(0, 0)` es el mismo que en el sistema normalizado del ATD; `x` recorre el largo y `y` el ancho. **No se presupone** que H ataque siempre hacia `+x`, ni se invierten ejes por parte. La orientación táctica, si se necesita, será una señal independiente y comprobada.

Las posiciones fuera del rectángulo del terreno pueden ser reales. No recortarlas a los límites: perderíamos evidencia de salida del balón. Rechazar infinitos o valores no numéricos observados; aplicar otros filtros de plausibilidad solo con reglas documentadas.

Homografía: pasar coordenadas normalizadas a `starter.load_homography.project()`, no metros. Una matriz no válida no se usa; su error de reproyección no es una probabilidad.

## 4. Equipos, slots y ausencias

- Equipos: `H` y `A`, obtenidos de metadatos; no deducidos del dorsal o de una posición de columna arbitraria.
- Un `slot_id` identifica un slot del export, **no garantiza identidad estable del jugador**. No acumular estadísticas por persona sin resolver identidad.
- `ball_observed` y `player_observed` indican presencia válida en la fuente, no presencia física real.
- En memoria, coordenada desconocida → `NaN`, con máscara `False`. En JSON → `null`, nunca el literal no estándar `NaN`.
- Una observación interpolada se mantiene diferenciada: `*_observed=False`, `*_available=True`, `*_imputed=True`. No presentarla como medida original.
- Sin interpolación: `available == observed` y `imputed == False`.
- Ni `(0, 0)` ni `D` se usan como sustitutos automáticos de datos ausentes.

## 5. Interfaz normalizada del tracking

Formato inicial en memoria: diccionario de arrays NumPy. No se exige un fichero Parquet, una base de datos ni un nuevo framework. Si se persiste un caché, será local e ignorado por Git.

| Clave | Forma / tipo | Descripción |
|---|---|---|
| `frame` | `(N,)`, int64 | Secuencia exacta `0..N-1` |
| `ball_xy_m` | `(N, 2)`, float64 | Posición del balón; ausencias como NaN |
| `ball_observed` | `(N,)`, bool | Balón medido válido |
| `ball_available` | `(N,)`, bool | Coordenada utilizable observada o imputada |
| `ball_imputed` | `(N,)`, bool | Coordenada estimada, no medida |
| `player_xy_m` | `(N, S, 2)`, float64 | Posiciones por slot |
| `player_observed` | `(N, S)`, bool | Máscara de medida válida |
| `player_available` | `(N, S)`, bool | Posición utilizable |
| `player_imputed` | `(N, S)`, bool | Posición estimada |
| `slot_id` | `(S,)`, cadena | Identificador del slot en el export |
| `slot_team` | `(S,)`, cadena | `H`, `A` o desconocido; desconocidos excluidos del voto por equipo |

`N` procede de la fuente táctica; `S` de los metadatos, no se fija a 22 o 46. El adaptador valida formas y coherencia entre máscaras y coordenadas. Debe evitar duplicar arrays completos innecesariamente.

## 6. Señales de los módulos

El modelo recibe señales alineadas `(N,)`. Cada señal numérica incluye una máscara de validez. Valor ausente → NaN y validez falsa. Una puntuación en `[0,1]` es una **fuerza de evidencia**, no una probabilidad calibrada salvo prueba explícita.

| Grupo | Campos propuestos | Productor |
|---|---|---|
| Distancias | `nearest_H_m`, `nearest_A_m`, `distance_valid` | Nico |
| Contacto/control | `control_H_score`, `control_A_score`, `control_valid` | Jimy |
| Balón parado | `dead_score`, `restart_score`, `dead_valid`, `restart_valid` | Pablo |
| Smart Tagging | `tag_H_score`, `tag_A_score`, `tag_dead_score`, `tag_valid` | Pablo |

Una distancia de equipo solo es válida si hay balón y al menos un jugador utilizable de ese equipo. Si los equipos tienen coberturas distintas, el adaptador expone máscaras por equipo y `distance_valid` exige ambas para una comparación H/A.

Los módulos opcionales pueden faltar completos: el modelo debe declararlo en su configuración y no transformar su ausencia en evidencia negativa. No se compara por distancia cuando esta no es válida. Los umbrales y pesos pertenecen a la configuración, no a este contrato.

Smart Tagging original se mantiene como eventos `{code, start_frame, end_frame, tags}` del loader oficial. La rasterización a señales la hace un adaptador con política de solapes documentada: en v1 combinar evidencia del mismo tipo con máximo, conservar evidencias contradictorias de H/A y dejar al modelo resolverlas. No copiar directamente esos intervalos al CSV final.

## 7. Modelo y salida

Interfaz interna objetivo:

```python
def predict(inputs, config):
    """Devuelve un array (N,) de etiquetas H/A/D/X."""
```

El baseline inicial puede leer directamente los datos autorizados mediante su código oficial. No necesita fingir que consume señales todavía inexistentes; el adaptador documenta qué entradas utiliza realmente.

Contrato externo obligatorio:

```csv
frame,label
0,H
1,H
2,X
```

Ejemplo puramente sintético e incompleto, no una entrega real. La entrega real tiene encabezado exacto, 199.319 filas, índices consecutivos y solo `H/A/D/X`. El validador oficial decide su validez.

La v1 no impone decisiones futbolísticas como una duración mínima ni una regla de relleno universal: son hipótesis de P1–P7. Sí prohíbe confundir ausencia con balón parado. `X` no es gratis: macroF1 lo penaliza; para métricas temporales el evaluador rellena abstenciones según sus reglas. Usar sus recuentos, sin reconstruir una métrica distinta en P0.

## 8. Compatibilidad con los candidatos A/B

El protocolo vigente de #26 exige `python -m solution.<cand> --out <csv>`. Mantenerlo. P0 puede ejecutar ese comando con una lista de argumentos sin `shell=True`, recoger el CSV y pasarlo a validación/evaluación.

La configuración se registra aparte si el candidato aún no admite `--config`. No afirmar que una opción se aplicó si su implementación no la consume. No compartir código entre candidatos antes de la congelación ni cambiar el presupuesto por introducir este contrato. Cualquier cambio del brief se acuerda y registra para ambos.

## 9. Privacidad y evolución

No publicar tracking normalizado, señales por frame, predicciones completas, cachés, imágenes o intervalos reales de discrepancias sin comprobar que su difusión está permitida. Mantenerlos locales en `salidas/` o fuera del repo. Compartir únicamente evidencia agregada permitida y ejemplos sintéticos. El baseline oficial es una excepción deliberadamente conservada como referencia: asigna D cuando no ve el balón; P0 no lo corrige para no cambiar el algoritmo de referencia. Los modelos mejorados deben tratar esa limitación según P1/P2.

Versionado: `contract_version: "1.0"` en configuraciones y registros nuevos. Un cambio incompatible incrementa la versión mayor y exige adaptador o migración explícita. Los nombres aquí definidos son la decisión inicial; si un módulo no puede cumplirlos, registrar la discrepancia y resolverla antes de integrarlo, no cambiar unidades silenciosamente.

## Referencias

- [Datos oficiales](../DATA.md), [FAQ](../FAQ.md), [evaluación](../EVALUATION.md).
- [Loader ATD](../starter/load_atd.py), [homografía](../starter/load_homography.py), [Smart Tagging](../starter/load_smart_tagging.py).
- [Protocolo A/B vigente](experimentos/confrontacion-candidatos.md).
