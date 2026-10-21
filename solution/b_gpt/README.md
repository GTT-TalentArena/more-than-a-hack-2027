# b_gpt

Candidato determinista de CPU: evidencia geométrica de control, indicios de balón
parado, Smart Tagging débil y Viterbi a 25 fps. No es un LLM y no llama a servicios
externos. Esta primera versión conserva el algoritmo y todos los parámetros de
`control_v1`; cambia el empaquetado y añade diagnósticos agregados sin ground truth.
Las versiones siguientes se registran mediante commits en **`cand/b-gpt`**, no mediante
carpetas nuevas. No se publica en `main` ni en la web.

## Variante v1: v0 + mejora de Claude

Esta rama (`cand/b-gpt-claude`) parte de la v0 congelada en el tag **`b-gpt-v0`** (solo
Codex, ChatGPT-6 Astra high) y añade los cambios v1, v2 y v3, escritos por Claude Code
(Claude Opus 5.5, effort medium) con la aprobación de Alejandro como evaluador. Registro
propio en `prompts/confrontacion/b-gpt-claude/`.

**Balón perdido tras salir del campo = parada.** Un balón que ha salido no puede volver
al juego sin un saque (reglas 9 y 15–17). La v0 solo detectaba la salida mientras *veía*
el balón fuera; si el tracking lo perdía justo después —lo habitual al salir del encuadre—
y los jugadores seguían moviéndose, como en un saque de banda o de puerta, mantenía la
posesión. Ahora, si el balón se vio fuera de forma clara (persistente, como en la v0, o a
más de `clear_out_m` = 1 m de la línea) y a continuación desaparece, todo el hueco cuenta
como evidencia de parada con el mismo peso que un balón visto fuera, y los jugadores
corriendo no cuentan en contra. El hueco termina cuando el balón vuelve a localizarse y
nunca dura más que `stop_lookback_s` (45 s). El resto del método y de los parámetros es
idéntico a la v0.

Motivo: Smart Tagging solo anota una parte de las reanudaciones, así que muchas paradas
(saques de banda y de puerta sin anotar) solo se pueden detectar con el tracking. Nada se
ha elegido con la ventana pública. `evidence_totals.out_of_play_gap_frames` informa en el
`.summary.json` de cuántos frames afecta el cambio.

**v2 · Huecos largos sin balón = parada.** Diagnósticos sin GT del partido completo
(`evidence_totals.dead_time_diagnostics`, ejecución de Edu) muestran que en este tracking el
balón casi nunca falta poco tiempo (< 0,2 min de huecos de menos de 5 s en todo el partido),
pero falta en **132 tramos de ≥ 5 s que suman ~43 min**: un número parecido al de paradas de
un partido y una duración que, sumada a la `D` ya detectada fuera de ellos, da ≈ 47 % de `D`,
en línea con el tiempo efectivo de LaLiga. Vidal-Codina et al. (2022) describen proveedores
que marcan el balón parado dejándolo sin datos. La v1 etiquetaba como vivos 12,6 min de esos
tramos. Ahora, con los jugadores seguidos (≥ 8), un tramo sin balón de **≥ `long_gap_s` = 10 s**
es evidencia fuerte de parada y uno de **≥ `medium_gap_s` = 5 s**, moderada; los jugadores
corriendo no cuentan en contra. Si faltan balón y jugadores a la vez es un corte de datos, no
una parada. Los umbrales salen de la duración de una reanudación (saque de banda rápido 5–10 s;
faltas, saques de puerta y córners, más de 10 s), no de ninguna puntuación.

**v3 · Solo los huecos que empiezan o acaban como un saque.** En la ventana pública la v2
subió el recall de `D` (0,26 → 0,41) pero bajó su precisión (≈ 1,0 → 0,59): no todo hueco largo
es una parada. Un jugador de espaldas a la cámara que protege o conduce el balón, o un balón
perdido en vuelo, también lo hacen desaparecer con el juego vivo. La v3 sustituye la regla de la
v2: un hueco de ≥ 5 s (con jugadores seguidos) solo es evidencia de parada si el balón **se perdió
junto a una línea** (≤ `clear_out_m`), **reaparece quieto** (< 0,65 m/s, como en la v0: colocado
para una falta, un saque de puerta o de centro), **reaparece junto a una línea** (saque de banda,
córner) o el hueco dura **más de `very_long_gap_s` = 30 s**. Si reaparece moviéndose dentro del
campo, se trata como juego vivo, como en la v1. La idea es posterior a ver el desglose de la
evaluación pública #3 (desviación declarada en el registro).

