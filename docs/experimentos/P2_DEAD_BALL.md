# P2 · Interrupciones y reinicios (#14)

Hipótesis previa a la ejecución: combinar salidas observadas del campo con preparación y movimiento dentro del contexto de reinicio puede recuperar interrupciones reales sin convertir las oclusiones en D. No se presupone una mejora de spellF1.

## Interfaz y alcance

`solution.dead_ball.detect()` recibe geometría en metros, máscaras, periodos y eventos del loader oficial; devuelve `dead_score`, `restart_score`, `dead_valid`, `restart_valid` y candidatos locales. Arrays de longitud N; ausencia = NaN y máscara falsa. Los scores son evidencia, no probabilidades. No consume GT ni identidades de jugador.

Se conserva el contrato v1: ATD `frame_id - 1`; eventos `round(seconds * fps)`; intervalos semiabiertos; dimensiones y bloques de `games.py`. Solapes del mismo tipo se combinan por máximo. Equipos contradictorios se conservan en los eventos, sin decidir H/A. N/A sigue desconocido. El contexto táctico general H/A corresponde a #20.

## Reglas iniciales, fijadas antes de resultados

- Salida: tres observaciones consecutivas más de 0,5 m fuera del rectángulo; inicio fechado en la primera. No se recortan coordenadas.
- Movimiento: velocidades derivadas solo entre observaciones originales consecutivas de la misma parte; se descartan saltos superiores a 45 m/s. Reinicio requiere tres frames de movimiento a al menos 2 m/s.
- Preparación general: al menos cinco frames consecutivos de balón a como máximo 0,5 m/s, en una zona compatible con el tipo de saque y dentro de su ventana automática. Se busca después movimiento sostenido; no se copia el intervalo completo como D. El primer saque inicial tiene la regla específica siguiente.
- Zonas iniciales: córner a <= 5 m de ambas líneas; banda a <= 3 m de la línea lateral; saque de puerta a <= 18 m de una línea de fondo; falta sin zona impuesta. Son aproximaciones geométricas, no validaciones reglamentarias de la posición exacta del saque.
- Un saque de banda admite reentrada desde fuera con movimiento sostenido. Un balón que reaparece después de un hueco no aporta velocidad durante el hueco.
- El primer evento de saque inicial de cada parte aporta contexto D hasta el comienzo de su ventana. Se busca movimiento sostenido que comience cerca del centro (radio 3 m), sin exigir inmovilidad previa. Si se confirma, D se extiende hasta ese reinicio; si no, el interior de la ventana queda incierto. Los números publicados del saque sirven solo para diagnóstico, no para generar etiquetas.
- La quietud colectiva (mediana de velocidad <= 1,5 m/s, mínimo seis slots observados) refuerza preparación, nunca genera D por sí sola. No se derivan trayectorias por identidad de slot.
- Una salida confirmada puede sostener evidencia de interrupción hasta reentrada en movimiento o un reinicio contextual confirmado, durante un máximo de 90 s; al agotar el horizonte se vuelve a desconocido. No se afirma que una ausencia sea D: la evidencia procede de la salida previa.
- El límite de 90 s afecta a salidas sin frontera contextual emparejada. Una preparación con reinicio confirmado tiene su propio final observado; el tramo inicial previo al saque puede superar ese horizonte.
- Sin evidencia suficiente no se fuerza una decisión. Se reinicia el contexto entre partes.

## Integración experimental

Modelo interno `baseline_dead_ball`: mismo nearest-team y hold de P1 en ambas variantes; solo cambia `enabled`. Umbral de integración D = 0,75; reinicios confirmados cortan la conservación de D. Es un consumidor provisional de señales, no la implementación de Viterbi de #16. La integración final requiere revisión de Jimy/Alejandro y no altera los candidatos A/B congelados.

## Validación prevista

Pruebas sintéticas de índices, ausencia, preparación, movimiento, solapes, fuera de campo, reinicio de partes y fronteras. Después, referencias oficiales y comparación on/off con repetición en Docker. Una comparación pública por variante, sin barrido de parámetros. Se registrarán métricas, cobertura, candidatos, conflictos, configuración, hashes y limitaciones. Revisar localmente los errores futbolísticos sin publicar intervalos ni materiales del partido. Revisión humana/CI externa pendiente hasta disponer de evidencia.

## Reproducción

Desde la raíz del repo, con Python y las dependencias de `docker/requirements.lock` instaladas:

