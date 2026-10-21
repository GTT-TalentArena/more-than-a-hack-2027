# Estudio: el modelo de posesión

> **More than a Hack 2027 · fase 1** · estudio previo a programar · 20 de octubre de 2026
>
> **Fuentes:** la documentación y el código público del reto (`CHALLENGE.md`, `EVALUATION.md`, `DATA.md`,
> `FAQ.md`, `RULES.md`, `OVERVIEW.md`, `evaluation/possession_metrics.py`, `starter/`) y literatura publicada,
> enlazada en la [sección 8](#8-fuentes).
>
> **Datos del partido:** no se ha abierto ninguno. Ni `data/`, ni `evaluation/gt/*.csv`, ni
> `evaluation/results/*.csv`. Las cifras del partido que aparecen aquí son las que publican los documentos del
> reto. Lo que exige mirar datos queda como experimento local en la [sección 7](#7-experimentos-locales-para-el-equipo).
> Las simulaciones de la [sección 2](#2-cómo-puntúa-la-métrica) usan secuencias **sintéticas** y el scorer
> oficial; el script está en el [apéndice](#apéndice-simulación-sintética-del-scorer).

---

## Resumen

1. **`spellF1` cuenta posesiones, no frames.** Cada error estructural (un parpadeo, un hueco `D` falso dentro de
   una posesión, una posesión corta real que no vemos) cuesta del orden de **1–1,4 / N**, donde N es el número de
   posesiones reales. Con N de unos pocos cientos, cada error vale **≈0,3–0,4 puntos**. Además, el número de
   posesiones predichas pone un techo duro: si predecimos el doble de las reales, `spellF1 ≤ 0,67`.
2. **No ver el balón no es balón muerto.** El baseline escribe `D` cuando no ve el balón, y el balón falta en el
   41 % de los frames puntuados. Cada `D` falso dentro de una posesión la parte en dos. Separar "no lo veo" de
   "está muerto" es la mejora más barata que tenemos.
3. **La ground truth tiene muchas posesiones muy cortas.** Se deduce de la tabla de retrasos de `EVALUATION.md`:
   un retraso uniforme de 8 frames solo puede costar 0,11 si **alrededor del 10 % de las posesiones duran menos de
   1–2 s** ([2.5](#25-una-inferencia-la-gt-tiene-muchas-posesiones-cortas)). Por eso suavizar más no sale gratis:
   el filtro que borra parpadeos también borra posesiones reales, y las dos cosas cuestan casi lo mismo.
4. **Las fronteras se puntúan casi al frame.** Un frame de retraso es gratis, 3 frames cuestan ~2 puntos, 8 frames
   ~11 y 1 s ~35 (`EVALUATION.md`). Un suavizado que desplaza fronteras pierde mucho aunque acierte el número de
   posesiones.
5. **`X` significa "repite mi etiqueta anterior".** Dentro de una posesión es inocuo; en un cambio de posesión es
   un retraso. Escribir explícitamente la etiqueta que se mantiene da el mismo `spellF1` y mejor `macroF1`.
6. **Qué proponemos:** pasar de "jugador más cercano en cada frame + ventana de voto" a un **detector de `D`**,
   **eventos de control con regla de mantener el último equipo**, **decodificación temporal (HMM/Viterbi con coste
   de cambio)** y **refinamiento de fronteras** al frame del toque.
7. **Estado del arte:** hay métodos de reglas (Link y Hoernig 2017; Vidal-Codina et al. 2022), modelos aprendidos
   de posesión y balón muerto (Borghesi et al. 2023, con TCN), y modelos que funcionan **sin balón** a partir de
   los jugadores (Kim et al. 2023; PathCRF, Kim et al. 2026, con CRF y Viterbi). La segmentación temporal de
   acciones conoce el mismo problema con el nombre de *sobresegmentación*, y su métrica F1@k es prácticamente
   `spellF1`.
8. **Hay datos externos con la misma semántica que nuestra GT.** El dataset abierto Sportec/DFL (7 partidos,
   CC-BY 4.0) trae para el balón `BallPossession` y `BallStatus`. Nos permite elegir parámetros sin tocar la
   ventana pública, que tiene solo 17 posesiones.

---

## 1. Reglas H/A/D/X

### 1.1 Qué cuenta como posesión

`CHALLENGE.md` lo define así:

- **Con el balón en juego, siempre hay un equipo en posesión.** No existen los estados "disputado", "transición"
  ni "desconocido": todo frame puntuado es `H`, `A` o `D`.
- **Cambio de posesión:** se produce cuando un jugador del equipo rival consigue posesión **controlada**.
- **Balón suelto o disputado:** la posesión se queda con **el último equipo que la tuvo**. Es, literalmente, una
  regla de histéresis: no se cambia hasta que hay control del otro equipo.
- **No cuentan como cambio:** un toque sin control, una desviación de un pase que no lo intercepta y un duelo aéreo
  ganado sin control posterior.
- **Señales de "control" que sugiere el reto:** que el jugador conserve el balón unos segundos, o que el equipo
  encadene más de dos pases.
- **Tras cada reinicio hay un poseedor claro.** El problema es detectar cuándo cambia después.
- **Una posesión es una racha máxima de un mismo equipo con el balón vivo.** `H H H A A` son dos posesiones.
  `H H D D H H` también son dos, separadas por una parada, aunque sea el mismo equipo.

### 1.2 Cómo se construyó la ground truth (y qué implica)

Según `CHALLENGE.md`, la GT **sale de tracking corregido**, no de alguien viendo vídeo ni de datos de eventos. La
derivación es mecánica: un frame es `D` donde el tracking corregido marca el balón muerto y, en el resto, lleva el
equipo que ese tracking señala como dueño. **No se suaviza, ni se interpola, ni se retoca a mano.**

Esto tiene tres consecuencias:

1. Lo que hay que imitar es el **"equipo dueño del balón" de un tracking corregido**, no la idea intuitiva de
   posesión. Es el mismo tipo de campo que llevan los feeds profesionales. El dataset abierto de la DFL, por
   ejemplo, trae para el balón `BallPossession` (1 = local, 2 = visitante) y `BallStatus` (0 = parado,
   1 = en juego), y kloppy los convierte en `ball_owning_team` y `ball_state`
   ([Bassek et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/);
   [deserializador de kloppy](https://github.com/PySport/kloppy/blob/master/kloppy/infra/serializers/tracking/sportec/deserializer.py)).
2. **La GT no se suavizó.** Si el dueño cambia un instante, en la GT hay una posesión corta. La
   [sección 2.5](#25-una-inferencia-la-gt-tiene-muchas-posesiones-cortas) indica que esas posesiones existen y no
   son raras.
3. **La referencia es la ventana pública.** El reto dice que, si nuestra lectura de la definición choca con los 5
   minutos públicos, manda la GT. Hay que mirar en local cómo están etiquetados los casos dudosos (rebotes,
   despejes, duelos) antes de fijar reglas ([experimento L5](#7-experimentos-locales-para-el-equipo)).

### 1.3 Cuándo es `D`

- `D` = **el balón no está en juego**, tal como lo marca el tracking corregido: fuera del campo, falta pitada,
  sustitución, gol, antes de cada reinicio...
- **No se pide quién es dueño de un balón muerto.** El tracking corregido nombra un equipo incluso con el balón
  parado (el que va a sacar, o el último que tocó), pero la GT lo descarta: con balón muerto, `D`.
- **Una trampa documentada (`FAQ.md`):** la segunda parte se puntúa desde el frame 110 808, pero el saque inicial es
  en el 113 742. Esos 2934 frames están puntuados y son todos `D`. La primera parte, en cambio, se puntúa desde el
  propio saque (frame 11 185).
- **Peso de `D`:** en la ventana pública hay 1469 frames `D` de 7500 (~20 %, `DATA.md`). Como cada parada separa
  posesiones, **los bordes de `D` son bordes de posesión**. Un `D` que no detectamos fusiona dos posesiones; un `D`
  que nos inventamos parte una en dos.

### 1.4 Cuándo compensa `X`

El scorer (`fill_abstentions` en `possession_metrics.py`) trata `X` de forma distinta según la métrica:

| dónde | `macroF1` | `spellF1` (ranking) |
|---|---|---|
| frame **no puntuado** (antes del partido, descanso, después) | no cuenta | no cuenta |
| frame puntuado, **dentro de una posesión** | fallo | **gratis**: se rellena con la última etiqueta de esa mitad |
| frame puntuado, **en un cambio de posesión** | fallo | **caro**: la etiqueta vieja se arrastra = retraso |
| frame puntuado, **al principio de una mitad** | fallo | se rellena hacia atrás con la primera etiqueta |

**Regla práctica:**

- Fuera de los tramos puntuados, `X`.
- Dentro de una posesión con el balón perdido, **escribir explícitamente la etiqueta que se mantiene**. Para
  `spellF1` es idéntico a `X` (el scorer hace ese mismo relleno), y para `macroF1`, que desempata, puntúa si
  acierta. `X` solo tiene sentido si la alternativa fuera inventar un cambio.
- En un cambio de posesión, **adivinar siempre**. En la simulación del apéndice, poner `X` en el segundo que sigue
  a cada cambio cuesta entre 13 y 41 puntos de `spellF1` según cuántas posesiones cortas haya.
- **Nunca usar `D` como "no sé".** `D` sí parte posesiones. Es justo el error del baseline (sección 3.3).

### 1.5 Frames puntuados y ventana pública

| tramo | frames de vídeo | puntuado |
|---|---|---|
| primera parte | 11 185 – 90 651 | sí |
| descanso | 90 652 – 110 807 | no |
| segunda parte (incluye 2934 frames `D` antes del saque) | 110 808 – 190 197 | sí |
| ventana pública (GT en el repo) | 11 185 – 18 684 | 17 posesiones, media 14,2 s |

En total hay 158 857 frames puntuados. El ATD empieza en `frame_id = 1`, así que `video_frame = frame_id − 1`
(`DATA.md`).

---

## 2. Cómo puntúa la métrica

### 2.1 `macroF1`: la vista por frame

Es la media sin ponderar del F1 de `H`, `A` y `D` sobre los frames puntuados. Un `X` cuenta como fallo. El suelo
práctico está en ~0,16 y las diferencias por debajo de ~0,01 son ruido. **Es casi ciega a la estructura:** la
inmensa mayoría de frames están en mitad de una posesión, donde no pasa nada.

### 2.2 `spellF1`: la vista por posesión (con la que se ordena el ranking)

Así lo calcula el código (`possession_metrics.py`, `spell_scores`):

1. Se rellenan las `X` de la predicción (hacia delante dentro de cada mitad).
2. Se trocea **cada mitad por separado** en rachas de etiqueta constante. Ninguna posesión cruza el descanso.
3. Las **posesiones** son las rachas de `H` o de `A`. Las rachas de `D` no son posesiones, pero **separan**.
4. Para cada pareja (posesión real, posesión predicha) **del mismo equipo** que se solapan, se calcula el IoU
   temporal: intersección / unión.
5. Se emparejan **uno a uno**, de mayor a menor IoU (voraz). Ninguna posesión real se acredita dos veces.
6. Para cada umbral de IoU (0,3, 0,4, 0,5, 0,6 y 0,7) se calcula
   `F1 = 2·TP / (n_pred + n_real)`. `spellF1` es la media de esos cinco F1.

Es la misma idea que el **F1@k segmental** de la segmentación temporal de acciones
([Lea et al. 2017](https://arxiv.org/abs/1611.05267)). Allí, si varias detecciones caen dentro de una misma acción
real, solo una cuenta como acierto y el resto como falsos positivos. La métrica se diseñó precisamente para
penalizar la **sobresegmentación**.

**Un techo que conviene tener presente.** Como `TP ≤ min(n_pred, n_real)`:

```
spellF1 ≤ 2·min(r, 1) / (1 + r),   con r = n_pred / n_real
```

| r = posesiones predichas / reales | 0,5 | 0,8 | 1 | 1,25 | 1,5 | 2 | 3 | 5 |
|---|---|---|---|---|---|---|---|---|
| techo de `spellF1` | 0,67 | 0,89 | 1 | 0,89 | 0,80 | 0,67 | 0,50 | 0,33 |

`validate_submission.py` imprime nuestro número de posesiones. En la ventana pública, el real es 17. En el partido
completo no se publica, aunque una extrapolación lineal de la ventana pública da un orden de **300–400** (es una
extrapolación, no un dato).

### 2.3 Qué errores castiga y cuánto

Costes medidos con el scorer oficial sobre una secuencia sintética de 100 posesiones de 10 s
([apéndice](#apéndice-simulación-sintética-del-scorer)). Para otro N, el coste escala como 1/N:

| error | qué le pasa a la estructura | coste en `spellF1` |
|---|---|---|
| parpadeo de 1 frame del otro equipo **en mitad** de una posesión | 1 posesión real → 3 predichas | **≈ 1,4 / N** |
| parpadeo cerca de una frontera | +1 posesión espuria | ≈ 1,0 / N |
| hueco `D` en mitad de una posesión (p. ej. por no ver el balón) | 1 → 2 | ≈ 1,1 / N |
| **perder** una posesión real de 1 s entre dos del mismo rival | 3 reales → 1 predicha | **≈ 1,2 / N** |
| detectar esa posesión de 1 s, pero 5 frames tarde | ninguno | ≈ 0,2 / N |
| retrasar 8 frames todas las fronteras, si todas las posesiones duran 10 s | ninguno | 0 |

Las conclusiones son tres:

- **Los errores estructurales cuestan todos lo mismo, del orden de 1/N.** Da igual que sea un parpadeo, un `D`
  falso o una posesión corta perdida. Con N ≈ 350, cada uno vale ≈ 0,3–0,4 puntos, y 50 errores así son ~15–20
  puntos.
- **Por eso la duración mínima o el suavizado no tienen un óptimo obvio.** Un filtro gana ≈ 1,4/N por cada
  parpadeo que borra y pierde ≈ 1,2/N por cada posesión real que borra. El umbral bueno es aquel en el que, para
  esa duración, hay tantas posesiones falsas como reales. Hay que **medirlo**, no suponerlo.
- **El retraso solo duele en las posesiones cortas.** Con posesiones largas, 8 frames de retraso son gratis. En
  la GT real cuestan 11 puntos, lo cual nos dice algo de la GT (2.5).

### 2.4 Por qué el parpadeo hunde `spellF1`

Ejemplo: una posesión real de `H` de 10 s (250 frames). En el frame 125 la nube de jugadores hace que el más
cercano al balón sea un rival durante un solo frame:

```
real:     HHHHHHHHHH...HHHHHHHHHHHHHHHHHHHHHHHHHHHH          1 posesión
predicho: HHHHHHHHHH...HHHH A HHHHHHHHHHHHHHHHHHHHHHH        3 posesiones: H(125) A(1) H(124)
```

- A IoU ≤ 0,5, la primera mitad (IoU = 125/250 = 0,5) casa con la real. La segunda mitad y la `A` son falsos
  positivos.
- A IoU 0,6 y 0,7, no casa ninguna: la posesión real se pierde y las tres predichas son falsas.

Un frame de 250 cambia 0,4 % de los frames (nada para `macroF1`), pero destruye una posesión y crea dos falsas. El
baseline sin suavizar hace esto cientos de veces. Por eso `baseline_raw` tiene `macroF1` 0,65 y `spellF1` 0,05: con
"varias veces más posesiones que el partido" (`FAQ.md`), el techo de la tabla de 2.2 ya es de 0,5 o menos, antes de
contar un solo fallo.

### 2.5 Una inferencia: la GT tiene muchas posesiones cortas

`EVALUATION.md` publica el `spellF1` de una predicción perfecta pero retrasada: 1 frame → 1,0000; 3 → 0,9818;
8 → 0,8933; 1 s → 0,6539.

Con un retraso uniforme δ, cada posesión conserva su longitud L, y su IoU con la real es `(L − δ) / (L + δ)`. Casa
con el umbral t solo si `L ≥ δ·(1 + t)/(1 − t)`:

| retraso δ | L mínima para casar a IoU 0,3 | a IoU 0,7 | `spellF1` publicado | posesiones que no casan (media) |
|---|---|---|---|---|
| 8 frames | 15 frames (0,6 s) | 45 frames (1,8 s) | 0,8933 | ~11 % |
| 25 frames (1 s) | 46 frames (1,9 s) | 142 frames (5,7 s) | 0,6539 | ~35 % |

Como el número de posesiones no cambia, `F1 ≈ TP/N`, así que perder 0,107 significa que, de media sobre los cinco
umbrales, ~11 % de las posesiones no casan. Eso solo es posible si **alrededor del 10 % de las posesiones de la GT
duran menos de ~1–2 s**, y si **del orden de un tercio duran menos de ~2–6 s**.

La simulación lo confirma: con una distribución sintética "normal" (lognormal de mediana ~9 s), 8 frames de retraso
solo cuestan 0,017. Para acercarse al 0,893 publicado hay que meter entre un 20 % y un 40 % de posesiones
"relámpago" de 0,3–2 s (apéndice, sección 0).

**Cautelas:** `EVALUATION.md` no dice si esa tabla se calculó sobre el partido completo o sobre la ventana
pública, y la deducción es aproximada (supone que el número de posesiones predichas y reales coincide). Hay que
comprobarlo en local con la GT pública ([L2](#7-experimentos-locales-para-el-equipo)). Si se confirma, **cambia el
diseño**: no se pueden imponer duraciones mínimas de varios segundos, y la precisión de las fronteras pesa mucho.
Además, choca en parte con "un toque sin control no cuenta": habrá que ver en vídeo qué son esas posesiones cortas.

### 2.6 Ruido, ventana pública y diagnóstico

- **Ruido:** en el partido completo, las diferencias de `spellF1` por debajo de ~0,04 son ruido. En la ventana
  pública es mucho peor: 17 posesiones, y **una posesión mal resuelta mueve unos 6 puntos**. El propio reto lo
  demuestra: en la ventana pública gana `smooth125` (0,42 frente a 0,33) y en el partido completo gana `smooth50`
  (0,2433 frente a 0,2242).
- **Bootstrap:** `python evaluation/run_evaluation.py --bootstrap 1000` remuestrea posesiones y da intervalos. Si
  se solapan, la diferencia no está demostrada.
- **Diagnósticos que ya calcula el scorer** y que conviene mirar siempre: `n_pred_spells` frente a `n_gt_spells`,
  la duración media, `alive_dead_f1` (solo vivo/muerto), `team_acc_both_alive` (solo equipo, cuando los dos dicen
  vivo), la precisión y el recall de transiciones a ±12 y ±25 frames (un recall de ~1 con precisión ~0 es
  parpadeo) y `evaluation/reports/<nombre>_transitions.csv`, que lista cada cambio como `matched`, `missed` o
  `spurious` con su frame, para ir a verlo en el vídeo.

---

## 3. Cambios de posesión

### 3.1 Señales para detectar un cambio

| señal | qué capta | dónde falla |
|---|---|---|
| **jugador más cercano** al balón (baseline) | quién está junto al balón | en pases (el balón pasa cerca de rivales), balones aéreos (no tenemos altura), duelos y balones entre dos jugadores. Cambia de equipo en cuanto el balón está a medio camino |
| **zona de posesión**: balón a menos de R de un jugador | contacto posible | R depende del proveedor: Vidal-Codina et al. usan 0,5 m o 1 m; databallpy, 1,5 m por defecto. Hay que calibrarla con nuestro ruido |
| **cambio en la cinemática del balón** (dirección o velocidad) con un jugador en la zona | **toque real**: recepción, pase, desvío | requiere velocidad del balón fiable. Con el balón visible a ratos, la derivada es ruidosa |
| **frenada del balón junto a un jugador** (recepción) | **control** | — |
| **pico de aceleración del balón** (≥ 4 m/s² en Link y Hoernig 2017) | golpeo, inicio de pase | ruido de tracking |
| **duelo**: rivales a < ~1 m del balón | situación disputada → no decidir | — |
| **confirmación de control**: el balón sigue en la zona k frames, o el siguiente toque es del mismo equipo | distingue control de rebote o desvío (lo que pide el reto) | introduce retraso si el cambio se fecha al confirmar en vez de en el primer toque |
| **contexto colectivo**: quién presiona, hacia dónde corren los bloques, la forma de cada equipo | posesión sin ver el balón | más difícil; es lo que aprenden los modelos "sin balón" (sección 5) |
| **Smart Tagging**: `ATTACKING TRANSITION` y `DEFENSIVE TRANSITION` (24 + 24), fases con equipo | candidato a cambio y prior de equipo | son ventanas de fase, no instantes. En los saques iniciales se abren ~3,5 s antes. Es automático, con falsos positivos y negativos |

Un apunte sobre el etiquetado de fases. Si entendemos bien las definiciones de `OVERVIEW.md`, el tag `Team` es el
equipo **que realiza** la fase. Entonces `BUILD UP`, `PROGRESSION` y `CREATING CHANCES` de Barcelona son evidencia de
`H`, pero `DEFENDING IN …` de Barcelona es evidencia de `A`. Hay que comprobarlo en local antes de usarlo.

### 3.2 Esquema propuesto: eventos de control + mantener el último equipo

Es la regla del reto convertida en algoritmo y la misma estructura que el método de reglas de
[Vidal-Codina et al.](https://arxiv.org/abs/2202.00804) (zona de posesión, zona de duelo, ganancia por cambio de
dirección o velocidad):

```
estado = equipo que reinicia tras cada D
para cada frame de juego vivo:
    si se ve el balón y hay un TOQUE (jugador a < R y cambio de dirección/velocidad del balón):
        si hay rivales a < R_duelo: duelo -> no decidir todavía
        si el equipo del toque != estado y se CONFIRMA el control
           (k frames en zona, o siguiente toque del mismo equipo):
            cambio de estado FECHADO EN EL PRIMER TOQUE, no en la confirmación
    en otro caso: estado se mantiene (balón suelto, disputado o no visible)
```

**La fecha del cambio importa.** Confirmar el control con k frames de espera está bien, pero el cambio se escribe
hacia atrás, en el frame del primer toque. Como el procesamiento es offline, podemos usar el futuro. Si no,
introducimos un retraso sistemático de k frames, y 8 frames ya cuestan ~11 puntos (2.5).

### 3.3 Cuando no se ve el balón (41 % de los frames puntuados)

Es el centro del problema (`DATA.md`): falta en 64 643 de 158 857 frames puntuados, **y desproporcionadamente en los
momentos que importan**: áreas llenas, duelos, balones aéreos.

**Qué hace hoy el baseline:** si no hay balón, `D`. Con la ventana de ±50, un hueco de más de ~4 s sigue siendo
`D`. Así, todo hueco largo dentro de una posesión la parte en dos (≈ 1,1/N cada vez, sección 2.3), y todo `D` real
con balón visible queda como posesión. Es la debilidad más clara del baseline, y su propio docstring lo reconoce.

**Estrategia propuesta, por tipo de hueco:**

1. **Hueco corto (≲ 1 s) con el mismo equipo a los dos lados:** mantener la etiqueta. Si hace falta, interpolar la
   posición del balón (lineal o con física simple).
2. **Hueco con equipos distintos a los dos lados:** el cambio ocurre dentro del hueco. Hay que situarlo en el
   instante más probable: el rival que más se acerca a la trayectoria interpolada, o el cambio de comportamiento
   colectivo. **Nunca dejarlo en `X`**, porque arrastraría la etiqueta vieja hasta el final del hueco.
3. **Hueco largo:** decidir entre "sigue la posesión" y "balón muerto" con evidencia de parada (3.4), no por la
   mera ausencia.
4. **Modelos sin balón:** la literatura muestra que la posesión de equipo se puede inferir solo con los jugadores.
   PathCRF publica un 92,4 % de acierto por frame en posesión de equipo, en datos DFL limpios
   ([Kim et al. 2026](https://arxiv.org/abs/2602.12080)). Ball Radar infiere poseedor y trayectoria del balón a
   partir de los jugadores ([Kim et al. 2023](https://arxiv.org/abs/2306.08206)). En baloncesto ya se hizo en 2015
   ([Wei et al.](https://openaccess.thecvf.com/content_iccv_2015_workshops/w21/html/Wei_Predicting_Ball_Ownership_ICCV_2015_paper.html)).
   Es la vía para los huecos largos con juego vivo.

**Una pregunta que hay que responder en local:** ¿el ATD automático deja de dar balón cuando está muerto? Algunos
proveedores señalan así el balón muerto: Vidal-Codina et al. lo describen para Track160 y Hawk-Eye. Si en nuestros
datos la ausencia correlaciona con `D`, la ausencia **larga** es evidencia de parada. Si no, no lo es
([L4](#7-experimentos-locales-para-el-equipo)).

### 3.4 Detectar `D` (porque sus bordes son bordes de posesión)

Señales candidatas, todas a validar:

- **Balón fuera del rectángulo** del campo (coordenadas normalizadas < 0 o > 1, con un margen), sobre todo justo
  antes de que desaparezca.
- **Quietud colectiva:** la velocidad media de los jugadores cae y se queda baja unos segundos (el ATD da la
  velocidad de cada jugador).
- **Balón quieto** en un punto de reinicio: esquina, banda, área pequeña, punto de penalti, centro del campo.
- **Formaciones de reinicio:** saque inicial (cada equipo en su campo), córner, saque de puerta...
  [Vidal-Codina et al.](https://arxiv.org/abs/2202.00804) detectan el tipo de reinicio por patrones de posición
  durante la parada.
- **Smart Tagging `SET PIECES`:** 59 reinicios con tipo. El equipo falta (`N/A`) en todos los saques de banda.
- **Fin de la parada = reinicio:** pico de aceleración del balón desde parado. El equipo del primer toque es el
  poseedor inicial ("tras cada reinicio hay un poseedor claro").
- El tramo de la segunda parte anterior al saque (2934 frames) debería salir **de un detector de saque inicial**,
  no escrito a mano. `RULES.md` exige que las etiquetas salgan de un algoritmo.

---

## 4. Continuidad temporal: técnicas

Dos premisas para todo lo que sigue:

1. El procesamiento es **offline**: cada frame puede mirar el futuro. No hay ninguna razón para usar filtros
   causales que introducen retraso.
2. Por lo visto en la sección 2, el suavizado ideal **borra parpadeos sin borrar posesiones cortas reales ni mover
   fronteras**. Ningún filtro ciego lo consigue: hace falta evidencia, como el toque o el control.

### 4.1 Ventana de voto mayoritario (el baseline)

Es `smooth()` en `starter/baseline.py`: voto centrado de ±w frames entre `H` y `A`, ignorando los frames sin balón.
Si la ventana no ve ningún balón, `D`. Con empate, `H`.

- **Ventajas:** trivial y simétrica (centrada, sin retraso sistemático).
- **Inconvenientes:** borra cualquier posesión de menos de ~w frames. Las fronteras caen donde se cruza el 50 % del
  voto, que se desplaza si el balón falta de forma desigual a cada lado. Ignora la confianza. Un solo w para todo.
  Mezcla "no veo" con `D`.
- **Parámetro:** w. Los datos publicados ya muestran el dilema: ±50 da 0,2433, ±125 da 0,2242 y ±25 da 0,1996 en el
  partido completo.

### 4.2 Filtro de mediana o moda y morfología

Sobre etiquetas categóricas, la "mediana" es la moda en la ventana, casi lo mismo que 4.1. La alternativa
morfológica (apertura y cierre sobre la máscara de cada clase) es exactamente **eliminar rachas de menos de k
frames**: es la duración mínima de 4.3.

- **Ventajas:** control explícito de qué se borra, y k distinto por clase (`D` frente a `H`/`A`).
- **Inconvenientes:** el orden de las operaciones cambia el resultado y sigue siendo ciego a la evidencia.

### 4.3 Duración mínima de posesión

Se fusionan las rachas más cortas que k con sus vecinas. Si los dos vecinos son del mismo equipo, se absorbe. Si no,
se corta por el punto de mayor evidencia.

- **Coste techo**, aplicado a una predicción **perfecta** (simulación, apéndice, sección 3):

  | duración mínima | 1 s | 2 s | 3 s | 5 s |
  |---|---|---|---|---|
  | GT sintética sin posesiones relámpago | 0,997 | 0,961 | 0,915 | 0,764 |
  | GT sintética con 20 % de relámpago | 0,958 | 0,856 | 0,805 | 0,714 |

  Si la sección 2.5 está en lo cierto, una duración mínima de 2–3 s **nos quita 15–20 puntos aunque el resto fuera
  perfecto**. Una duración mínima de unos pocos frames (0,2–0,5 s) sí puede ser rentable contra el parpadeo puro.
- **Parámetros:** k por clase. `D` probablemente admite un mínimo mayor que las posesiones, porque una parada
  rara vez dura menos de un par de segundos (a comprobar).

### 4.4 Histéresis (máquina de estados)

Se mantiene el estado actual y solo se cambia cuando la evidencia del otro estado supera un umbral de entrada
θ_on durante k frames (o una suma acumulada, al estilo CUSUM). Para volver hace falta otro umbral, θ_off. Es la regla
"el balón suelto se queda con el último" llevada a código.

- **Ventajas:** interpretable, barata y fiel a la definición del reto. Distingue toque de control.
- **Inconvenientes:** si se aplica de forma causal, **mete un retraso de k frames**. Hay que **retrofechar** el
  cambio al inicio de la evidencia. Tiene varios umbrales que interactúan y que hay que fijar por tipo de
  transición (`H↔A`, vivo→`D`, `D`→vivo).
- **Parámetros:** θ_on, θ_off, k y la regla de retrofechado.

### 4.5 HMM con Viterbi y coste de cambio, HSMM y CRF

Se modelan tres estados ocultos, {`H`, `A`, `D`}. Cada frame aporta una puntuación por estado (la *emisión*: el
log de la probabilidad de lo observado en ese estado). Cada cambio de estado tiene un coste (la *transición*).
Viterbi encuentra **la secuencia globalmente óptima**:

```
minimizar  Σ_t −log p(observación_t | estado_t)  +  λ · (número de cambios)
```

Es una segmentación penalizada, la misma idea que la detección de puntos de cambio con penalización
([PELT, Killick et al. 2012](https://arxiv.org/abs/1101.1438)). Referencia clásica de HMM y Viterbi:
[Rabiner 1989](https://ieeexplore.ieee.org/document/18626).

- **Ventajas:**
  - Un solo mando principal (λ) para el dilema parpadeo frente a posesión corta.
  - Las fronteras caen donde cambia la evidencia, sin retraso sistemático.
  - **Los frames sin balón se tratan con naturalidad**: emisión neutra (o la de un modelo sin balón), y el estado
    se mantiene salvo que el contexto pida cambiar.
  - Admite costes asimétricos: `H→A` frente a `H→D` frente a `D→H`.
  - Admite transiciones prohibidas, como en PathCRF, que enmascara las transiciones imposibles con una puntuación
    muy negativa.
- **Inconvenientes:**
  - Necesita emisiones razonablemente calibradas.
  - Un HMM implica duraciones geométricas, que no son las del fútbol.
  - λ hay que elegirlo con datos que no sean la ventana pública (sección 6).
- **HSMM** (*hidden semi-Markov model*, con duración explícita, [Yu 2010](https://doi.org/10.1016/j.artint.2009.11.011)):
  - Modela la distribución de duración de cada estado. Por ejemplo, `D` con mínimo de un par de segundos.
  - Más caro: O(T·D_max) con 160 000 frames. Se puede reducir trabajando a 5 fps (lo hace PathCRF) y refinando
    después las fronteras a 25 fps.
  - Un mínimo de k frames también se consigue en un HMM normal encadenando k subestados.
- **CRF** ([PathCRF](https://arxiv.org/abs/2602.12080)): las emisiones y las transiciones se aprenden con datos
  etiquetados, y se decodifica igual, con Viterbi.

### 4.6 Refinamiento de fronteras

Primero se segmenta. Después, cada frontera se mueve dentro de ±Δ frames hasta el frame con más evidencia de toque
(cambio de dirección del balón junto a un jugador del nuevo equipo) o de parada y reinicio. Es lo que hace
[ASRF](https://arxiv.org/abs/2007.06866) en segmentación de acciones: una rama predice las fronteras y corrige la
segmentación. Encaja aquí porque `spellF1` castiga los desplazamientos de más de ~3 frames, sobre todo en
posesiones cortas. En la simulación, un ruido de σ = 5 frames en las fronteras cuesta entre 0 y 7 puntos, y σ = 12
cuesta entre 2 y 23, según cuántas posesiones cortas haya.

### 4.7 Comparativa

| técnica | parpadeo | posesiones cortas reales | fronteras | balón ausente | parámetros |
|---|---|---|---|---|---|
| ventana de voto | bien si w es grande | las borra si w es grande | se desplazan | lo confunde con `D` | w |
| mediana / morfología | bien | las borra (< k) | estables | — | k por clase |
| duración mínima | bien | las borra (< k) | estables | — | k por clase |
| histéresis | bien | las conserva si hay evidencia fuerte | retraso salvo retrofechado | mantiene el estado | θ_on, θ_off, k |
| HMM/Viterbi + λ | bien | según λ y la evidencia | donde cambia la evidencia | emisión neutra | λ (+ asimetrías) |
| HSMM / CRF | bien | modela duraciones | donde cambia la evidencia | sí | duraciones / aprendidos |
| + refinamiento de fronteras | — | — | **mejora** | — | Δ |

**Recomendación:** HMM/Viterbi como columna vertebral, con emisiones construidas a partir de los eventos de
control (3.2), un modelo de `D` (3.4) y emisión neutra sin balón. La ventana de voto y la histéresis quedan como
comparación, y al final se añade el refinamiento de fronteras.

---

## 5. Estado del arte

### 5.1 Posesión y eventos a partir de tracking

| trabajo | entrada | qué hace | por qué nos importa | qué hemos verificado |
|---|---|---|---|---|
| [Link y Hoernig 2017](https://pmc.ncbi.nlm.nih.gov/articles/PMC5503225/), *PLoS ONE* | TRACAB 25 Hz, con el indicador de balón en juego del propio dato | Posesión individual: empieza cuando el balón entra en el espacio de acción del jugador; detección de golpeo por un pico de aceleración del balón ≥ 4 m/s²; fin por predicción del balón a 1 s. Una red bayesiana distingue control de mero contacto. F = 0,83 en posesión individual (tolerancia de 0,6 s) | Reglas de contacto y control; la idea de que control ≠ estar cerca | texto completo (PMC) |
| [Vidal-Codina et al. 2022](https://arxiv.org/abs/2202.00804), *Sports Engineering* | tracking 25 Hz de tres proveedores | Árbol de decisión determinista: zona de posesión de 0,5 o 1 m, zona de duelo de 1 m, ganancia si cambia la dirección o la velocidad del balón, pérdida si el balón sale de su zona y el jugador no participa en el siguiente frame de control. Balón muerto por indicador o por ausencia de balón. Reinicios por patrones de posición. +90 % de detección en la mayoría de eventos | La referencia de reglas más completa; databallpy la implementa | texto de arXiv (los umbrales angulares y de velocidad están en material suplementario no leído) |
| [Khaustov y Mozgovoy 2020](https://doi.org/10.3390/app10228046), *Applied Sciences* | tracking | Reglas para posesión, pases y tiros, planteadas como línea base práctica | Otra línea base de reglas | solo el resumen |
| [Richly et al. 2016](https://scitepress.org/Papers/2016/58776), IoTBD | posiciones | SVM, k-NN y random forest sobre rasgos posicionales para eventos compuestos | ML clásico sobre rasgos hechos a mano | solo el resumen |
| [Morra et al. 2020](https://arxiv.org/abs/2004.04147), ICIAR | tracking sintético (SoccER) | Eventos atómicos más lógica temporal de intervalos para eventos complejos | Formalizar reglas temporales ("toque y luego control") | solo el resumen |
| [Borghesi et al. 2023](https://doi.org/10.1016/j.eswa.2023.119780), *Expert Systems with Applications* | tracking profesional | **TCN que clasifica cada momento como balón muerto, posesión local o posesión visitante**, con agregación invariante a permutaciones de los jugadores. 86,2 % de acierto en posesión y 89,2 % en vivo/muerto (+7,3 % y +33,2 % frente al estado del arte anterior, según el resumen) | **Es casi exactamente nuestra tarea**. Sugiere separar vivo/muerto de local/visitante | solo el resumen (el PDF no se pudo descargar). Ventana temporal, entradas y tratamiento del balón ausente: **sin verificar** |
| [Kim et al. 2023](https://arxiv.org/abs/2306.08206), KDD (Ball Radar) | **solo jugadores** | Set Transformer y Bi-LSTM jerárquico: primero predice el poseedor y después la trayectoria del balón. El resumen da un 64,7 % de acierto en poseedor individual | Inferir dónde está el balón cuando falta. [Código](https://github.com/pientist/ballradar) | resumen |
| [Kim et al. 2026](https://arxiv.org/abs/2602.12080), KDD (PathCRF) | **solo jugadores** (Sportec Open DFL) | Modela la posesión como una arista jugador→jugador (con autolazos para "la tiene" y nodos "fuera"). Usa un **CRF con transiciones imposibles enmascaradas** y **decodificación Viterbi**. Event F1 de 75,7 %; un 92,4 % de acierto por frame en posesión de equipo | Decodificación estructurada sin balón; transiciones prohibidas | parte del texto. La cifra de 92,4 % viene de un resumen y hay que comprobarla en el artículo. Su resumen enlaza [código](https://github.com/hyunsungkim-ds/pathcrf.git) (no abierto) |
| [Wei et al. 2015](https://openaccess.thecvf.com/content_iccv_2015_workshops/w21/html/Wei_Predicting_Ball_Ownership_ICCV_2015_paper.html), ICCV-W (baloncesto) | trayectorias de jugadores | Predice quién tiene el balón solo con la disposición de los jugadores, ordenados por rol | El contexto colectivo delata al poseedor | resumen |
| [Wang et al. 2014](https://infoscience.epfl.ch/record/185107), *CVIU* | vídeo | El seguimiento del balón se plantea como "quién lo tiene" | La posesión como estado latente | resumen |
| [Maksai et al. 2016](https://openaccess.thecvf.com/content_cvpr_2016/html/Maksai_What_Players_Do_CVPR_2016_paper.html), CVPR | vídeo | Seguimiento del balón con interacciones jugador–balón y restricciones físicas (programación entera mixta) | Física del balón para rellenar huecos | resumen |

### 5.2 Segmentación temporal (el mismo problema, en otro campo)

- [Lea et al. 2017](https://arxiv.org/abs/1611.05267): proponen el **F1 segmental** con umbral de IoU, que penaliza
  la sobresegmentación y es insensible a pequeños desplazamientos. Es el antecedente directo de `spellF1`.
- [Farha y Gall 2019 (MS-TCN)](https://arxiv.org/abs/1903.01945): para frenar la sobresegmentación añaden una
  **pérdida de suavizado** (MSE truncado entre log-probabilidades de frames consecutivos) y refinan por etapas. Es
  aplicable si entrenamos un modelo.
- [Ishikawa et al. 2021 (ASRF)](https://arxiv.org/abs/2007.06866): una rama de fronteras que corrige la
  segmentación; su resumen da mejoras de hasta un 16,1 % en F1 segmental. Inspira 4.6.
- HMM y Viterbi ([Rabiner 1989](https://ieeexplore.ieee.org/document/18626)); HSMM
  ([Yu 2010](https://doi.org/10.1016/j.artint.2009.11.011)); puntos de cambio penalizados
  ([PELT](https://arxiv.org/abs/1101.1438)).

### 5.3 Vídeo (por si usamos el vídeo táctico)

- [SoccerNet 2023](https://arxiv.org/abs/2309.06006) incluye *ball action spotting*: localizar en el tiempo pases y
  conducciones en vídeo de televisión. Sirve como referencia si algún día detectamos toques en el vídeo para
  afinar fronteras. No es prioritario: `CHALLENGE.md` deja claro que el reto no va de rehacer la visión.

### 5.4 Datos abiertos y herramientas útiles

| recurso | qué aporta | cautela |
|---|---|---|
| **Sportec Open DFL** ([Bassek et al. 2025](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/); datos en [figshare](https://doi.org/10.6084/m9.figshare.28196177)) | 7 partidos de la Bundesliga 1 y 2 con posiciones, eventos y, para el balón, `BallPossession` (1/2) y `BallStatus` (0/1). **Misma semántica que nuestra GT.** CC-BY 4.0. Se carga con kloppy o floodlight | Tracking de alta calidad (hay que degradarlo para parecerse al nuestro). Su definición de "dueño" puede diferir de la de Metrica. No hemos verificado la frecuencia de los ficheros (las cámaras van a 25 Hz) |
| [kloppy](https://github.com/PySport/kloppy) | Lee nuestro EPTS y el formato DFL, con `ball_owning_team` y `ball_state` | — |
| [databallpy](https://databallpy.readthedocs.io/en/latest/features/team_and_player_possession.html) | Posesión individual según Vidal-Codina, con parámetros por defecto `pz_radius=1.5`, `bv_threshold=5.`, `ba_threshold=10.` y `min_frames_pz=0`. También posesión de equipo a partir de eventos | La documentación tiene incoherencias (un ejemplo usa 1,5 en vez de 5 para `bv_threshold`) |
| [SkillCorner opendata](https://github.com/SkillCorner/opendata) | Tracking de **televisión** a 10 fps con posesión por frame (jugador y grupo): ruido más parecido al nuestro | Otra frecuencia y otra definición de posesión. El formato exacto no está verificado |
| [Metrica sample-data](https://github.com/metrica-sports/sample-data) | Sample Game 3 en **el mismo formato EPTS** que nuestro ATD, con eventos JSON | Partido anonimizado. La posesión habría que derivarla de los eventos |

`RULES.md` permite usar datos externos si los organizadores pueden acceder a ellos y el documento técnico lo
explica. Los tres datasets son públicos.

---

## 6. Propuesta

### 6.1 Qué probar y en qué orden

Ordenado por ganancia esperada y coste. Cada paso se mide contra el anterior, no contra el baseline original.

| # | mejora | por qué primero | parámetros a validar |
|---|---|---|---|
| **P0** | **Instrumentación:** script local que genera, valida y puntúa, e imprime el diagnóstico de 2.6 y un histograma de duraciones; bootstrap; plantilla de registro (6.3). Banco de validación externo con DFL degradado (6.2) | Sin esto, todo lo demás se decide con 17 posesiones | — |
| **P1** | **Separar "no veo" de "muerto":** sin balón no se escribe `D`; se mantiene la etiqueta | Elimina la mayor fuente de cortes falsos (≈ 1,1/N cada uno). Cambio de pocas líneas | — |
| **P2** | **Detector de `D`** (3.4): balón fuera, quietud colectiva, reinicios, Smart Tagging `SET PIECES`, saque inicial | Tras P1, las paradas reales hay que detectarlas con evidencia. Sus bordes son bordes de posesión | margen fuera de campo; velocidad media y duración de quietud; mínimo de `D` |
| **P3** | **Eventos de control + mantener el último equipo** (3.2), en lugar del más cercano en cada frame | Es la definición del reto; quita los parpadeos de pases y duelos en su origen | R (0,5–1,5 m); umbrales de ángulo y velocidad del balón; k de confirmación; R_duelo |
| **P4** | **HMM/Viterbi** con {`H`, `A`, `D`}, coste de cambio λ y emisiones de P2 y P3 (neutra sin balón). Comparar con ventana e histéresis | Optimiza la secuencia completa, con un mando claro para el dilema parpadeo frente a posesión corta | λ (barrido buscando una meseta); asimetrías |
| **P5** | **Refinamiento de fronteras** al frame del toque, la salida o el reinicio | Los retrasos de más de 3 frames cuestan mucho con posesiones cortas | Δ de búsqueda |
| **P6** | **Huecos de balón:** interpolación corta; para huecos largos, rasgos colectivos (presión, dirección de los bloques) o un modelo sin balón | 41 % de frames sin balón, y los cambios dentro de los huecos se fechan mal | longitud máxima de interpolación |
| **P7** | **Smart Tagging** como prior suave de equipo (fases) y de cambio (transiciones) | Información gratis, pero ruidosa | peso del prior |
| **P8** | **Modelo aprendido** (gradient boosting por frame, o TCN al estilo Borghesi) entrenado con DFL degradado, decodificado con P4 | Solo si P1–P6 se estancan; necesita P0 bien montado | — |

### 6.2 Cómo validar sin sobreajustar la ventana pública

La ventana pública tiene 17 posesiones, y una posesión mal resuelta mueve ~6 puntos. El propio reto demuestra que
elegir con ella lleva a la opción equivocada (`EVALUATION.md`, `FAQ.md`). Protocolo propuesto:

1. **La ventana pública sirve para comprobar que el pipeline es correcto** (frames alineados, formato, que `H` sea
   Barcelona), **no para elegir** entre versiones. Se miran sus intervalos de bootstrap, no la cifra suelta.
2. **Elegir parámetros en datos externos etiquetados:** los 7 partidos de Sportec/DFL, con validación dejando un
   partido fuera cada vez. Antes se **degradan para que se parezcan a los nuestros**:
   - quitar el balón en ~41 % de los frames, en ráfagas cuya distribución de longitudes y zonas se mide en
     nuestro ATD (sin GT, [L1](#7-experimentos-locales-para-el-equipo));
   - quitar identidades y quedarse solo con equipo y posición;
   - fragmentar los tracks y añadir ruido de posición.
3. **Regla de la meseta:** se barre cada parámetro y se elige el centro de una zona plana, no el pico. Un método que
   solo funciona en un valor exacto está sobreajustado.
4. **Comprobaciones sin etiquetas en el partido completo:**
   - número de posesiones;
   - histograma de duraciones;
   - fracción de `D` (~20 % en la ventana pública);
   - fracción de posesiones de menos de 1 s;
   - reparto local/visitante;
   - coherencia entre las dos mitades.

   No se ajusta para clavarlas: sirven para detectar algo raro.
5. **Pocos parámetros, con valores con sentido físico** (radios en metros, tiempos en décimas de segundo) y
   documentados.
6. **Cada experimento se registra antes de ver el resultado** (hipótesis y efecto esperado), incluidos los
   fallidos. Esto encaja con el log del equipo.
7. **Congelar:** la configuración final se elige con DFL y con criterios a priori. La ventana pública se mira una
   última vez para descartar una regresión grave.

### 6.3 Qué registrar en cada experimento

| campo | ejemplo |
|---|---|
| id, fecha, autor, commit | `E07 · 2026-10-24 · Nico · a1b2c3d` |
| hipótesis y efecto esperado | "sin balón ≠ `D` reduce posesiones predichas y sube `spellF1`" |
| cambio y parámetros | `R=1.0 m, k=5, λ=8` |
| ventana pública | `spellF1` (intervalo de bootstrap 5–95 %), `macroF1`, `alive_dead_f1`, `team_acc_both_alive`, `n_pred_spells` frente a 17, duración media, P/R de transiciones a ±12 y ±25 |
| DFL degradado (dejando un partido fuera) | `spellF1` medio ± desviación |
| partido completo, sin etiquetas | n.º de posesiones, % de `D`, % de posesiones < 1 s |
| decisión | se adopta / se descarta / dudoso, y por qué |

Al log público solo van métricas agregadas y conclusiones, nunca datos del partido (`docs/README.md`).

---

## 7. Experimentos locales para el equipo

Estos experimentos **requieren mirar los datos del partido o la GT pública**, así que los ejecuta el equipo en
local, sin pasar datos ni extractos a ningún LLM en la nube. Los resultados agregados se pueden anotar en este
documento o en el log.

| id | pregunta | cómo | para qué |
|---|---|---|---|
| **L0** | ¿Qué canales trae el ATD? (¿altura del balón, velocidad, algún estado o dueño del balón?) | Leer la `DataFormatSpecification` del XML de metadatos | Saber con qué señales contamos |
| **L1** | ¿Cómo son los huecos de balón? | Histograma de longitudes de hueco en los frames puntuados; zona del campo donde empiezan | Decidir la interpolación (P6) y degradar DFL de forma realista (6.2) |
| **L2** | ¿Cuántas posesiones cortas tiene la GT pública? | Histograma de duraciones de las 17 posesiones; contar las de menos de 1 s y menos de 2 s | Confirmar o refutar la sección 2.5 |
| **L3** | ¿Cuánto cuesta la duración mínima, como techo? | Aplicar duraciones mínimas de 0,2 / 0,5 / 1 / 2 s **a la propia GT pública** y puntuar | Coste máximo del filtro (4.3) |
| **L4** | ¿La ausencia de balón indica `D`? | % de frames sin balón dentro de `D` y dentro de juego vivo, en la ventana pública | Decidir si la ausencia larga es evidencia de parada (3.3) |
| **L5** | ¿Qué es cada posesión corta y cada cambio de la GT? | Ver en el vídeo los cambios de la ventana pública (el `_transitions.csv` del scorer da los frames) | Fijar qué cuenta como control en la práctica (1.2) |
| **L6** | ¿A qué distancia acierta el "más cercano"? | Con balón visible y GT viva: acierto de equipo por tramos de distancia jugador–balón | Calibrar R (P3) |
| **L7** | ¿Cuánto da P1 por sí solo? | `smooth()` sin escribir `D` cuando falta el balón; puntuar con bootstrap y en DFL | Primer experimento del registro |

En L2, L3 y L5 hay que recordar que la ventana pública tiene 17 posesiones. Sirven para **entender** el problema, no
para fijar umbrales; los umbrales se fijan en DFL (6.2).

---

## 8. Fuentes

**Documentación del reto** (este repositorio): `CHALLENGE.md`, `EVALUATION.md`, `DATA.md`, `FAQ.md`,
`RULES.md`, `OVERVIEW.md`, `evaluation/possession_metrics.py`, `evaluation/run_evaluation.py`,
`starter/baseline.py` y `starter/0[1-3]_*.ipynb`.

**Literatura y recursos** (enlaces comprobados el 20/10/2026; entre paréntesis, qué hemos leído):

1. Link, D. y Hoernig, M. (2017). *Individual ball possession in soccer.* PLoS ONE 12(7): e0179953.
   [doi:10.1371/journal.pone.0179953](https://doi.org/10.1371/journal.pone.0179953) (texto completo).
2. Vidal-Codina, F., Evans, N., El Fakir, B. y Billingham, J. (2022). *Automatic event detection in football using
   tracking data.* Sports Engineering. [arXiv:2202.00804](https://arxiv.org/abs/2202.00804) (texto de arXiv sin el
   material suplementario).
3. Khaustov y Mozgovoy (2020). *Recognizing events in spatiotemporal soccer data.* Applied Sciences 10(22):
   8046. [doi:10.3390/app10228046](https://doi.org/10.3390/app10228046) (resumen).
4. Richly, K., Bothe, M., Rohloff, T. y Schwarz, C. (2016). *Recognizing compound events in spatio-temporal
   football data.* IoTBD 2016. [SciTePress](https://scitepress.org/Papers/2016/58776) (resumen).
5. Morra, L. et al. (2020). *Slicing and dicing soccer: automatic detection of complex events from spatio-temporal
   data.* ICIAR 2020. [arXiv:2004.04147](https://arxiv.org/abs/2004.04147) (resumen).
6. Borghesi, Costa, Morra y Lamberti (2023). *Using temporal convolutional networks to estimate
   ball possession in soccer games.* Expert Systems with Applications 223: 119780.
   [doi:10.1016/j.eswa.2023.119780](https://doi.org/10.1016/j.eswa.2023.119780) (resumen; el detalle del método
   está sin verificar).
7. Kim, H., Choi, H.-J., Kim, C. J., Yoon, J. y Ko, S.-K. (2023). *Ball trajectory inference from multi-agent sports
   contexts using Set Transformer and hierarchical Bi-LSTM.* KDD 2023.
   [arXiv:2306.08206](https://arxiv.org/abs/2306.08206) (resumen).
8. Kim, H., Lee, K., Seo, S., Ko, S.-K., Yoon, J. y Park, C. (2026). *PathCRF: Ball-free soccer event detection via
   possession path inference from player trajectories.* KDD 2026. [arXiv:2602.12080](https://arxiv.org/abs/2602.12080)
   (introducción y método; parte de las tablas solo a través de un resumen).
9. Wei, X., Sha, L., Lucey, P., Carr, P., Sridharan, S. y Matthews, I. (2015). *Predicting ball ownership in
   basketball from a monocular view using only player trajectories.* ICCV Workshops.
   [CVF](https://openaccess.thecvf.com/content_iccv_2015_workshops/w21/html/Wei_Predicting_Ball_Ownership_ICCV_2015_paper.html)
   (resumen).
10. Wang, X., Ablavsky, V., Ben Shitrit, H. y Fua, P. (2014). *Take your eyes off the ball: improving ball-tracking
    by focusing on team play.* CVIU 119: 102–115. [EPFL](https://infoscience.epfl.ch/record/185107) (resumen).
11. Maksai, A., Wang, X. y Fua, P. (2016). *What players do with the ball: a physically constrained interaction
    modeling.* CVPR 2016.
    [CVF](https://openaccess.thecvf.com/content_cvpr_2016/html/Maksai_What_Players_Do_CVPR_2016_paper.html)
    (resumen).
12. Lea, C., Flynn, M. D., Vidal, R., Reiter, A. y Hager, G. D. (2017). *Temporal convolutional networks for action
    segmentation and detection.* CVPR 2017. [arXiv:1611.05267](https://arxiv.org/abs/1611.05267) (definición de
    F1@k).
13. Abu Farha, Y. y Gall, J. (2019). *MS-TCN: multi-stage temporal convolutional network for action segmentation.*
    CVPR 2019. [arXiv:1903.01945](https://arxiv.org/abs/1903.01945) (resumen).
14. Ishikawa, Y., Kasai, S., Aoki, Y. y Kataoka, H. (2021). *Alleviating over-segmentation errors by detecting
    action boundaries.* WACV 2021. [arXiv:2007.06866](https://arxiv.org/abs/2007.06866) (resumen).
15. Rabiner, L. R. (1989). *A tutorial on hidden Markov models and selected applications in speech recognition.*
    Proc. IEEE 77(2): 257–286. [IEEE Xplore](https://ieeexplore.ieee.org/document/18626).
16. Yu, S.-Z. (2010). *Hidden semi-Markov models.* Artificial Intelligence 174(2): 215–243.
    [doi:10.1016/j.artint.2009.11.011](https://doi.org/10.1016/j.artint.2009.11.011) (resumen).
17. Killick, R., Fearnhead, P. y Eckley, I. A. (2012). *Optimal detection of changepoints with a linear
    computational cost.* JASA 107(500): 1590–1598. [arXiv:1101.1438](https://arxiv.org/abs/1101.1438).
18. Cioppa, A., Giancola, S. et al. (2023). *SoccerNet 2023 challenges results.*
    [arXiv:2309.06006](https://arxiv.org/abs/2309.06006) (resumen).
19. Bassek, M., Rein, R., Weber, H. y Memmert, D. (2025). *An integrated dataset of spatiotemporal and event data in
    elite soccer.* Scientific Data 12: 195.
    [PMC](https://pmc.ncbi.nlm.nih.gov/articles/PMC11787359/) · datos en
    [figshare](https://doi.org/10.6084/m9.figshare.28196177) (sección de métodos: `BallPossession` y `BallStatus`).
20. kloppy, deserializador Sportec:
    [código](https://github.com/PySport/kloppy/blob/master/kloppy/infra/serializers/tracking/sportec/deserializer.py)
    (`BallPossession` → `ball_owning_team`, `BallStatus` → `ball_state`).
21. databallpy, *Team and player possession*:
    [documentación](https://databallpy.readthedocs.io/en/latest/features/team_and_player_possession.html).
22. SkillCorner opendata: [GitHub](https://github.com/SkillCorner/opendata) ·
    Metrica sample-data: [GitHub](https://github.com/metrica-sports/sample-data).

**Sin verificar** (no se usa para ninguna conclusión): los detalles internos de Borghesi et al. 2023 (ventana
temporal, entradas, tratamiento del balón ausente); los umbrales del material suplementario de Vidal-Codina et al.;
el formato exacto de SkillCorner; la frecuencia de los ficheros DFL; y el contenido de los repositorios de PathCRF y
Ball Radar.

---

## Apéndice: simulación sintética del scorer

Para cuantificar el coste de cada error sin tocar datos del partido, se generaron mitades **sintéticas** de 200
posesiones: duración lognormal con media de ~12–14 s, un 30 % de paradas `D` de 5–40 s y, opcionalmente, una
fracción `p_short` de posesiones "relámpago" de 0,3–2 s. Después se puntuaron predicciones perfectas a las que se
añadía un único tipo de error, con `possession_metrics.evaluate`. **Las distribuciones son supuestos**: los números
sirven para comparar tipos de error entre sí, no para predecir nuestra puntuación.

Resultados (`spellF1`):

| prueba | `p_short = 0` | `p_short = 0,2` | `p_short = 0,4` | GT real (`EVALUATION.md`) |
|---|---|---|---|---|
| retraso uniforme 3 / 8 / 25 frames | 0,999 / 0,983 / 0,864 | 0,987 / 0,921 / 0,741 | 0,966 / 0,784 / 0,533 | 0,982 / 0,893 / 0,654 |
| 10 / 50 / 100 parpadeos de 1 frame (otro equipo) | 0,926 / 0,695 / 0,499 | 0,928 / 0,702 / 0,497 | 0,926 / 0,699 / 0,501 | — |
| 10 / 50 / 100 huecos `D` de 1 frame | 0,951 / 0,772 / 0,598 | 0,951 / 0,777 / 0,593 | 0,952 / 0,777 / 0,598 | — |
| ruido en fronteras σ = 5 / 12 / 25 frames | 0,999 / 0,975 / 0,890 | 0,978 / 0,886 / 0,792 | 0,927 / 0,773 / 0,670 | — |
| duración mínima 1 / 2 / 3 / 5 s sobre una predicción perfecta | 0,997 / 0,961 / 0,915 / 0,764 | 0,958 / 0,856 / 0,805 / 0,714 | 0,854 / 0,658 / 0,640 / 0,578 | — |
| `X` durante 5 / 25 / 50 frames tras cada cambio | 0,997 / 0,865 / 0,661 | 0,961 / 0,766 / 0,588 | 0,897 / 0,588 / 0,482 | — |

Los costes por error de la sección 2.3 salen de casos deterministas: 100 posesiones de 10 s y un único error
colocado a mano.

<details>
<summary>Script (Python, numpy; se ejecuta con <code>python sim_spellf1.py evaluation</code>)</summary>

```python
"""Coste de cada tipo de error en spellF1, sobre secuencias SINTETICAS (sin datos del partido).

Uso: python sim_spellf1.py <ruta a evaluation/>
"""
import sys

import numpy as np

sys.path.insert(0, sys.argv[1])
import possession_metrics as pm  # noqa: E402

H, A, D, X = pm.H, pm.A, pm.D, pm.X
FPS = 25
rng = np.random.RandomState(0)


def synthetic_half(n_poss=200, mean_s=14.2, p_stop=0.3, stop_s=(5, 40), p_short=0.0):
    """Una mitad sintetica: posesiones con duracion lognormal (media ~mean_s) y paradas D.

    p_short es la fraccion de posesiones "relampago" de 0.3-2 s (toques, rebotes con dueno).
    """
    seq, team = [], H
    sigma = 0.9
    mu = np.log(mean_s * FPS) - sigma ** 2 / 2
    for _ in range(n_poss):
        if rng.rand() < p_short:
            length = int(rng.uniform(0.3, 2.0) * FPS)
        else:
            length = max(int(rng.lognormal(mu, sigma)), 13)
        seq += [team] * length
        if rng.rand() < p_stop:
            seq += [D] * int(rng.uniform(*stop_s) * FPS)
            team = H if rng.rand() < 0.5 else A
        else:
            team = A if team == H else H
    return np.array([X] * 50 + seq + [X] * 50, dtype=np.int8)


def score(gt, pred):
    r = pm.evaluate(gt, pred)
    return r["spell_f1_mean"], r["n_gt_spells"], r["n_pred_spells"]


def spells(codes):
    return pm.possession_spells(codes, pm.valid_runs(codes))


def blip(gt, n, width, kind):
    """n parpadeos de `width` frames en mitad de posesiones distintas: equipo contrario o D."""
    pred = gt.copy()
    chosen = rng.choice(len(spells(gt)), n, replace=False)
    for index in chosen:
        a, b, k = spells(gt)[index]
        mid = (a + b) // 2
        pred[mid:mid + width] = (A if k == H else H) if kind == "team" else D
    return pred


def jitter(gt, sigma):
    """Mueve cada frontera de etiqueta un desplazamiento gaussiano de sigma frames."""
    pred = gt.copy()
    for frame, old, new in pm.transitions(gt, pm.valid_runs(gt)):
        shift = int(round(rng.normal(0, sigma)))
        if shift > 0:
            pred[frame:frame + shift] = old
        elif shift < 0:
            pred[frame + shift:frame] = new
    return pred


def min_duration(codes, min_frames):
    """Fusiona las posesiones mas cortas que min_frames con la etiqueta anterior (rellenado)."""
    out = codes.copy()
    for a, b, k in spells(codes):
        if b - a < min_frames and a > 0 and out[a - 1] in (H, A, D):
            out[a:b] = out[a - 1]
    return out


def lag(gt, frames):
    """Prediccion perfecta desplazada `frames` frames: cada frame toma la etiqueta de `frames` antes."""
    pred = gt.copy()
    pred[frames:] = gt[:-frames]
    return pred


def report(gt):
    base, n_gt, _ = score(gt, gt)
    lengths = np.array([b - a for a, b, _ in spells(gt)]) / FPS
    print("GT sintetica: {} posesiones, media {:.1f} s, mediana {:.1f} s, <3 s: {:.0%}".format(
        n_gt, lengths.mean(), np.median(lengths), np.mean(lengths < 3)))

    print("\n0) Retraso uniforme (EVALUATION.md, GT real: 1->1.000 3->0.982 8->0.893 25->0.654)")
    print("  " + "  ".join("{}:{:.3f}".format(f, score(gt, lag(gt, f))[0]) for f in (1, 3, 8, 25)))

    print("\n1) Parpadeos en mitad de una posesion (n = numero de posesiones afectadas)")
    for kind in ("team", "dead"):
        for width in (1, 25):
            row = []
            for n in (1, 10, 50, 100):
                row.append("{}:{:.3f}".format(n, score(gt, blip(gt, n, width, kind))[0]))
            print("  {:<5} {:>2} frames  ".format(kind, width) + "  ".join(row))

    print("\n2) Ruido en las fronteras (sigma en frames)")
    print("  " + "  ".join("{}:{:.3f}".format(s, score(gt, jitter(gt, s))[0])
                           for s in (2, 5, 12, 25, 50)))

    print("\n3) Filtro de duracion minima aplicado a una prediccion PERFECTA")
    print("  " + "  ".join("{}s:{:.3f}".format(s, score(gt, min_duration(gt, s * FPS))[0])
                           for s in (1, 2, 3, 5, 8)))

    print("\n4) X a traves de un cambio de posesion (la X se rellena con la etiqueta previa)")
    for gap in (5, 25, 50):
        pred = gt.copy()
        for frame, old, new in pm.transitions(gt, pm.valid_runs(gt)):
            pred[frame:frame + gap] = X
        print("  X en los {} frames tras cada cambio: {:.3f}".format(gap, score(gt, pred)[0]))


if __name__ == "__main__":
    for p_short in (0.0, 0.2, 0.4):
        rng.seed(0)
        print("=" * 30, "p_short =", p_short)
        report(synthetic_half(p_short=p_short))
```

</details>