Comando de esta variante (no pisa el CSV de la v0):

```bash
python -m solution.b_gpt --out evaluation/results/b_gpt_claude.csv
```

## Ejecución local

Desde la raíz de `more-than-a-hack-2027`, con Python 3.11–3.14:

```bash
python -m pip install -r solution/b_gpt/requirements.txt
export MTAH_DATA_DIR="$HOME/mtah2027"
python -m solution.b_gpt --out evaluation/results/b_gpt.csv
```

Se recomienda instalar las dependencias en un entorno virtual. Todas las dependencias
directas y transitivas están fijadas. Solo la instalación necesita red; la inferencia
usa CPU, sin GPU, descargas, entrenamiento ni llamadas externas.

El comando de inferencia lo ejecuta **únicamente el participante en local**. Un agente
LLM no debe abrir los datos, los CSV del partido ni ejecutar este comando sobre ellos.
El desarrollo y las pruebas de esta entrega han usado exclusivamente documentación,
código público y datos sintéticos. No se ha accedido a `~/mtah2027`.

Las entradas del partido proceden de `games.asset_paths(source="tactical")`, que
respeta `MTAH_DATA_DIR`; `--data-dir` permite indicar otra raíz local. Se leen ATD,
metadatos y Smart Tagging. No se leen homografía, vídeo, retransmisión ni GT.

El comparador es `evaluation/results/baseline_smooth50.csv`, según la ubicación del
repositorio. Es una predicción, no un activo de `asset_paths`. Se puede indicar otro
CSV de ese baseline mediante `--baseline /ruta/baseline_smooth50.csv`. Si falta o no
cumple el contrato, el comando falla con un error saneado; no sustituye silenciosamente
el baseline ni omite la comparación.

Salidas:

- El CSV indicado: `frame,label`, **199.319 filas de datos**, índices `0…199318` y
  etiquetas `H/A/D/X`. Se valida con la función oficial después de escribirlo.
- Un archivo con el mismo nombre y extensión `.summary.json`: parámetros, versiones,
  huella del código, tiempo, memoria, evidencia agregada y diagnósticos de **ambos** CSV.
- Una sola línea JSON en stdout: número de posesiones, duración media y mediana,
  porcentaje `D` y porcentaje `X`, dentro de las mitades publicadas.

No hay filas, coordenadas, series temporales ni eventos individuales en los diagnósticos
o en stdout. Los errores omiten valores de entrada y variables locales. El CSV por
frame es el entregable local; no se debe compartir con un LLM. Para validarlo aparte:

```bash
python evaluation/validate_submission.py evaluation/results/b_gpt.csv
```

El CSV es determinista byte a byte con las mismas entradas, código y dependencias.
El JSON contiene tiempo y memoria de ejecución, que pueden variar; estos campos no
intervienen en las etiquetas ni en el hash del CSV.

## Método y motivos de los parámetros

El lector comprueba cada ID de frame y el número de slots, aplica `frame_id - 1` y
convierte coordenadas normalizadas a metros. Los slots solo aportan pertenencia a
equipo: no son identidades de jugadores. Cada mitad se procesa por separado según
`games.half_video_blocks`; fuera de ellas se escribe `X`.

**Control.** Se calcula la distancia más corta al balón para cada equipo. La evidencia
depende de la proximidad absoluta, de la diferencia respecto al rival, de la velocidad
del balón y de la fiabilidad de la observación. Un rival más cercano pero a varios
metros de un balón en vuelo no se convierte automáticamente en poseedor. La ausencia
del balón aporta evidencia de control cero y no equivale a `D`.

**Paradas.** Se combinan balón fuera del campo, balón quieto con quietud colectiva,
y ausencia del balón con quietud colectiva prolongada. Balón moviéndose dentro del
campo y jugadores activos aportan evidencia contraria. Las fases automáticas son
indicios débiles: las defensivas favorecen al contrario, `N/A` no se convierte en un
equipo y los solapamientos se combinan por máximo, no sumando observaciones correladas.

**Reinicios.** Los intervalos `SET PIECES` delimitan una búsqueda de inicio de movimiento.
Si hay evidencia, se busca hacia atrás el tramo compatible con una parada. El primer
`Kick Off (Start)` permite detectar el tramo previo al saque de cada mitad, sin escribir
a mano ningún frame de saque. Un intervalo de reinicio no se etiqueta entero como `D`.

