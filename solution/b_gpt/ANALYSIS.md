# Lectura de las métricas públicas recibidas

Esta nota usa únicamente los agregados facilitados por el participante. No se ha
abierto ningún CSV del partido ni se modifica el método a partir de estos resultados.

## Qué mejora se observa

`spellF1` pasa de 0,3256 a 0,3895: **+0,0639**. `macroF1` aumenta **0,0413**.
Se pasa de 26 a 21 posesiones frente a 17 reales, y de 10,8 a 13,6 s de duración
media frente a 14,2 s. Es compatible con menor fragmentación, pero acertar un conteo
o una media no garantiza acertar los intervalos ni sus equipos.

La fórmula permite separar descriptivamente parte de la subida. En cada umbral IoU:

`F1 = 2 × TP / (N_GT + N_pred)`.

El denominador es constante entre los cinco umbrales, así que también se cumple para
la media de los TP. Con los números redondeados proporcionados:

- Baseline: `0,3256 × (17 + 26) / 2 ≈ 7,0` emparejamientos medios.
- Candidato: `0,3895 × (17 + 21) / 2 ≈ 7,4` emparejamientos medios.
- Manteniendo 7,0 emparejamientos y bajando a 21 predicciones, el F1 sería
  `14 / 38 ≈ 0,3684`: aproximadamente **0,0428** del aumento se explica por el menor
  denominador. Los **0,0211** restantes corresponden al aumento de emparejamientos.

Por tanto, aproximadamente dos tercios de la subida corresponden a menor número de
predicciones, y un tercio a más emparejamientos. Es una descomposición aritmética, no
una ablación causal ni prueba de que se hayan eliminado exactamente cinco errores.
Tampoco equivale exactamente a «una posesión más»: son unos **0,4 emparejamientos
medios adicionales** entre umbrales. Una posesión puede emparejarse en unos IoU y en otros no.

Los IC 90 % `[0,214, 0,447]` y `[0,242, 0,537]` se solapan ampliamente. Con solo 17
posesiones no hay base para afirmar una mejora generalizable. El solapamiento de dos
intervalos marginales tampoco es un test formal de la diferencia; haría falta un
análisis pareado para eso. No se utiliza la ventana para elegir un umbral o versión.

## Qué podría generalizar

La separación entre «balón no observado» y «balón parado» aborda un fallo estructural
documentado: el balón falta en muchas imágenes, también durante juego vivo. Mantener
la posesión durante una oclusión puede evitar falsos cortes en cualquier tramo del
partido. Lo mismo ocurre al exigir proximidad absoluta y evidencia persistente antes
de cambiar al rival durante un pase. Son razones de continuidad y control, independientes
del número de posesiones de esta ventana.

El coste de cambio y la decodificación sin reducir la frecuencia temporal también
pueden conservar intervalos completos sin desplazar sistemáticamente los límites.
Pero pueden fusionar posesiones cortas reales o retrasar cambios ocultos. La mezcla de
oclusiones, saques, faltas y ataques puede ser distinta en el resto del partido. No
se extrapola el +0,0639, ni se adopta 21 posesiones/13,6 s como objetivo.

## Por qué asignar el equipo puede no mejorar

El candidato conserva esencialmente la misma fuente de información: distancias entre
el balón y el jugador más cercano de cada equipo. La confianza y la continuidad
regularizan esa decisión; no añaden observaciones independientes de quién controla.

Si el balón 2D proyectado pasa cerca de un rival durante un vuelo, falta el receptor
en el tracking, se confunden equipos o se pierde el balón durante el cambio, ambos
métodos pueden equivocarse de la misma manera. Smart Tagging se infiere de las mismas
entradas y describe fases, no posesiones completas; no es un segundo anotador fiable.
Mantener el último equipo puede corregir fluctuaciones, pero también mantener el
equipo anterior demasiado tiempo. Es plausible mejorar la estructura sin aumentar
el acierto de equipo por frame.

Hay además dos métricas distintas en el evaluador: acierto sobre todos los frames
GT vivos y acierto condicionado a que GT **y predicción** estén vivos. Cambiar `D`
modifica el denominador de la segunda. Para comparar hay que usar el mismo campo;
la tabla abreviada no permite saber cuál se reportó.

## Qué no permiten concluir los valores recibidos

La fila del candidato no incluye F1 de `D` ni acierto de equipo. Se toma la observación
verbal de que el equipo no mejora como información adicional del participante; no
se puede comprobar ni cuantificar con esa fila. La subida de `macroF1` por sí sola
no demuestra que mejore `D`.

De hecho, si no hay abstenciones dentro de la ventana y las medias corresponden a
los mismos tramos puntuados, los productos aproximados sugieren:

- Baseline: `26 × 10,8 ≈ 280,8 s` de posesión viva en 300 s.
- Candidato: `21 × 13,6 ≈ 285,6 s` de posesión viva.

Eso dejaría aproximadamente **6,4 %** y **4,8 %** de `D`, respectivamente, frente al
~19,6 % publicado para la ventana. Son inferencias con medias redondeadas y supuestos
sobre el alcance del informe; los porcentajes exactos deben salir del diagnóstico.
Tener menos `D` no impide mejorar su F1 si aumenta la precisión, pero no demuestra
mejor cobertura de paradas. Por ello se añaden porcentajes y coherencia de reinicios
para todo el partido sin consultar la GT, en vez de retocar el detector.

## Decisión de esta versión

Se mantiene el método y todos sus parámetros. Se añaden diagnósticos simétricos para
el candidato y el baseline, con denominadores explícitos. La coherencia con Smart
Tagging es una comprobación interna y parcialmente circular: el candidato ya usa
esas anotaciones. Sirve para detectar comportamientos sospechosos, no para estimar
`spellF1` ni para maximizar esa coherencia a costa de etiquetar todo como `D`.

Mejorar de verdad la asignación de equipo requeriría evidencia adicional de recepción,
control y trayectoria, o validación externa con semántica compatible. No se añade ahora
un clasificador ni se cambian radios o costes basándose en estos cinco minutos.
