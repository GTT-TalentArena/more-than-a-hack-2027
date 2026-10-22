# Prompts · candidato A

Un apartado por prompt, en orden. Se copia el texto tal cual y se resume la respuesta: qué decidió el modelo y qué
ficheros cambió, con el commit.

## 001 · 2026-10-21 ~18:00 · brief común

Texto: [`../BRIEF.md`](../BRIEF.md), sin cambios.

Respuesta (resumen). El modelo leyó la documentación, el código de `starter/` y `evaluation/` y el estudio, sin
abrir ningún dato del partido ni la GT pública. Construyó `solution/a_opus/` (versión 1.0.0):

- **Método.** Evidencia por frame y decodificación exacta H/A/D (Viterbi con coste de cambio λ = 5 nats y paradas
  de al menos 2 s).
  - Equipo: zona de control con compuerta de velocidad relativa; sin balón la evidencia es cero, no `D`.
  - Desempates: el cambio de equipo, lo más tarde posible; la parada, lo antes posible.
  - Balón muerto: fuera de campo, salida, balón quieto, golpeo, velocidad colectiva, formación de saque inicial y
    `SET PIECES` del Smart Tagging.
  - Autocalibración sin etiquetas: radio de control, umbral de balón quieto, mezcla de velocidades, polaridad de
    los códigos del Smart Tagging y un modelo de equipo sin balón con validación cruzada por mitades.
- **Pruebas.** Generador sintético en los formatos reales (`synth.py`) y tests (`tests.py`): el decodificador
  coincide con la fuerza bruta.
- **Resultado sintético** (3 partidos): spellF1 0,69–0,77 frente a 0,31–0,33 del baseline con los mismos datos.
  Tarda ~10 s y es determinista.
- **Ficheros:** `solution/a_opus/*`. Commit: _pendiente_.

## 002 · 2026-10-21 · no funciona en el terminal

Texto: "no me funciona en terminal. revisa las salidas y las ejecuciones fallidas en el terminal porfa."