```powershell
.\scripts\prepare_data.ps1 -Source "D:\pcordoba\Documents\dataTA" -Destination "D:\pcordoba\Documents\dataTA\organized"
.\scripts\verify_p2.ps1 -DataDir "D:\pcordoba\Documents\dataTA\organized" -Python ".\.venv\Scripts\python.exe"
```

La preparación comprueba duplicados por SHA-256, no sobrescribe archivos distintos y crea enlaces duros a los vídeos de la misma unidad; no duplica sus contenidos. Requiere permisos de escritura en el destino. Las señales solo consumen tracking y Smart Tagging, no vídeo ni homografía. No abrir los assets con un LLM cloud.

Diagnóstico agregado, sin puntuar:

```powershell
python -m solution.dead_ball --data-dir "D:\pcordoba\Documents\dataTA\organized" --out salidas/p2-diagnostic.json
```

Docker, cuando su motor y la imagen común descrita en `docs/DOCKER.md` estén disponibles:

```powershell
.\scripts\verify_p2.ps1 -DataDir "D:\pcordoba\Documents\dataTA\organized" -Docker
```

El script Docker usa `--no-build`, montaje de datos de solo lectura y el mismo pipeline. No ejecuta compilaciones del backend. El chequeo byte a byte del baseline puede detectar diferencias de finales de línea entre un checkout Windows y Linux: no editar la referencia ni presentar ese código 4 como éxito; diagnosticarlo por separado.

Cada variante genera, valida y repite su CSV antes de evaluarlo; el resumen controlado comprueba configuración, código, entorno y hashes de entradas comunes. Las salidas y los informes completos quedan ignorados bajo `salidas/`. Los registros P2 incluyen hashes de los fuentes del modelo, además del commit y el estado del árbol; una ejecución con cambios pendientes no equivale a una reproducción desde un commit publicado.

En esta máquina se ha creado `.venv` con Python 3.12.14 y acceso a las dependencias ya disponibles del runtime local (NumPy 2.3.5 y pandas 3.0.1). No se presenta como el entorno fijado de Docker, que sigue pendiente. No se han cambiado las dependencias bloqueadas del equipo.

## Límites de la primera versión

No detecta directamente silbatos, faltas o sustituciones. Un falso evento, movimiento de colocación del balón o tracking desplazado pueden provocar fronteras incorrectas. La geometría 2D no determina si el balón entero cruzó una línea ni distingue altura. Las velocidades colectivas agregan slots observados, con posibles duplicados; no representan identidades estables. Sin movimiento observado suficiente, el saque inicial puede quedar sin refinar; los demás reinicios exigen además preparación. No existe garantía de recuperar todas las interrupciones ni de mejorar el test privado.

## Estado de Docker en esta máquina

22 de octubre de 2026: Docker Desktop 4.11.1 termina con `Access denied`; grupo `docker-users` vacío. Compose valida estáticamente, pero el motor no está disponible. El usuario ha indicado continuar en Python y dejar Docker pendiente. No se modifican grupos, no se cierra sesión y no se declara validación de contenedores. La documentación oficial explica este error: https://docs.docker.com/desktop/troubleshoot-and-support/troubleshoot/topics/.

## Corrección de aceptación antes de la versión final

La primera comparación reproduce ambos CSV y verifica las entradas, pero la comprobación específica del segundo saque inicial falla: 0 saques iniciales refinados y solo 17,21 % del tramo previo marcado D. Se corrige por este criterio funcional, no para maximizar el score público. Los umbrales físicos permanecen iguales.

Regla revisada: el primer evento `Kick Off (Start)` de cada parte aporta contexto D desde el comienzo del bloque hasta el comienzo de su ventana. Dentro de esa ventana se busca movimiento sostenido que comience junto al centro, sin exigir inmovilidad consecutiva previa. Si se confirma, la frontera se fecha al primer movimiento de esa secuencia; si no, el interior de la ventana permanece incierto. No se etiqueta la ventana entera como D ni se introducen los frames publicados en la generación. La etiqueta automática puede estar desfasada o ser falsa: se conserva esta limitación.

La comparación inicial queda como evidencia de fallo de cobertura: spellF1 0,04414 → 0,04658, macroF1 0,46039 → 0,50611. La fragmentación empeora de 6,0952 a 6,1905. No se adopta por esas cifras; ambas variantes siguen lejos de smooth50 (0,32558 público). Se repetirá la comparación controlada después de la corrección, sin barridos de parámetros.

## Verificación y resultado final · 22 de octubre de 2026