**Secuencia.** Viterbi optimiza evidencia por segundo menos costes de cambio. Cambiar
H↔A requiere evidencia del destino; entrar/salir de `D` requiere indicios compatibles.
Los huecos no permiten adelantar arbitrariamente un cambio hasta el inicio de una
oclusión. No hay número objetivo de posesiones ni duración mínima impuesta.

Los valores son heurísticos, fijados antes de la evaluación pública; no son estimaciones
calibradas ni valores óptimos demostrados. Se conservan sin cambios:

| Parámetro | Valor | Razón física o estructural |
|---|---:|---|
| Radio de control | 2 m | Alcance próximo al jugador; decaimiento suave, no asignación por cercanía a cualquier distancia. |
| Escala de separación entre equipos | 1,5 m | Atenuar disputas con distancias similares. |
| Escala de velocidad rápida | 9 m/s | Un balón rápido cerca de un jugador puede ser un pase, no control. |
| Máxima velocidad para filtrar saltos | 55 m/s | Umbral conservador para saltos aislados extremos, no para recortar pases normales. |
| Interpolación máxima | 0,24 s; confianza 0,3 | Cubrir pérdidas muy breves sin inventar trayectorias en oclusiones largas. |
| Velocidad por desplazamiento | aproximadamente 0,24 s | Reducir ruido de coordenadas sin suavizar las etiquetas. |
| Margen fuera del campo | 0,35 m; persistencia 0,16 s | Evitar que el ruido en la línea cree paradas de un frame. |
| Balón quieto / jugadores quietos | <0,65 / <1,2 m/s | Indicios de colocación o espera, siempre combinados. |
| Persistencia de quietud | 2 s; 3 s si falta el balón | La ausencia es una señal más ambigua y exige apoyo más duradero. |
| Jugadores válidos para actividad | al menos 8 | Evitar interpretar unos pocos tracks o un encuadre vacío como quietud colectiva. |
| Peso control / fase automática | 4,0 / 0,55 | Geometría próxima más fuerte que una anotación de fase correlada y temporalmente imprecisa. |
| Coste H↔A / con D | 0,65 / 0,9 | Penalizar fragmentación; una parada falsa divide una posesión incluso si vuelve el mismo equipo. |
| Búsqueda de reinicio | intervalo ±2 s | Permitir imprecisión temporal de las anotaciones automáticas. |
| Búsqueda previa de parada | hasta 45 s | Admitir preparación de faltas/córners sin extender la búsqueda indefinidamente. |
| Equipo tras reinicio sin equipo | siguiente control en 2 s | Hipótesis local al saque; no propagar un control futuro lejano. |

Los pesos son energías relativas, no probabilidades. Por ejemplo, con ventaja máxima
4 por segundo, un episodio aislado de un equipo necesita superar dos costes de 0,65;
esto admite controles claros de alrededor de un tercio de segundo, pero exige más
duración si la evidencia es débil. No equivale a borrar todas las posesiones cortas.
Los detalles y restantes umbrales explícitos están en `config.py` y `model.py`.

## Diagnósticos del partido completo

En `.summary.json`, `full_match_diagnostics` contiene `b_gpt` y `baseline_smooth50`,
cada uno con `full_match`, `by_half` y `whole_video`. No usa la GT pública ni la privada.

- `possessions_per_minute`: número de posesiones dividido por el tiempo de vídeo de
  las mitades publicadas. Incluye paradas y el tramo previo al segundo saque dentro
  de ese bloque. No divide por 45 minutos ni por tiempo de balón vivo.
- `duration_seconds.p10/p50/p90`: percentiles de duración de las posesiones H/A;
  en el total se agrupan las posesiones de ambas mitades, sin promediar percentiles.
- `percent_D`, `percent_X`: porcentajes sobre etiquetas originales, entre 0 y 100.
  `whole_video` muestra aparte los porcentajes incluyendo descanso y márgenes no puntuados.
- Posesiones: se rellenan `X` dentro de cada mitad como hace el scorer, sin cruzar el
  descanso. `n_possessions_without_X_fill` muestra también el conteo sin ese relleno.
  Una mitad íntegramente `X` conserva su ausencia de respuesta.

`smart_tagging` informa totales y tipos: saques de banda, córners, faltas/saques libres,
saques de puerta y los dos tipos de saque de centro. Se cuentan instancias automáticas,
no se afirma que sean eventos reales distintos. Los tipos desconocidos y puntos medios
fuera de las mitades se contabilizan en `event_inventory` y no entran en el denominador.