Respuesta (resumen). El modelo leyó el panel del terminal: solo había dos órdenes fallidas, sin datos del
partido.
- `python -m .\solution\a_opus\` falló porque `-m` recibe un nombre de módulo, no una ruta.
- `python -m solution.a_opus` falló porque el `python` global (`C:\Python311`) no tiene numpy ni pip. El venv del
  repo principal sí tiene las versiones fijadas.

Cambios:
- `__main__.py` avisa en un mensaje claro si falta numpy.
- `main()` dice dónde ha buscado los datos si no los encuentra (código 2).
- El README tiene una receta para Windows.

Comandos dados: los del venv con `MTAH_DATA_DIR`. Commit: _pendiente_.

## 003 · 2026-10-21 · log de la primera ejecución real

Texto: el log agregado de la ejecución 1 (ver `ejecuciones.md`) y la salida de `validate_submission.py`, pegados
tal cual.

Respuesta (resumen). El modelo diagnosticó el log:
- **Confirmado:** la lectura, los equipos (el Smart Tagging cuadra con DATA.md), la orientación (H = Barça al
  65 %) y el modelo sin balón (83 % con datos no vistos).
- **Nuevo:** el balón del ATD está suavizado y sin huecos cortos, su tercer canal es la velocidad, y las fases del
  Smart Tagging van por parejas.
- **Fallos de código:** el golpeo tras balón quieto nunca se detectaba, y las ventanas `SET PIECES` largas
  alargaban la parada dentro del juego.
- **Síntoma principal:** solo 48 cambios H↔A directos. El 54,7 % de `D` es plausible: tres indicios públicos
  sitúan `D` en ~45–54 % del partido completo.

v1.1:
- Corregidos los dos fallos.
- Fases emparejadas contadas una vez.
- La velocidad ya no vota `D` con el balón en juego.
- λ_HA de 5 a 4.
- Comprobaciones sin etiquetas en el log (`diagnostics.py`).

Sintético v1.1: 0,723 / 0,781 / 0,753. Commit: _pendiente_.

## 004 · 2026-10-21 · qué hace falta para la siguiente mejora

Texto: "dime exactamente qué necesitas. vamos a ponernos con otra mejora en cuanto sepa lo que necesitas"

Respuesta (resumen). El modelo pidió dos cosas, ya calculadas en las ejecuciones 2 y 3 y sin gastar otra
evaluación pública:
- las líneas `[a_opus]` del log de la v1.1, sobre todo las comprobaciones sin etiquetas;
- el bloque de detalle agregado de `gtt_comet_v1_1` en la ventana pública (o
  `evaluation/reports/gtt_comet_v1_1.json`).

Quedó explícito qué no se pasa: los CSV de transiciones (llevan frames), la submission y los datos. El detalle
público solo sirve para entender el tipo de error, no para elegir parámetros. Sin cambios de código.

## 005 · 2026-10-21 · reejecutar con el log en un fichero

Texto: "la terminal se eliminó. dame y ejecuto de nuevo. te paso todo el output o ponte el output que necesites
directamente en una ruta accesible por ti. no hacemos mejoras aún. primero dame eso y le damos caña, que edu ya ha
gastado sus 5 evaluaciones"

Respuesta (resumen):
- Se añade `--log <ruta>` (copia UTF-8 del log agregado). El CSV no cambia: mismo SHA-256 en el sintético.
- El modelo leyó el informe agregado ya existente `evaluation/reports/gtt_comet_v1_1.json`, sin abrir los
  `*_transitions.csv` y sin gastar otra evaluación pública.
- Guardó el hash del `gtt_comet_v1_1.csv` actual para comprobar que la reejecución lo reproduce byte a byte (C1).
- Comando dado: la v1.1 con `--log evaluation\reports\gtt_comet_v1_1_log.txt`. Commit: _pendiente_.

## 006 · 2026-10-21/22 · atacar las fronteras con el estudio

Texto: "ataca a eso entonces. tienes para aplicar la teoría que estudiamos de la posesión. está en
docs/ESTUDIO_POSESION creo. si algo de ahí te sirve de mejora, adelante. hecho. dale caña."

Respuesta (resumen):
- **Reejecución y log.** El modelo leyó el log de la v1.1 del fichero y comprobó que la reejecución reproduce el
  CSV byte a byte (C1).
- **Diagnóstico.** El log sin etiquetas responde L4 del estudio: el balón se ve en el 91 % de los frames vivos y
  en el 24 % de los `D`. La ventana pública (ya puntuada) muestra fronteras desplazadas más de 1 s.
- **v1.2**, aplicando el estudio:
  - evidencia de parada por ausencia larga del balón (3.3, punto 3, y L4), con dos pasadas y un paso de EM duro;
  - modelo sin balón con ventanas desplazadas para quitarle el retraso (3.3, punto 4, y P6);
  - cambio de equipo fechado en el primer toque (3.2, 4.6, P5);
  - estimación y corrección del retraso balón–jugadores por velocidad.
- **Probado y descartado** (documentado en el README): evidencia por hueco según longitud, cadena de Markov de
  visibilidad y estimador de retraso por posición.
- **Resultados.** Sintético v1.2: 0,728 / 0,789 / 0,755. Tests nuevos del fechado en el primer toque.
  Commit: _pendiente_.

## 007 · 2026-10-22 · evaluar y mejorar hasta gastar las 5 evaluaciones

Texto: "lo tienes? evalúa y mejora. tenemos que llegar a las 5 evaluaciones hoy. el equipo las necesita. guarda
resultados para la gráfica y a fuego."

Respuesta (resumen):
- **Lectura del log de la v1.2.** Sin retraso del balón; modelo sin balón al 87,9 / 83,8 % con el pico en 0;
  ausencia larga = 87,7 % `D`.
- **Evaluación pública n.º 3.** La ejecutó el modelo, solo sobre la v1.2 y con salida solo agregada: spellF1
  0,4800, macroF1 0,8331, transF1@25 0,216.
- **Tabla para la gráfica.** `prompts/confrontacion/a-opus/resultados.csv`: una fila por versión, con las
  métricas públicas, los agregados del partido completo sin etiquetas y la media sintética.
- **v1.3:** toques (estudio 3.1 y P3), λ = 3 y reinicio tras hueco largo (3.4). Sintético 0,761 / 0,810 /
  0,774. Commit: _pendiente_.

## 008 · 2026-10-22 · log de la v1.3

Texto: "hecho, ya está el log de la v1.3 en evaluation\reports\gtt_comet_v1_3_log.txt"

Respuesta (resumen):
- **Lectura del log.** Solo 70 toques en todo el partido: el detector por aceleración no encaja con el balón
  suavizado del ATD real.
- **Evaluación pública n.º 4** (solo la v1.3, salida agregada): idéntica a la v1.2 (0,4800).
- **Tabla para la gráfica:** añadida la fila de la v1.3.
- **v1.4:**
  - detector de toques por cambio neto de velocidad;
  - umbral con vuelo libre sin nadie a 4 m en la ventana;
  - asignación por distancia mínima en ±3 frames;
  - log con los recuentos de cada filtro;
  - generador con `--ball-style real` para reproducir el balón suavizado.
- **Resultados.** Sintético: ruidoso 0,775, estilo real 0,785. Commit: _pendiente_.

## 009 · 2026-10-22 · log de la v1.4

Texto: "hecho, ya está el log de la v1.4 en evaluation\reports\gtt_comet_v1_4_log.txt"

Respuesta (resumen). El log está sano salvo los toques: 422 picos y 213 asignados. Encaja con un balón suavizado a
~1 s. El modelo no gastó la evaluación n.º 5 y preguntó si gastarla en la v1.4 o preparar una v1.5.

## 010 · 2026-10-22 · el mejor candidato posible frente a B

Texto: "no es taaaan urgente. mejora todo cuanto puedas para sacar el mejor candidato frente al de edu."

Respuesta (resumen):
- **Banco de pruebas nuevo:** sintético con suavizado fuerte (`--smooth-half 12`), que reproduce la firma del
  balón real.
- **v1.5:**
  - toques a la escala elegida por partido (±6/12/25, sin etiquetas);
  - modelo sin balón también con el balón visible sin control claro, a medio peso.
- **Probado y desactivado** (sin mejora): fechado de cambios sin compuerta de velocidad y fechado de saques por
  media subida.
- **Descartado:** λ 2–2,5, toque a 2,5 nats y margen de 0,2 m.
- **Resultados.** Sintético: ruidoso 0,784 (v1.4: 0,775), suavizado 0,786 (v1.4: 0,774). Evaluación n.º 5
  reservada. Commit: _pendiente_.

## 011 · 2026-10-22 · tabla para Molines y valoración de la v1.5

Texto: "molines quiere que le pase estos resultados de la imagen. ya tienes el log de la 1.5. evalúa y si ves que
es un buen candidato, me dices y comparto. no hay prisa, podemos hacer un par de iteraciones si quieres aún."
(Con una captura del formato de tabla pedido. De la captura solo se usaron las cabeceras de columna.)

Respuesta (resumen):
- **Log de la v1.5 sano:** 214 posesiones, 49,3 % de `D`, 101 cambios directos. Pero los toques seguían flojos:
  balones aéreos en la referencia del umbral.
- **v1.6:** umbral con referencia de balón raso. Neutra en el sintético y dirigida al fallo real.
- **Evaluación n.º 5:** reservada para la v1.6 si su log sale sano.
- **Tabla:** preparada en el formato de Molines con las 4 evaluaciones hechas. Commit: _pendiente_.

## 012 · 2026-10-22 · log de la v1.6 y evaluación n.º 5

Texto: "hecho, ya está el log de la v1.6 en evaluation\reports\gtt_comet_v1_6_log.txt; si está sano, gasta la n.º 5
en ella"

Respuesta (resumen):
- **Log sano:** 219 posesiones, 113 paradas (49,3 %), 106 cambios directos y 622 toques asignados (el doble que
  la v1.5).
- **Evaluación pública n.º 5** (solo v1.6, salida agregada): spellF1 0,5250 (bootstrap 0,338–0,713), macroF1
  0,8391, 15 posesiones frente a 17, spellF1@0,7 0,375 y acierto de equipo 0,899. Es la mejor de las cinco, pero
  su intervalo solapa con las anteriores.
- **Cierre:** tabla completa en `resultados.csv` y en el formato de Molines. Se agotaron las 5 evaluaciones.
  Commit: _pendiente_.

## 013 · 2026-10-22 · commit, push y PR para Molines

Texto: "commit y push, le dejamos la PR ya lista a Molines. revisa qué más hay que checkear con esto ya hecho en
las issues, revisa las entradas en los logs. aviso nada más te mande este prompt de que ya está subido"

Respuesta (resumen):
- **Registros revisados:** se completa `desviaciones.md`, que estaba vacío.
- **Commit de la v1.6** en `cand/a-opus`.
- **Fusión de `main`** (Docker, contrato P0, P1; sin conflictos) y `configs/candidate_a.json` para la vía común
  `docker compose run --rm modelo`.
- **Push y PR** para Alejandro, sin fusionar hasta terminar la comparación (A10).
- **Issues:** lista de lo que se puede marcar en #26, #17, #15, #16 y #18 con esta entrega.