**53 tests superados** en 101,145 s, sin fixtures del partido. Incluyen contrato, P0/P1, P2, generación sintética de 199.319 filas, reinicios, segunda parte, duplicados de eventos y rechazo de comparaciones con código/datos/parámetros diferentes. `git diff --check` y `docker compose config --quiet` con la ruta real de datos pasan.

Datos: 13 entradas ZIP comprobadas; siete assets únicos extraídos y dos vídeos enlazados bajo `dataTA/organized`. Repetir la preparación crea cero archivos. Los cuatro baselines oficiales se han regenerado con tracking real, coinciden byte a byte con los publicados en este checkout y dan los mismos hashes en dos ejecuciones. La evaluación pública de referencias termina con código 0.

Comparación final en Python local, `public-5min`, bootstrap 1000, mismo commit base `88f4724`, árbol con cambios propios pendientes, mismos hashes de código, entorno y entradas comunes. Solo cambia `enabled`; P2 activado añade Smart Tagging a su manifiesto. El comprobador automático verifica estas condiciones. No es una comparación con Viterbi ni con un candidato A/B.

| Variante | spellF1 | macroF1 | alive_dead_f1 | Posesiones | Duración media (s) | Fragmentación | X públicos |
|---|---|---|---|---|---|---|---|
| P2 desactivado, P1 hold 25 | 0,0441379310 | 0,4603944218 | 0,8964002823 | 128 | 2,34375 | 6,0952380952 | 780 |
| P2 activado | 0,0465753425 | 0,5059441824 | 0,9033125148 | 129 | 2,29333 | 6,2380952381 | 778 |
| smooth50 oficial, referencia pública | 0,3255813953 | 0,6207331924 | — | 26 | 10,8031 | 1,4285714286 | 0 |

`alive_dead_f1` usa juego vivo como clase positiva. Los CSV de ambas variantes validan y se reproducen byte a byte; ambas ejecuciones terminan con código 0. Los hashes y run IDs identifican resultados locales, no un commit nuevo publicado:

| Variante | Run ID | SHA-256 del candidato |
|---|---|---|
| Desactivada | `20261022T121354.904987Z-8e806a17987b-modelo` | `a0597187862e3a23ae9bf9d5534ca788271193a55fa95b1520b368fd661a6b18` |
| Activada | `20261022T121550.600410Z-f8facff86c9d-modelo` | `83d82503bb861edff3f61f92070a1615b70f703f69d0849f3994d51482f93e7e` |

Evidencia agregada local: `salidas/p2-comparison-final.json`; tests: `salidas/p2-tests-acceptance.log`. No publicar los informes completos ni los CSV. El exportador de comparación solo copia campos agregados permitidos.

Con P2 se generan 66 candidatos de interrupción y 54 frames candidatos de reinicio; hay tres frames con evidencias D/reinicio simultáneas. El consumidor experimental da prioridad al reinicio y limpia el D retenido. Se refina uno de los dos saques iniciales. La cobertura D del tramo publicado anterior al segundo saque pasa de 0 % sin detector a **97,1029 %**; no equivale a acertar su frontera exacta ni a cubrir todo el tramo. Ese reinicio sigue sin refinar y necesita revisión futbolística local. En el partido completo se emiten 16.021 frames D, frente a cero en P1; no conocemos su calidad sin GT privada.

**Decisión: resultado mixto, conservar como componente experimental.** La mejora pública de spellF1 es pequeña y la fragmentación empeora; no se afirma mejora generalizable ni se sustituye smooth50. El objetivo de P2 es aportar señales de interrupción; el nearest-player de este consumidor sigue fragmentando y no implementa el control de #15 ni el decodificador de #16.

Pendiente para aceptación/cierre de #14: motor Docker habilitado por el usuario y repetición en el entorno fijado; revisión visual local de falsos cortes y reinicios omitidos, especialmente el segundo saque; revisión de interfaces con Jimy/Alejandro/Nico, integración con el consumidor final #16 y CI/revisión de otro integrante. La entrada de log propuesta no se ha publicado. No cerrar la issue únicamente por los tests ni por la tabla pública.

## Log público propuesto (EN)

P2 investigates dead-ball and restart evidence from observed pitch exits and set-piece context. Missing ball observations do not trigger stoppages. Tagged phases only define search windows; motion refines restart boundaries. We will test synthetic transitions and compare the same P1 consumer with P2 enabled and disabled. Thresholds are fixed before public evaluation. Full-match data and frame-level outputs stay local. This is a draft for the team log; it has not been published.