Definiciones fijadas para **informar**, sin efecto sobre las predicciones:

- Se representa cada intervalo por su punto medio, independiente del reinicio estimado
  por el candidato, y se le asigna la mitad que contiene ese punto.
- `inside_dead_fraction`: punto medio dentro de una racha `D` explícita.
- `just_after_dead_fraction`: punto medio fuera de `D`, hasta **2 s** después del
  extremo exclusivo de una racha `D`. La frontera de salida cuenta como demora cero.
- `coherent_midpoint_fraction`: suma de las dos anteriores, sin doble conteo.
- `near_dead_to_live_boundary_fraction`: punto medio a ±2 s de una salida explícita
  `D→H/A`. Ayuda a distinguir un reinicio localizado de una parada excesivamente larga.
- `interval_could_be_coherent_fraction`: alguna posición del intervalo satisface el
  criterio. Es una comprobación más permisiva de la incertidumbre de la anotación,
  no un sustituto del criterio de punto medio.

Las fracciones van de 0 a 1, con numeradores y denominadores. Sin eventos se devuelve
`null`, no cero. Dos segundos toleran la imprecisión del tagging, descrita como del
orden de un segundo, sin aceptar cualquier parada lejana. Es una tolerancia fija de
diagnóstico; no se selecciona con el resultado público. La coherencia usa `D` explícito,
sin rellenar `X` como supuesta parada y sin conectar mitades.

**Coherencia no es exactitud.** El candidato ya utiliza Smart Tagging: no es una
validación independiente. Una predicción siempre `D` puede lograr coherencia de 100 %;
por eso se muestran cobertura `D`, localización de salida a vivo y distribución de
posesiones. Ninguno de estos agregados autoriza a imponer un número de posesiones.

## Pruebas, rendimiento y límites

Pruebas exclusivamente sintéticas, con fixtures generadas sin datos del partido:

```bash
python -m unittest solution.b_gpt.test_synthetic solution.b_gpt.test_diagnostics -v
python -m solution.b_gpt --synthetic --out /tmp/b_gpt_synthetic.csv
```

`--synthetic` no llama siquiera a `asset_paths`: también genera la entrada del baseline
y no abre el CSV real. Una prueba bloquea esa función para garantizarlo.

**34 pruebas pasadas** con NumPy 2.3.5 y pandas 2.3.3: contrato oficial del CSV,
alineamiento, unidades, entradas inválidas saneadas, oclusiones, posesiones cortas,
reinicios, independencia entre mitades, Viterbi frente a búsqueda exhaustiva,
denominadores/percentiles, límites de coherencia, caso degenerado siempre `D` y
equivalencia del relleno de `X` con el evaluador. Dos ejecuciones completas de
199.319 frames sintéticos produjeron hashes SHA-256 idénticos. La batería, que incluye
varias inferencias completas, tardó unos 14 s en este entorno.
Una ejecución adicional por el comando público y el script oficial de validación
terminó en **5,30 s**, con **221,1 MiB** de memoria máxima reportada, usando solo
entradas sintéticas. Ambos comandos terminaron con código cero.

El coste principal es `O(frames × slots)`, con distancias por bloques y Viterbi de
tres estados. No se decodifica vídeo. El objetivo de menos de 30 minutos en CPU tiene
amplio margen en estas pruebas; no se ha cronometrado el partido real. La instalación
de dependencias y un almacenamiento especialmente lento pueden afectar el tiempo total.

Limitaciones: con coordenadas 2D no se observa la altura del balón ni la decisión del
árbitro. Quietud no siempre significa parada; una oclusión puede contener un cambio
inobservable. Las fases automáticas y el tracking comparten errores. El control sigue
dependiendo del jugador cercano; ponderarlo no añade por sí mismo información semántica
de recepción, pase o despeje. No se afirma superar el baseline en el partido completo.

El análisis de las métricas públicas recibidas está en [ANALYSIS.md](ANALYSIS.md).
Se utiliza para entender la incertidumbre, no para ajustar umbrales. No hay una búsqueda
de parámetros ni selección de versiones mediante esas 17 posesiones.

Los CSV y JSON de resultados se quedan en local. `.gitignore` excluye
`solution/*/output/`, `solution/*/.venv/`, `__pycache__/` y los summaries de resultados.
Al devolver resultados a un LLM, compartir únicamente números agregados o errores
saneados, nunca filas de CSV, etiquetas por frame, XML, coordenadas o imágenes.
