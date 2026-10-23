# More than a Hack 2027

> 🇬🇧 **English version:** [GUIA_PROYECTO.en.md](GUIA_PROYECTO.en.md). This document was written in Spanish; the translation is kept in sync.

## Guia del proyecto - Phase 1: Ball Possession

> **Equipo:** [GTT-TalentArena](https://github.com/GTT-TalentArena)  
> **Repositorio:** [more-than-a-hack-2027](https://github.com/GTT-TalentArena/more-than-a-hack-2027)  
> **Objetivo:** detectar quien tiene la posesion del balon en cada frame.

---

## Resumen ejecutivo

| Elemento | Detalle |
|---|---|
| Partido | FC Barcelona vs Athletic Club |
| Video de referencia | Video tactico |
| Frames totales | **199.319** |
| Frecuencia | 25 fps |
| Salida | CSV con una etiqueta por frame |
| Metrica principal | **spellF1** |
| Equipo | 3 a 5 miembros |
| Fecha limite indicada | **17 de noviembre de 2026** |

> **Idea clave:** la clasificacion premia posesiones completas y coherentes, no solo aciertos aislados por frame.

---

## 1. Objetivo y etiquetas

Hay que asignar una etiqueta a cada frame del video tactico:

| Etiqueta | Significado |
|---|---|
| `H` | Barcelona tiene la posesion y el balon esta en juego |
| `A` | Athletic Club tiene la posesion y el balon esta en juego |
| `D` | Balon parado o fuera de juego |
| `X` | El sistema no quiere responder |

El video tiene 199.319 frames. Una posesion es una secuencia maxima y continua de `H` o de `A`; los periodos `D` son interrupciones.

```text
H H H H A A A D D H H
```

Representa tres posesiones: Barcelona, Athletic Club y Barcelona despues de una interrupcion.

No existen etiquetas oficiales como `disputa`, `transicion` o `balon dividido`.

---

## 2. Partido y datos

- Barcelona es el equipo local: `H`.
- Athletic Club es el visitante: `A`.

### Video tactico

Es la fuente principal:

- 199.319 frames.
- 25 fps y resolucion 1920x1080.
- Tracking automatico de jugadores y balon.
- Homografia entre imagen y campo.
- Smart Tagging tactico.
- 46 slots de tracking.
- El balon aparece aproximadamente en el 57 % de los frames totales.

### Video de retransmision

Es opcional, tiene aproximadamente 164.488 frames y una linea temporal diferente, con cortes y repeticiones. Si se usa, el equipo debe sincronizarlo con el video tactico.

> La entrega siempre se indexa al video tactico. Un archivo de unas 164.000 filas sera rechazado.

### Estructura local de los datos

```text
data/
|-- tactical/
|   |-- BAR-ATH_tactical.mp4
|   |-- BAR-ATH_tactical_atd.xml
|   |-- BAR-ATH_tactical_atd.txt
|   |-- BAR-ATH_tactical_homography.csv
|   `-- BAR-ATH_tactical_smart_tagging.xml
`-- broadcast/
    |-- BAR-ATH_broadcast.mp4
    |-- BAR-ATH_broadcast_atd.xml
    |-- BAR-ATH_broadcast_atd.txt
    `-- BAR-ATH_broadcast_homography.csv
```

### Reglas sobre los datos

- No subirlos a GitHub.
- No redistribuirlos.
- No incluirlos en la documentacion publica.
- No publicar videos recortados, tracking exportado ni derivados reconstruibles.
- Mantener `data/` excluido mediante `.gitignore`.

---

## 3. Limitaciones del tracking

El tracking es automatico y no esta corregido:

- No hay identidades reales de jugadores.
- Los 46 slots no representan necesariamente a 46 personas.
- Un slot puede cambiar de jugador.
- Puede haber huecos, duplicados y cambios de identidad.
- Las coordenadas estan normalizadas entre 0 y 1.
- El balon falta aproximadamente en el **41 % de los frames evaluados**.

Por eso la solucion debe trabajar con informacion colectiva: equipo, posiciones, distancias, velocidad, zonas del campo y continuidad temporal.

---

## 4. Definicion de posesion

Una posesion cambia cuando un jugador del equipo contrario consigue el control del balon.

### No implica necesariamente un cambio

- Un simple toque.
- Un rebote.
- Una desviacion de un pase.
- Ganar un duelo aereo sin controlar posteriormente el balon.

### Posibles senales de control

- El jugador mantiene el balon durante varios segundos.
- El equipo completa varios pases consecutivos.
- La situacion permanece estable durante varios frames.
- La distancia al jugador mas cercano favorece claramente a un equipo.

> La ground truth publica tiene prioridad sobre cualquier interpretacion teorica.

---

## 5. Frames puntuados

Los intervalos evaluados son:

- Primera parte: `11.185-90.651`.
- Segunda parte: `110.808-190.197`.

El intervalo `110.808-113.741` esta puntuado como `D`, porque el segundo tiempo aun no ha comenzado. El resto de frames previos, del descanso y posteriores al partido no se puntua.

---

## 6. Metricas

### `spellF1`

Es la metrica principal y decide la clasificacion. Compara posesiones predichas y reales como intervalos temporales mediante IoU en los umbrales `0.3`, `0.4`, `0.5`, `0.6` y `0.7`.

Una solucion puede tener buen `macroF1` y mal `spellF1` si cambia de etiqueta continuamente y crea muchas posesiones artificiales.

### `macroF1`

Es la media del F1 de `H`, `A` y `D` por frame. Se informa como primer desempate, pero no es la metrica principal.

### Baseline de referencia

```text
spellF1 = 0.2433
```

Nuestro objetivo inicial es superar ese resultado.

---

## 7. Tratamiento de `X`

`X` significa que el sistema no quiere dar una respuesta fiable.

- En `macroF1`, un `X` dentro de una zona puntuada cuenta como fallo.
- En `spellF1`, el evaluador lo rellena con la ultima etiqueta valida de esa parte.
- Un `X` dentro de una posesion estable puede ser util.
- Un `X` justo en una transicion puede arrastrar la etiqueta anterior y ser perjudicial.
- Fuera de las zonas puntuadas no tiene coste.
- Nunca se deben dejar celdas vacias: hay que escribir `X`.

---

## 8. Normas

### Permitido

- Cualquier lenguaje y framework.
- Modelos clasicos, machine learning y modelos preentrenados.
- LLMs y APIs comerciales, si los organizadores pueden inspeccionarlos.
- Datos externos.
- Detector, tracking o reconocimiento de eventos propios.
- Mejorar o sustituir los datos automaticos proporcionados.

### Prohibido

- Etiquetar el video a mano.
- Corregir manualmente el CSV frame a frame.
- Usar la ground truth privada o datos derivados de ella.
- Entregar un archivo que el repositorio no pueda regenerar exactamente.
- Depender de un modelo privado o dataset inaccesible para los organizadores.
- Publicar los datos del partido o derivados reconstruibles.

Se permite etiquetar manualmente una pequeña cantidad de datos para entrenar o validar un modelo, pero las etiquetas finales deben salir del algoritmo.

### Restriccion sobre LLMs

No se deben subir a servicios LLM cloud externos los videos, datasets, informacion confidencial, material restringido ni extractos que permitan reconstruirlos. Para esos materiales debemos usar procesamiento local o verificar previamente las condiciones del servicio.

---

## 9. Codigo incluido

| Ruta | Funcion |
|---|---|
| `games.py` | Constantes, rutas, frames, pitch y alineacion |
| `evaluation/possession_metrics.py` | Metricas, segmentos, matching y validacion |
| `evaluation/run_evaluation.py` | Evaluacion de los CSV en `evaluation/results/` |
| `evaluation/validate_submission.py` | Validacion del contrato del CSV |
| `starter/baseline.py` | Jugador mas cercano al balon y suavizado temporal |
| `starter/load_atd.py` | Carga del tracking |
| `starter/load_smart_tagging.py` | Carga Smart Tagging |
| `starter/load_homography.py` | Carga la homografia |
| `starter/*.ipynb` | Tutoriales desde los datos hasta la primera entrega |

### Baseline

1. Busca el jugador mas cercano al balon.
2. Asigna la posesion a su equipo.
3. Si no ve el balon, usa `D`.
4. Aplica una votacion mayoritaria temporal.

No utiliza video, Smart Tagging, homografia, modelo entrenado, estado de posesion ni logica especifica para reinicios.

---

## 10. Requisitos y comandos

### Requisitos

- Python 3.8 o superior.
- `numpy` y `pandas` para evaluacion y baseline.
- Dependencias adicionales de `requirements-starter.txt` para notebooks y visualizacion.
- La documentacion menciona especialmente `kloppy` y `matplotlib`.

### Instalacion y evaluacion

```bash
pip install -r requirements.txt
python starter/baseline.py
python evaluation/run_evaluation.py
python evaluation/validate_submission.py mi_submission.csv
```

Orden recomendado de notebooks:

1. `01_smart_tagging.ipynb`
2. `02_tracking_atd.ipynb`
3. `03_first_submission.ipynb`

---

## 11. Formato de la entrega

```csv
frame,label
0,X
1,X
2,D
3,D
4,H
...
199318,X
```

| Requisito | Condicion |
|---|---|
| Cabecera | Exactamente `frame,label` |
| Filas | Exactamente 199.319 filas de datos |
| Frames | `0` a `199318`, en orden |
| Etiquetas | Solo `H`, `A`, `D` o `X` |
| Celdas | Ninguna vacia |
| Codificacion | UTF-8 |
| Indice | No incluir columna de indice |

Un archivo mal formado se omite y obtiene cero. Hay que validar exactamente el archivo que se vaya a subir.

---

## 12. Entregables

### 1. Archivo de posesion

CSV completo con 199.319 filas.

### 2. Repositorio publico

Debe contener:

- Codigo fuente.
- Dependencias fijadas.
- Instrucciones de instalacion y ejecucion.
- Comando para regenerar el CSV.
- Todo lo necesario para reproducir exactamente la entrega.

No debe contener los datos del partido.

### 3. Documento tecnico

Debe explicar:

- Enfoque y motivo de la eleccion.
- Assets utilizados y descartados.
- Reglas para cambios de posesion.
- Tratamiento de rebotes, duelos, balones sueltos y reinicios.
- Uso de `X`.
- Limitaciones.
- Instalacion, ejecucion y reproduccion.

---

## 13. Repositorio del equipo

La mejor opcion es trabajar sobre un fork del repositorio oficial dentro de la organizacion del equipo.

Ruta local:

```text
D:\amolines\Documents\AMolines\TArena\more-than-a-hack-2027
```

Estructura recomendada:

```text
more-than-a-hack-2027/
|-- data/                 # local, nunca se sube
|-- evaluation/
|-- starter/
|-- solution/
|   |-- main.py
|   |-- features.py
|   |-- possession_model.py
|   `-- postprocess.py
|-- docs/
|   `-- GUIA_PROYECTO.md
|-- requirements.txt
`-- README.md
```

Trabajad con ramas para cada experimento y revisad los cambios antes de incorporarlos a `main`.

---

## 14. Plan de trabajo

### Fase 1 - Entorno

- Confirmar el fork del equipo.
- Instalar dependencias.
- Descargar los datos y colocarlos en `data/`.
- Ejecutar el baseline.

### Fase 2 - Comprension

- Revisar tracking y frames sin balon.
- Visualizar posiciones.
- Analizar Smart Tagging.
- Entender la homografia.
- Comprobar la alineacion.
- Estudiar los 17 segmentos publicos.

### Fase 3 - Solucion

Considerar continuidad temporal, histeresis, duracion minima, estado anterior, reinicios, balon perdido, distancias, velocidad, posicion colectiva, Smart Tagging y zonas del campo.

### Fase 4 - Evaluacion

- Usar la ventana publica para comprobar formato y alineacion.
- No escoger hiperparametros solo por la puntuacion publica.
- Medir numero y duracion de posesiones.
- Priorizar `spellF1`.
- Validar cada CSV.

### Fase 5 - Entrega

- Congelar dependencias.
- Probar desde un entorno limpio.
- Regenerar el CSV desde cero.
- Ejecutar `validate_submission.py`.
- Comprobar que no hay datos privados publicados.
- Preparar el documento tecnico y el formulario.

---

## 15. Checklist final

- [ ] El repositorio publico puede regenerar la entrega.
- [ ] `data/` esta ignorado.
- [ ] No hay videos, tracking, XML, CSV privados ni derivados publicados.
- [ ] No se usa la ground truth privada.
- [ ] Las etiquetas finales las genera el algoritmo.
- [ ] El CSV tiene exactamente 199.319 filas.
- [ ] Los frames van de `0` a `199318` en orden.
- [ ] Solo aparecen `H`, `A`, `D` y `X`.
- [ ] No hay celdas vacias.
- [ ] `validate_submission.py` devuelve `OK`.
- [ ] El documento tecnico explica metodo, datos, reglas y limitaciones.
- [ ] El equipo tiene entre 3 y 5 personas.

---

## La pregunta que debe guiar nuestra solucion

> **¿Ha cambiado realmente la posesion o estamos viendo ruido, un rebote, una perdida temporal del tracking o un balon disputado?**

La metrica premia posesiones coherentes. Por eso es mas importante diseñar un buen modelo temporal de estados y transiciones que utilizar necesariamente un modelo enorme.

---

## Fuentes oficiales

- [CHALLENGE.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/CHALLENGE.md)
- [DATA.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/DATA.md)
- [EVALUATION.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/EVALUATION.md)
- [RULES.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/RULES.md)
- [SUBMISSION.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/SUBMISSION.md)
- [FAQ.md](https://github.com/metrica-sports/more-than-a-hack-2027/blob/main/FAQ.md)
