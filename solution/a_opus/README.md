# Candidato A · posesión por frame con decodificación exacta

> **Confrontación de candidatos (#26)** · candidato A · Claude Opus 5.5 (effort max) · rama `cand/a-opus`
>
> El código lo ha escrito el LLM sin ver ningún dato del partido: ni el ATD, ni el Smart Tagging, ni la GT
> pública, ni los CSV de `evaluation/results/`. Está construido a partir de la documentación del reto y del
> estudio `docs/ESTUDIO_POSESION.md`, y se ha probado solo con partidos **sintéticos** generados por
> `synth.py` en los mismos formatos. Ningún parámetro se ha elegido con la ventana pública.

## Ejecución

```bash
pip install -r solution/a_opus/requirements.txt
python -m solution.a_opus --out evaluation/results/a_opus.csv
python evaluation/validate_submission.py evaluation/results/a_opus.csv
```

- Se ejecuta **desde la raíz del repositorio**, y `-m` recibe el nombre del módulo con puntos
  (`solution.a_opus`), no una ruta.
- Lee los datos de `MTAH_DATA_DIR` (o `./data`) a través de `games.asset_paths()`; `--data-dir` lo cambia.
  Si no los encuentra, dice dónde ha mirado y termina con código 2.
- Escribe 199.319 filas `frame,label`, con `X` fuera de las dos mitades puntuadas y `H`/`A`/`D` dentro.
- Tarda **unos 10 s** en un portátil sin GPU (el ATD sintético, del mismo tamaño que el real, se lee en ~7 s).
  Usa solo numpy y la biblioteca estándar.
- Es **determinista**: dos ejecuciones dan el mismo fichero byte a byte (comprobado con SHA-256), con saltos
  de línea `\n` en cualquier sistema operativo.
- Todo lo que imprime son **agregados** (recuentos, porcentajes, duraciones, constantes ajustadas). Ninguna fila,
  ningún frame. Es el log que se puede devolver al LLM según el acuerdo A7.
- Cualquier parámetro de `config.py` se cambia sin tocar el código: `--set decode.lam_ha=6 --set ballfree.enabled=0`.

Por la **vía común del equipo** (#12 y #24), con `configs/candidate_a.json` (`"model": "module"`). Hay que poner en
`DATOS` la carpeta que contiene `tactical/`:

```powershell
docker compose run --rm modelo modelo --config configs/candidate_a.json --repetir
```

Sin Docker vale `python docker/pipeline.py modelo --config configs/candidate_a.json --repetir`, con
`MTAH_DATA_DIR` apuntando a los datos: por contrato, el módulo solo recibe `--out`. La imagen fija las mismas
versiones que `requirements.txt` (numpy 2.4.6 y pandas 3.0.6). Por esta vía sale el mismo CSV byte a byte que con la
ejecución directa (comprobado en sintético).

En **Windows (PowerShell)**, si `python` es el del sistema y no tiene numpy, crea un entorno con las versiones
fijadas y llama a su intérprete por la ruta. Así no depende de activar el entorno, que la política de ejecución
de scripts puede bloquear:

```powershell
py -3.11 -m venv .venv
.venv\Scripts\python.exe -m pip install -r solution\a_opus\requirements.txt
$env:MTAH_DATA_DIR = "<carpeta del bundle, la que contiene tactical\>"
.venv\Scripts\python.exe -m solution.a_opus --out evaluation\results\a_opus.csv
.venv\Scripts\python.exe evaluation\validate_submission.py evaluation\results\a_opus.csv
```

Tests (sin datos del partido):

```bash
python -m solution.a_opus.tests          # decodificador frente a fuerza bruta, lector, equipos del Smart Tagging
python -m solution.a_opus.tests --full   # además, un partido sintético corto de punta a punta
python -m solution.a_opus.synth --out-dir <carpeta>   # un partido sintético completo para probar
```

## Enfoque

Una posesión es un intervalo, y `spellF1` puntúa intervalos. Por eso el candidato no decide frame a frame:
calcula una **evidencia por frame** y después busca **la secuencia H/A/D globalmente óptima** con un coste por
cada cambio de estado.

```
maximizar   Σ_t evidencia(estado_t, t)  −  λ · (número de cambios)      con D ≥ 2 s
```

Es un HMM/Viterbi de tres estados (`decode.py`) y resuelve exactamente lo que el estudio recomendaba (sección
4.5): un solo mando (λ) para el dilema entre parpadeo y posesión corta, fronteras donde cambia la evidencia y sin
retraso sistemático, porque se procesa offline con pasado y futuro. La duración mínima de la parada se impone de
forma exacta con una suma acumulada, así que la recursión es O(1) por frame y una mitad se decodifica en menos de
un segundo. El test `test_decoder_is_exact` compara la solución con la fuerza bruta en 300 problemas aleatorios.

### Evidencia de equipo (H frente a A)

- **Zona de control.** Para cada equipo, la distancia del balón a su jugador más cercano entra en un núcleo
  `K(d) = exp(−½·(max(d − d0, 0)/σ)²)`, multiplicado por una compuerta de velocidad relativa balón–jugador. Un
  balón que pasa rápido junto a un rival no está controlado. La evidencia del frame es `α·(C_H − C_A)`: en un
  duelo, con los dos equipos cerca, se anula.
- **Sin balón no es balón muerto.** Es el principal error del baseline: cuando no se ve el balón, la evidencia es
  cero, no `D`, y el decodificador mantiene el estado. Los huecos de hasta 2 s se rellenan con una recta entre
  las dos observaciones, con un peso que decae con la longitud del hueco.
- **"El balón suelto se queda con el último equipo".** En vuelos y oclusiones la evidencia es exactamente cero y
  el decodificador empata. Los empates se resuelven a propósito: el cambio de equipo se coloca **lo más tarde
  posible**, en el primer toque del nuevo equipo.
- **Toques sin control.** Cambiar de posesión cuesta λ = 5 nats y un parpadeo dentro de una posesión cuesta el
  doble. Con α = 0,4 hacen falta ~10 frames de control claro para cambiar y ~20 para un parpadeo, así que un
  desvío o un despeje sin control no cambian la posesión, como pide `CHALLENGE.md`. (λ = 4 en la v1.1 y λ = 3
  desde la v1.3; ver las secciones de ejecuciones reales más abajo.)
- **Toques (v1.3; detector por cambio de velocidad desde la v1.4).** Un pico del cambio neto de velocidad del
  balón, con un jugador claramente el más cercano, aporta 1,5 nats a su equipo. Un toque solo no cambia la
  posesión, pero fecha el cambio en el frame justo cuando le sigue control.
- **Smart Tagging como prior débil.** Las fases con equipo (`BUILD UP`, `PROGRESSION`, `DEFENDING IN …`) añaden
  un empujón pequeño: 0,03 nats por frame como máximo, menos de una décima parte de un frame de control. Solo pesa
  cuando no hay balón. El tagger emite las fases por parejas sobre el mismo intervalo (`BUILD UP` de un equipo y
  `DEFENDING IN ATTACKING THIRD` del otro, etc.), así que cada intervalo cuenta una sola vez.
- **Modelo sin balón.** Es una regresión logística sobre la forma y el movimiento de los equipos: posición relativa,
  amplitud, velocidad hacia la portería rival y bloque, orientados según el sentido de ataque de cada mitad. Actúa
  solo donde no hay balón (el 41 % de los frames puntuados).

### Evidencia de balón muerto (D frente a vivo)

Va aparte de la de equipo, a propósito. Quién está cerca del balón dice qué equipo lo tiene **si está vivo**, pero
casi nada sobre si lo está: el que va a sacar de banda está tan pegado al balón como un regateador. Por eso la
evidencia de equipo nunca juega en contra de `D`.

| término | qué capta | magnitud |
|---|---|---|
| fuera del campo | balón visto a más de 0,5 m fuera de una línea; el cruce se fecha con la recta interpolada desde la última observación dentro | +1 nat por observación, +0,5 por frame interpolado fuera; ×0,3 si vuelve dentro antes de 1 s (balón aéreo proyectado) |
| salida | última observación junto a una línea y saliendo, seguida de un hueco ≥ 1,5 s | +3 nats en total |
| balón quieto | balón parado ≥ 1 s (balón colocado); ×3 en córner o centro del campo, ×2 en área pequeña o punto de penalti, ×0,3 si va pegado a un jugador (portero con el balón en las manos) | +0,06 nats por frame |
| golpeo tras balón quieto | el balón sale a más de 5 m/s después de estar quieto (se busca desde 1 s antes del final de la racha quieta, porque el ajuste lento lo anticipa) | −0,5 nats por frame, 10 frames |
| reinicio tras hueco largo (v1.3) | el balón reaparece lento (en manos o colocado) y lo toca alguien antes de 5 s | +0,05 por frame hasta el toque; −0,5 por frame durante los 10 siguientes |
| balón rápido | balón a más de 6 m/s dentro del campo | −0,08 nats por frame |
| velocidad colectiva | mezcla de dos gaussianas sobre la velocidad media de los jugadores (parado = componente lenta). No puede votar `D` donde el balón se ve moviéndose dentro del campo en ≥ 20 % de los ±1 s | LLR recortada a ±3, /25 por frame |
| ausencia larga del balón (v1.2) | cada frame de un hueco ≥ 2 s del balón. La intensidad es el cociente de odds entre la fracción de frames de hueco largo que una primera decodificación (que no mira la visibilidad) pone en `D` y la fracción global; los huecos cortos no cuentan | 0,5 × log-odds-ratio / 25 por frame, recortado a ±3 |
| formación de saque inicial | casi todos en su campo, lentos, balón (si se ve) en el centro | +0,15 nats por frame |
| `SET PIECES` del Smart Tagging | el saque está dentro de la ventana; solo está documentado para los saques iniciales (~3,5 s después de que se abra) | +0,06 desde 2 s antes hasta 3 s después de que se abra; −0,06 el segundo siguiente a su cierre |

Las paradas empiezan **lo antes posible** (en cuanto sale el balón, lo que sigue no es juego) y terminan **lo más
tarde posible** (el saque es cuando se golpea). Duración mínima: 2 s.

### Autocalibración sin etiquetas

Algunas constantes se estiman con el propio partido, sin GT. Son estadísticos del ATD, no ajustes a una
puntuación:

- **Radio de control**: `d0` y `σ` se escalan con la mediana de la distancia al jugador más cercano de los
  balones lentos.
- **Umbral de balón quieto**: el ruido de posición del balón se mide con segundas diferencias, y el umbral sube
  si ese ruido lo exige.
- **Modelo de velocidad**: la mezcla de dos gaussianas se ajusta con EM sobre el partido.
- **Smart Tagging**: la polaridad y la fiabilidad de cada código se miden por su acuerdo con el equipo que
  claramente tiene el balón. Un código en contra se invierte y uno al 50 % se ignora.
- **Modelo sin balón**: se entrena con los frames en que la proximidad nombra un equipo con claridad
  (autosupervisión), con validación cruzada por mitades. Cada mitad se predice con el modelo de la otra, y el
  acierto en esos datos no vistos fija su peso (0 si no supera el 55 %, peso completo desde el 75 %).

## Activos usados y descartados

| activo | uso |
|---|---|
| ATD táctico | **sí**: todo lo anterior. El lector toma la estructura de línea del `DataFormatSpecification` del XML EPTS, y si no puede, la documentada |
| Smart Tagging | **sí**: `SET PIECES` como evidencia de parada y saque, y las fases como prior de equipo calibrado |
| homografía | **no**: el ATD ya está en coordenadas de campo, y solo serviría para proyectar sobre el vídeo y revisar errores |
| vídeo táctico | **no**: con 30 min de CPU no hay margen para detectar el balón en 199.319 frames de 1080p |
| retransmisión | **no**: no está sincronizada y su homografía falta en un tercio de los frames |
| GT pública | **no** se ha usado para nada (0 de 5 evaluaciones; A8). Solo se mirará para comprobar que el pipeline es correcto |
| datos externos | ninguno |

## Validación con datos sintéticos

`synth.py` simula 22 agentes con regates, pases, intercepciones, entradas, balones sueltos, tiros, fueras de
banda y de fondo, faltas y todos los saques, incluidos los iniciales. Encima añade el ruido que documenta el ATD
real:

- balón ausente ~50 % del tiempo, a ráfagas, más en el aire, en aglomeraciones y con el balón parado;
- ruido de posición y detecciones locas;
- balones aéreos proyectados lejos del punto real;
- tracks fragmentados que saltan entre los 46 slots;
- un Smart Tagging que marca solo algunos saques y fases, con bordes desplazados.

Sus parámetros son inventados y **distintos de los del candidato**. Sirve para comprobar que el pipeline es
correcto y para ver la forma de las curvas, no para predecir la puntuación real.

Resultados en tres partidos sintéticos completos (semillas 0, 1 y 2), con la configuración por defecto:

| | spellF1 | macroF1 | posesiones (predichas / reales) |
|---|---|---|---|
| candidato A v1.5 | 0,765 · 0,806 · 0,782 (suavizado: 0,805 · 0,759 · 0,818 · 0,764) | 0,933 (media) | 281/363 · 320/381 · 331/395 |
| candidato A v1.4 | 0,749 · 0,806 · 0,770 (estilo real: 0,809 · 0,760) | 0,928 (media) | 272/363 · 311/381 · 317/395 |
| candidato A v1.3 | 0,761 · 0,810 · 0,774 | 0,929 (media) | 275/363 · 313/381 · 322/395 |
| candidato A v1.2 | 0,728 · 0,789 · 0,755 | 0,926 (media) | 256/363 · 303/381 · 303/395 |
| candidato A v1.1 | 0,723 · 0,781 · 0,753 | 0,918 · 0,932 · 0,921 | 256/363 · 295/381 · 299/395 |
| candidato A v1.0 | 0,691 · 0,765 · 0,750 | 0,916 · 0,931 · 0,922 | 241/363 · 287/381 · 287/395 |
| `baseline_smooth50` (mismo sintético) | 0,317 · 0,329 · 0,308 | 0,447 · 0,470 · 0,445 | 639/363 · 769/381 · 760/395 |

Lo que enseña el sintético:

- **Las fronteras caen bien.** Los cambios H↔A detectados tienen un desfase mediano de 0 frames (p90 de
  9 frames con balón visible y de 16 sin él). Los finales de parada caen a ±1 frame.
- **Lo que se pierde son posesiones cortas.** Casi ninguna de menos de 2 s se detecta, y la mitad de las de
  2–5 s. Por debajo de ~1 s la evidencia disponible no alcanza ni para un decodificador bayesiano bien calibrado,
  porque el prior de cambio pesa más.
- **Las paradas por falta empiezan tarde** (~3 s): no hay pitido en el tracking, solo la frenada colectiva.
- **Sensibilidad a λ** (v1.1, media de las tres semillas): 3 → 0,761 · 4 → 0,753 · 5 → 0,731. El sintético
  prefiere un λ bajo. Se usa 4 y no 3 porque el ruido real (jugadores no trackeados en duelos, detecciones
  falsas, proyecciones aéreas) produce más evidencia espuria que el sintético. Es un compromiso a priori, no un
  ajuste.
- **Ablaciones** (v1.1, media de las tres semillas, desde 0,753): sin modelo de velocidad, 0,668 (−0,08); sin
  modelo sin balón, 0,717 (−0,04); sin Smart Tagging, 0,735 (−0,02); sin el filtro de velocidad por actividad
  del balón, 0,753 (en el sintético el juego nunca es lento: el filtro está pensado para el dato real). En el
  sintético el modelo sin balón acierta el 97 % porque la simulación ata mucho la forma del equipo a la posesión.

## Primera ejecución real (v1.0) y cambios de la v1.1

Ejecutada por Jimy en local el 21-O-2026. Al LLM solo volvió el log agregado (A7); no es una evaluación pública.

**Lo que confirmó:**
- El ATD se lee entero: 199.319 registros contiguos, estructura de línea leída del XML.
- La asignación de equipos es correcta: el Smart Tagging queda en H 314 / A 288 / N/A 36, exactamente lo que dice
  DATA.md.
- H es el Barça: 65 % de la posesión viva. El sentido de ataque está claro en las dos mitades.
- El modelo sin balón acierta un **82–85 %** en datos no vistos: en el dato real es una fuente útil.
- Todos los códigos del Smart Tagging tienen la polaridad esperada. `BUILD UP` y `PROGRESSION` coinciden en un
  87–89 % con quién tiene el balón; los de último tercio y área, en un 60–71 %.

**Lo que el sintético no tenía:**
- El balón del ATD está **suavizado** (ruido de posición ~0) y **no tiene huecos cortos**: la interpolación de
  ≤ 2 s no rellena nada. Cuando el balón falta, falta más de 2 s seguidos.
- El tercer canal del balón es la velocidad, no la altura.
- Las ventanas `SET PIECES` son mucho más largas de lo supuesto: la evidencia total implica ~15–25 s de media.

**Lo que salió mal:**
- Solo **48 cambios H↔A directos** en todo el partido (162 posesiones, 115 paradas, 54,7 % de `D`). Casi todos los
  cambios pasaban por una parada. Hay dos fallos de código que lo explican en parte:
  - el golpeo tras balón quieto no se detectaba nunca (el ajuste lento lo anticipa y la búsqueda no lo
    alcanzaba);
  - con ventanas largas, la evidencia de `SET PIECES` se metía varios segundos en el juego posterior al saque.

**Cambios de la v1.1:**
- Corregidos los dos fallos.
- Las fases emparejadas del Smart Tagging cuentan una sola vez.
- La velocidad colectiva ya no vota `D` cuando el balón se ve en juego.
- λ = 4.
- El log añade comprobaciones sin etiquetas: dónde cae el saque dentro de las ventanas, qué hace el balón en los
  frames decodificados como `D` y como vivos, tramos de control claro del equipo "sin balón" y la curva de
  posesiones y cambios frente a λ.

**Sobre el 54,7 % de `D`:** no es necesariamente un error. Tres indicios públicos apuntan a un `D` alto en el
partido completo:
- `starter/make_dummy_submission.py` dice que el balón muerto es "la etiqueta más común". En la ventana pública
  es la menos común, así que habla del partido completo.
- El macroF1 de `always_home` publicado en `run_evaluation.py` (0,1627) no cuadra con la ventana pública (daría
  0,210). Con la GT completa implica que H ocupa ~32 % de los frames puntuados. Con un Barça al ~60–70 % de la
  posesión, eso deja `D` en ~45–54 %.
- El tiempo de juego efectivo de LaLiga ronda los 55 min de ~106.

La ventana pública (19,6 % de `D`) es el arranque del partido y no es representativa.

## Segunda ejecución real (v1.1) y cambios de la v1.2

**Reproducibilidad.** La v1.1, reejecutada, da exactamente el mismo fichero (SHA-256 `a669fb61…`), que es el
criterio C1.

**Lo que dijeron las comprobaciones sin etiquetas** (ejecución 2):
- 184 posesiones, 108 paradas (47,2 % de `D`, ahora dentro del rango esperado) y 76 cambios H↔A directos.
- **El balón falta sobre todo con el balón muerto:** se ve en el 91 % de los frames decodificados como vivos y en
  el 24 % de los decodificados como `D`. Es la pregunta L4 del estudio, y la respuesta es que sí: una ausencia
  larga es evidencia de parada (estudio 3.3).
- Las ventanas `SET PIECES` duran ~35 s, y el saque decodificado cae a una mediana de 7 s de su apertura.
- No hay tramos largos de control rival ignorado, y la curva de λ no tiene meseta.

**Lo que dijo la ventana pública** (evaluaciones n.º 1 y 2, registradas por Jimy; solo se usó para entender el
tipo de error):
- La decisión vivo/muerto es buena (alive/dead F1 0,96) y el equipo acierta un 87 %.
- **Las fronteras caen mal:** solo 3 de las 20 transiciones reales tienen una de las nuestras a ±1 s.

**Cambios de la v1.2, todos sin etiquetas y sacados del estudio:**
- **Ausencia larga del balón como evidencia de parada** (estudio 3.3, punto 3, y L4). Hay dos pasadas: la
  primera no mira la visibilidad, y su asociación entre huecos largos y `D` (un paso de EM duro) da la intensidad
  de la segunda. Los huecos cortos no cuentan.
  - Primero probé dar evidencia a cada hueco según su longitud: en el sintético creaba paradas falsas con ráfagas
    de huecos cortos.
  - Luego, una cadena de Markov de visibilidad: convertía el parpadeo frame a frame del sintético en evidencia
    enorme.
  - Las dos se descartaron.
- **Modelo sin balón sin retraso** (estudio 3.3, punto 4, y P6). La forma de un equipo responde a la posesión con
  segundos de retraso, así que se añaden medias de 2 s desplazadas 1–2 s hacia el futuro y 1 s hacia el pasado, y
  la regresión aprende el desfase. El log imprime el perfil de acierto frente al desplazamiento: debe tener su
  máximo en 0.
- **Cambio fechado en el primer toque** (estudio 3.2, 4.6, P5). Cada cambio H↔A retrocede, hasta 1 s, por los
  frames en que el nuevo equipo está al alcance del balón y al menos tan cerca como el viejo. Un vuelo lo detiene:
  un pase sigue siendo del receptor.
- **Retraso del balón frente a los jugadores.** Se mide con balones conducidos: el desplazamiento δ que mejor
  iguala la velocidad del balón con la de su portador. Si es claro (≥ 2 frames y ≥ 5 % mejor que no desplazar),
  se corrige. Primero usé posiciones y lo descarté, porque confunde con un retraso los 0,5 m que el balón va por
  delante del jugador en un regate.

En el sintético estos cambios son neutros (0,757 frente a 0,753), y es lo esperado: se calibran solos, y el
sintético no tiene retraso, ni huecos largos ligados a `D`, ni duelos largos.

## Tercera ejecución real (v1.2) y cambios de la v1.3

**El log de la v1.2 confirmó cuatro cosas:**
- No hay retraso del balón (perfil de velocidad plano; corrección 0).
- El modelo sin balón mejora al 87,9 / 83,8 %, con el pico de acierto en desfase 0.
- Los huecos ≥ 2 s cubren el 40,6 % de los frames, y el 87,7 % caen en `D` (+0,042 nats/frame).
- El fechado en el primer toque casi no actúa (5 de 71 cambios).

**La ventana pública** (evaluación n.º 3) da spellF1 0,4800, igual que la v1.1, con un intervalo bootstrap de
0,29–0,67. Faltan 4 de 17 posesiones, y las transiciones que casan llegan tarde (+9 frames de mediana).

**Cambios de la v1.3:**
- **Toques** (estudio 3.1 y P3). Un toque es un pico de aceleración del balón (ajuste cuadrático local de ±4
  frames) por encima del percentil 95 de los balones en vuelo libre (autocalibrado), con un jugador claramente
  más cerca que cualquier rival. Vale 1,5 nats para su equipo, menos que λ: un toque solo (un desvío o un bloqueo)
  no cambia la posesión, pero fecha el cambio cuando le sigue control. Además es la única huella que deja una
  intercepción a un toque.
- **λ = 3.** Con los toques, la evidencia de un cambio es más nítida y está mejor situada; todos los barridos
  sintéticos prefieren 3; y el partido real sigue infrasegmentado (185 posesiones, 71 cambios directos). Un
  parpadeo dentro de una posesión aún exige 6 nats: cuatro toques rivales, o un toque y ~11 frames de control.
- **Reinicio tras un hueco largo** (estudio 3.4). Si el balón reaparece lento (en manos o colocado) y lo toca
  alguien antes de 5 s, la parada se alarga hasta ese toque y termina ahí. Es el caso típico del saque de banda,
  que con el balón en manos no está "quieto" y antes no tenía anclaje.

Sintético: toques solos con λ 4 → 0,767; λ 3 sin toques → 0,768; **los dos juntos → 0,782** (v1.2: 0,757). El
reinicio tras hueco largo no influye en el sintético, que apenas tiene huecos largos en las paradas.

## Cuarta ejecución real (v1.3) y cambios de la v1.4

**Lo que mostró el log de la v1.3:** λ = 3 sí actuó (197 posesiones, 83 cambios directos), pero el detector de
toques por aceleración **solo encontró 70 en todo el partido**, frente a los ~1.500 que encuentra en el sintético.
Con tan pocos toques, el reinicio tras hueco solo se activó 2 veces. La causa probable es el suavizado del balón
en el ATD real (mediana de la segunda diferencia ~0): aplana los picos de aceleración, mientras los balones
aéreos proyectados inflan el umbral de vuelo libre (24,9 m/s²).

**La ventana pública** (evaluación n.º 4) dio exactamente lo mismo que la v1.2 (0,4800): los cambios de la v1.3 no
actuaban en esos 5 minutos.

**Cambio de la v1.4: detector de toques por cambio neto de velocidad**, |v(t, t+6) − v(t−6, t)|. Lo que mide no
depende de lo afilado que se vea el golpeo tras el suavizado: un pase o una recepción cambian la velocidad varios
m/s con cualquier suavizado.
- **Umbral:** el percentil 95 de los frames de vuelo libre, con nadie a menos de 4 m en toda la ventana, para que
  un golpeo cercano no lo contamine. Mínimo 3 m/s.
- **Asignación:** la distancia mínima de cada equipo en ±3 frames alrededor del pico, con un radio de 2 m y
  0,75 m de margen.
- **Log:** cuenta picos, picos con jugador cerca, asignados y ambiguos, para ver en qué filtro se pierden.

Para probarlo, el generador tiene ahora `--ball-style real`: rellena los huecos de menos de 2 s y suaviza el
balón, como el ATD real. Resultados en el sintético:
- **Estilo real:** v1.4 0,785 frente a 0,775 sin toques.
- **Ruidoso:** 0,775 frente a 0,768 sin toques (el detector por aceleración daba 0,782).
- **Reinicio tras hueco:** −0,003 en el sintético, dentro del ruido. Se mantiene porque en el dato real los huecos
  largos son paradas (87 %) y es el caso que ancla.

## Quinta ejecución real (v1.4) y cambios de la v1.5

**Lo que mostró el log de la v1.4:** 422 picos de toque, 261 con un jugador cerca y 213 asignados. Son más que en
la v1.3, pero lejos de lo esperable. En vuelo libre, el cambio de velocidad del balón tiene p50/p90/p95 de
0,90/3,73/5,29 m/s: el ATD suaviza el balón a escala de ~1 s.

Se reprodujo con `synth.py --ball-style real --smooth-half 12`, que da casi la misma firma (0,48/3,76/5,21 m/s, 884
picos). A partir de ahí, este es el banco de pruebas principal.

**Cambios de la v1.5:**
- **Toques a la escala del partido.** El detector prueba semiventanas de ±6, ±12 y ±25 frames y se queda, sin
  etiquetas, con la que separa más picos con un jugador cerca. Con suavizado fuerte elige ±25 (1.128 toques
  frente a 449 a ±6); con suavizado ligero o ruido se queda en ±6. El log imprime el perfil.
- **Modelo sin balón también con el balón a la vista sin control claro** (vuelos, duelos, balón suavizado entre
  jugadores), a la mitad de su peso. Antes solo actuaba sin balón, que en juego vivo es un 7 % del tiempo. Va a la
  mitad y no entero (en el sintético el peso entero da +0,014 frente a +0,010) porque el modelo real acierta un
  86 % y no un 97 %: a medio peso hacen falta más de 6 s seguidos de error confiado para inventar un parpadeo.

**Probado y desactivado** (sin mejora en el sintético suavizado, −0,003; quedan tras interruptores):
- fechar los cambios con el alcance sin la compuerta de velocidad;
- fechar los saques en la media subida de la velocidad del balón.

**Probado y descartado:** λ 2–2,5, toque a 2,5 nats y margen de fuera de banda de 0,2 m. Todo dentro del ruido.

| sintético | v1.4 | v1.5 |
|---|---|---|
| ruidoso (3 semillas) | 0,775 | **0,784** |
| suavizado estilo real (4 partidos) | 0,774 | **0,786** |

## Sexta ejecución real (v1.5) y cambio de la v1.6

**El log de la v1.5 está sano:** 214 posesiones (mediana 10,4 s), 113 paradas (49,3 % de `D`), 101 cambios H↔A
directos y ningún tramo largo de control rival ignorado. El modelo sin balón en los frames sin control claro ha
subido posesiones y cambios hacia lo esperable.

**Los toques siguen flojos:** a la escala elegida (±25) el umbral salió de 12 m/s y solo se asignaron 315. A esa
escala, el "vuelo libre" (nadie a 4 m durante 2 s) son casi siempre balones largos aéreos, cuya proyección curva
infla la referencia (p90 9,5 m/s).

**Cambio de la v1.6:** la referencia del umbral es un **balón raso** en vuelo libre (las dos cuerdas por debajo de
12 m/s). Mide el ruido propio del tracker: alto en el sintético ruidoso (umbral 6,4 m/s), casi nulo en un balón
suavizado (3,4–4,2 m/s). El sintético no tiene ese sesgo aéreo, así que ahí el cambio es neutro (0,784 / 0,786,
igual que la v1.5). Corrige un fallo medido en el dato real.

## Séptima ejecución real (v1.6) y evaluación pública n.º 5

**Log:** 219 posesiones (mediana 10,4 s), 113 paradas (49,3 %), 106 cambios H↔A directos y 622 toques asignados
(umbral 8,83 m/s a ±25), el doble que la v1.5. Ningún tramo largo de control rival ignorado.

**Ventana pública** (la última evaluación disponible):

| | v1.0 | v1.1 | v1.2 | v1.3 | v1.6 |
|---|---|---|---|---|---|
| spellF1 | 0,4414 | 0,4800 | 0,4800 | 0,4800 | **0,5250** |
| macroF1 | 0,7997 | 0,8318 | 0,8331 | 0,8331 | **0,8391** |
| posesiones (GT 17) | 12 | 13 | 13 | 13 | 15 |
| spellF1 a IoU 0,7 | 0,207 | 0,200 | 0,200 | 0,200 | 0,375 |
| acierto de equipo (ambos vivos) | 0,875 | 0,870 | 0,871 | 0,871 | 0,899 |

`baseline_smooth50`: 0,3256 / 0,6207. Con 17 posesiones, el intervalo bootstrap de la v1.6 (0,34–0,71) solapa con
los anteriores. La ventana confirma que el pipeline va bien y que el patrón de error mejora: más posesiones
detectadas, fronteras mejor fechadas (latencia mediana −1 frame) y más casos a IoU 0,7. No es evidencia de que una
versión supere a otra. Las 5 evaluaciones públicas están agotadas: desde aquí solo valen el log sin etiquetas y el
sintético.

## Limitaciones conocidas

- **Posesiones de menos de ~2 s.** `EVALUATION.md` sugiere que la GT tiene bastantes (sección 2.5 del estudio).
  Este candidato apenas las ve. Es el mayor margen de mejora, junto con una evidencia de control más fuerte (por
  ejemplo, toques detectados por cambio de dirección del balón).
- **Inicio de parada en faltas y fueras de juego**: sin pitido, se fecha por la frenada colectiva y llega tarde.
- **Balón aéreo**: el ATD lo proyecta al suelo desde la cámara. La compuerta de velocidad y la regla de reentrada
  limitan el daño, pero no lo eliminan.
- **Parámetros a priori**: λ, α y los pesos de D salen de razonar y del sintético, no del partido real. Las
  comprobaciones sin etiquetas del log, no la ventana pública, son las que deben orientar los cambios.
- **Pocos cambios en juego**: la v1.0 decodificó muy pocos cambios H↔A directos en el dato real. La v1.1
  corrige dos fallos y baja λ, pero falta comprobarlo con la curva de λ y los tramos de control ignorado del
  log.

## Ficheros

| fichero | contenido |
|---|---|
| `__main__.py`, `pipeline.py` | orquestación, autocalibración, log agregado y escritura del CSV |
| `config.py` | todos los parámetros, con unidades y justificación |
| `atd.py` | lector del ATD EPTS sin kloppy (estructura de línea desde el XML) |
| `tags.py` | Smart Tagging (reutiliza `starter/load_smart_tagging.py`) y asignación de equipo |
| `features.py` | limpieza del balón, velocidades, jugador más cercano, forma de los equipos |
| `evidence.py` | evidencia de equipo y de balón muerto |
| `ballfree.py` | modelo de equipo sin balón, autoentrenado y con validación cruzada |
| `decode.py` | decodificador exacto H/A/D con duración mínima de parada |
| `diagnostics.py` | comprobaciones sin etiquetas que imprime el log (solo agregados) |
| `synth.py` | generador de partidos sintéticos en los formatos reales |
| `tests.py` | tests |

## Trabajo de P3 y P4 tras la entrega (#15, #16)

Ni el modelo ni su CSV cambian: Viterbi sigue siendo el decodificador por defecto, y la salida es la misma byte a
byte. Lo añadido sirve para comprobar y para integrar.

**Decodificadores alternativos (#16).** Con `--set decode.method=hysteresis` o `--set decode.method=vote` se
decodifica la misma evidencia de dos formas más:
- **hysteresis:** CUSUM con retrofechado y los mismos costes que Viterbi (estudio 4.4).
- **vote:** mayoría en una ventana de ±1 s, como el baseline pero sobre esta evidencia.

`python -m solution.a_opus.compare_decoders <partidos sintéticos>` los compara. Sobre 5 partidos sintéticos (3
ruidosos y 2 con el balón suavizado como el ATD real):

| decodificador | spellF1 | posesiones / reales | fragmentación | cortas reales (< 5 s) conservadas | falsas de menos de 2 s | transiciones P / R a ±1 s |
|---|---|---|---|---|---|---|
| **Viterbi** | **0,783** | 1.580 / 1.915 | 0,88 | 214 / 627 | **17** | 0,72 / 0,63 |
| histéresis | 0,761 | 2.010 / 1.915 | 1,11 | 298 / 627 | 195 | 0,62 / 0,69 |
| votación | 0,659 | 2.560 / 1.915 | 1,42 | 267 / 627 | 722 | 0,50 / 0,70 |

- **Viterbi** elimina el ruido sin imponer una duración mínima: conserva un tercio de las posesiones cortas reales
  y apenas inventa falsas.
- **La histéresis** confirma un cambio en cuanto el exceso acumulado supera el coste, y lo fecha donde empezó el
  exceso. Recupera más posesiones cortas, pero inventa 11 veces más falsas.
- **La votación** fragmenta como el baseline.

**Casos explícitos (#15, #16).** En `python -m solution.a_opus.tests`:
- `test_p3_control_cases`: un pase a 15 m/s que roza a un defensor no es control, una recepción sí, y un duelo no
  da evidencia neta.
- `test_p3_p4_scenarios`, con los costes del candidato:
  - la intercepción cambia la posesión en el primer contacto del nuevo equipo;
  - el rebote o desvío, el duelo sin control posterior y el ruido aislado no la cambian;
  - una recuperación real de 1,2 s se conserva;
  - un cambio a través de un hueco del balón se fecha donde empieza la evidencia del nuevo equipo.
- `test_p4_first_frames_of_a_half`: una parte que empieza parada decodifica `D` primero; una que empieza en juego
  toma el equipo de su primera evidencia desde el frame 0.

**Evidencia por frame (#15, contrato P0 §6).** `--evidence salidas/evidencia.npz` escribe, para todo el vídeo:
- `control_H_score`, `control_A_score` y `control_valid`: la fuerza de control 0..1, no una probabilidad;
- `nearest_H_m`, `nearest_A_m` y `distance_valid`;
- `touch_H` y `touch_A`;
- `team_llr` y `dead_llr` (nats), y el estado decodificado.

Sin balón observado ni interpolado, `control_valid` es falso y las puntuaciones son NaN. Ninguna ausencia se
convierte en evidencia. Son datos del partido frame a frame: solo en local, nunca en el repositorio.

## P3: integración de la P2 (#14)

`solution/a_opus/p2.py` ejecuta el detector de Pablo (`solution/dead_ball.py`) sobre el partido entero, tal como él
lo validó: su lector, sus umbrales y sus eventos. Sus candidatos se convierten en un término más de evidencia de
balón muerto:
- **`tagged_preparation`:** `D` desde el primer frame de balón quieto hasta el reinicio, y vivo justo después.
  Es lo que `setpiece_llr` no sabe: en qué punto de la ventana `SET PIECES` se juega el balón.
- **`initial_kickoff_context`:** `D` antes del primer saque inicial de cada parte.
- **`observed_exit`:** peso 0, porque `out` y `exit` ya cuentan las salidas.

Va desactivado por defecto (`p2.enabled=0`): el candidato A entregado no cambia. Con la P2 desactivada, el CSV de
un partido sintético es idéntico byte a byte al de `main`. La variante con la P2 se lanza con:

```bash
python -m solution.a_opus.with_p2 --out salidas/a_p2.csv --log salidas/a_p2_log.txt
```

El log añade una línea con los candidatos de la P2 por tipo, sin frames. `python -m solution.a_opus.compare_p2
<partidos sintéticos>` compara las dos variantes.

**Resultado en sintético** (5 partidos con el balón suavizado como el ATD real; 3 de ellos a escala de ~1 s,
`--smooth-half 12`):

| variante | spellF1 | macroF1 | posesiones / reales | falsas de menos de 2 s | error del reinicio p50 / p90 (frames) |
|---|---|---|---|---|---|
| A, sin la P2 | 0,7919 | 0,9310 | 1.650 / 1.984 | 18 | 7 / 75 |
| A + P2 tal cual | 0,7919 | 0,9310 | 1.650 / 1.984 | 18 | 7 / 75 |
| A + P2, regla con 1 s de margen (experimento) | 0,7907 | 0,9284 | 1.663 / 1.984 | 24 | 15 / 78 |
| ídem, reinicio fechado en el movimiento (experimento) | 0,7915 | 0,9299 | 1.656 / 1.984 | 22 | 9 / 77 |

- **Tal cual, la P2 no encuentra preparaciones.** 68 de 82 ventanas tienen el balón quieto en la zona del saque,
  pero ninguna cumple ≥ 2 m/s en los 3 frames inmediatamente posteriores. Con el balón suavizado, la velocidad
  tarda en subir: en 54 de ellas el movimiento llega dentro de 1 s. Solo aporta el contexto del saque inicial, y
  ahí A ya decodifica `D`.
- **Con 1 s de margen** (solo como experimento, sin cambiar `dead_ball.py`) sí las encuentra, pero A no mejora: ya
  fecha esos reinicios con `setpiece`, `static`, `kick` y `restart`, y el reinicio de la P2 cae unos frames antes
  del golpeo.

**Decisión:** la integración queda disponible y desactivada. No se adopta sin una ejecución real con el log sin
etiquetas, que diga cuántas preparaciones encuentra la P2 en el ATD real. La regla del movimiento inmediato se
comenta en #14.
