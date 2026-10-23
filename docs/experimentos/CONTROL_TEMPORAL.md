# Control y continuidad temporal · experimento independiente

> 🇬🇧 **English version:** [CONTROL_TEMPORAL.en.md](CONTROL_TEMPORAL.en.md). This document was written in Spanish; the translation is kept in sync.

Hipótesis fijada antes de ejecutar sobre el partido: exigir proximidad inequívoca y movimiento compatible con control, y penalizar los cambios de estado, reducirá la fragmentación del consumidor nearest-player de P2. No se garantiza superar smooth50 ni se modifican los candidatos A/B.

## Reglas y parámetros iniciales

- Leer ATD y Smart Tagging locales; no consumir GT en el generador. Usar metros, máscaras e índices del contrato v1.
- Control candidato: jugador de equipo conocido a <= 2 m, ventaja de distancia >= 0,75 m sobre el otro equipo y velocidad observada del balón <= 8 m/s. Ambos equipos deben tener una distancia válida. Son umbrales físicos provisionales, no calibrados.
- Confirmar una racha de al menos cinco observaciones consecutivas del mismo equipo. Fechar la evidencia al inicio de la racha, sin retrasarla hasta la confirmación. Un hueco o cambio de parte rompe la confirmación. No derivar velocidad entre observaciones separadas por huecos.
- Evidencia H/A: 1 para el equipo confirmado y 0 para el otro. Sin control confirmado, ambas emisiones son neutras: no se inventa D por ausencia del balón.
- Viterbi offline de tres estados H/A/D, coste 8 por cambio y sin duración mínima de posesión. Las rachas cortas con evidencia suficiente pueden sobrevivir. En empates H/A colocar el cambio lo más tarde posible, manteniendo el último equipo durante un hueco.
- P2 conserva sus parámetros. D recibe +2 por frame con evidencia P2 >= 0,75; -2 cuando existe evidencia explícita de movimiento vivo; en otro caso -0,05, un prior débil contra paradas sin evidencia. Un reinicio P2 confirmado prohíbe D en ese frame. Los valores son puntuaciones, no probabilidades.
- Reiniciar por parte; fuera de los bloques, X. Sin evidencia de equipo aún en la parte, abstenerse salvo que P2 justifique D.

No se cambia todavía el detector de P2: primero se aísla el efecto del consumidor. La cobertura del segundo saque no demuestra que su frontera exacta sea correcta; refinarla requiere revisión local que no exponga material del partido.

## Validación fijada antes de los resultados

Pruebas sintéticas: decodificación contra búsqueda exhaustiva, ausencia y pases rápidos, confirmación y retrofechado, posesión corta sostenida, empate en huecos, parada real entre posesiones del mismo equipo, reinicio explícito, partes independientes, máscaras y parámetros inválidos y circuito completo con CSV de 199.319 filas.

Comparación Docker una vez por configuración, con repetición y bootstrap 1000: consumidor temporal con P2 desactivado y activado. Registrar cobertura de control, cambios, D/X, spellF1, macroF1, fragmentación, hashes y entorno. Frente al consumidor P2 anterior cambian control y decodificación a la vez: esa comparación evalúa el conjunto, no atribuye causalidad a una sola pieza. No barrer parámetros ni elegirlos con la ventana pública.

Referencias de diseño: `docs/ESTUDIO_POSESION.md`, secciones 3.2 y 4.5; [Vidal-Codina et al.](https://arxiv.org/abs/2202.00804). Es una implementación experimental de reglas propias, no una reproducción del artículo ni la integración acordada de #15/#16.

## Reproducción

Desde la raíz, con la imagen común ya construida:

```powershell
$env:DATOS = "C:/Users/pablo/Documents/dataTA/organized"
docker compose run --rm --pull never --entrypoint python evaluar -m unittest discover -s tests -v
docker compose run --rm --pull never modelo modelo --config configs/temporal_control_no_p2.json --repetir
docker compose run --rm --pull never modelo modelo --config configs/temporal_control.json --repetir
docker compose run --rm --pull never --entrypoint python evaluar scripts/summarize_p2.py --model temporal_control --out /salidas/temporal-comparison.json
```

El destino del resumen no debe existir: no se sobrescriben resultados. El exportador comprueba igualdad de fuentes, configuración salvo `p2_enabled`, tracking, entorno y evaluación. Solo exporta métricas y diagnósticos agregados permitidos. Los datos originales siguen en `dataTA`; no se ha usado `data/`, que solo contiene su README.

## Resultado Docker · 22 de octubre de 2026

**67 tests superados en 43,809 s.** Incluyen doce tests del modelo temporal, comparación con búsqueda exhaustiva y una generación/repetición/validación completa sobre tracking inventado. También pasan los tests existentes de P0/P1/P2 y cinco tests del exportador agregado.

Dos ejecuciones completas con datos locales, parámetros anteriores sin cambios y bootstrap 1000. Ambas generan 199.319 filas válidas, terminan con código 0 y repiten el mismo SHA-256. La variante con P2 se interrumpió a petición del usuario y se reanudó con la misma configuración; solo se usa su ejecución completada. No hubo barridos ni ajustes con el score público.

| Variante | spellF1 público | macroF1 público | Posesiones públicas | Fragmentación |
|---|---|---|---|---|
| Consumidor P2 anterior | 0,046575 | 0,505944 | 129 | 6,238095 |
| Temporal sin P2 | 0,351515 | 0,503413 | 16 | 0,761905 |
| Temporal con P2 | 0,375758 | 0,549703 | 16 | 0,809524 |
| smooth50 oficial | 0,325581 | 0,620733 | 26 | 1,428571 |

La referencia pública tiene 17 posesiones. El nuevo consumidor reduce la fragmentación frente al anterior, pero el recuento parecido no demuestra que las fronteras sean correctas. El aumento de spellF1 frente a smooth50 es de 0,050176; macroF1 sigue por debajo en 0,071030. El intervalo bootstrap 5–95 % de spellF1 es [0,230303; 0,521212] con P2 y [0,218182; 0,496970] sin P2; también se solapan con el de smooth50. No se afirma superioridad generalizable ni mejora del test privado.

La comparación controlada on/off mantiene el mismo consumidor: P2 aporta +0,024242 de spellF1 y +0,046291 de macroF1 en esta muestra, con fragmentación ligeramente mayor. La comparación con el consumidor anterior cambia control y decodificación simultáneamente; no atribuye esa ganancia solo a P2. Las métricas de vivo/parado son 0,879637 con P2 frente a 0,903313 del consumidor anterior: el mejor resultado temporal no mejora todas las dimensiones.

En los bloques completos, sin GT privada, el modelo con P2 produce **241 posesiones**, mediana 14,32 s, cinco de menos de 1 s y 10,046 % de frames D. Son estadísticas de predicciones, no medidas de acierto. El control confirmado cubre el 24,512 % de los frames de esos bloques; el resto depende de continuidad temporal y P2. Los huecos largos pueden arrastrar un equipo incorrecto o perder recuperaciones reales. Sin P2 hay 209 posesiones y ningún D; esa variante es una ablación, no una solución completa.

## Procedencia y límites de la entrega

Entorno: Docker Desktop 4.96.2 / WSL 3.0.3, Python 3.11.17, NumPy 2.4.6 y pandas 3.0.6. Commit base `d0916ffc803ae2f64fb3a8e813bbb8d170d7bf65`, con cambios del modelo todavía sin commit. Los dos registros conservan iguales hashes de fuentes y entradas comunes; el exportador los ha comprobado. Esto no equivale aún a reproducir desde un commit nuevo publicado. La validación anterior de P2 usó una copia LF limpia; este experimento usa el checkout Windows montado en Linux. No se afirma igualdad de bytes entre ambos checkouts.

| Variante | Run ID | SHA-256 del candidato |
|---|---|---|
| Sin P2 | `20261022T164032.446705Z-822120a376a2-modelo` | `9a4272f598f443960dc4a7f17a456b471a7e21ed11eee8178ee54e8a0707bd3a` |
| Con P2 | `20261022T164325.144461Z-384cce3c3433-modelo` | `baf41868594358edcd3258093dac4f61f52f19bf9eb4488864a4cd8fd74dfc7b` |

Evidencia local ignorada: `salidas/temporal-comparison-docker-final.json`, `salidas/temporal-full-match-summary.json` y `salidas/temporal-control-tests-final.log`. Los registros completos y las predicciones permanecen locales. Los tiempos del pipeline (67,9 s y 66,6 s) incluyen repetición y evaluación; no son benchmarks de inferencia ni justifican comparar velocidad entre variantes.

Decisión: conservar la nueva implementación como experimento reproducible y llevarla a revisión; no sustituir automáticamente la solución oficial del equipo ni cerrar #15/#16. P2 mantiene su detector y la incertidumbre del segundo saque inicial. Antes de adoptar: revisión local de fronteras y posesiones cortas, validación externa sin ajustar sobre esta ventana y revisión de otro integrante. La evidencia de esta sección se obtuvo antes del commit de entrega; no se ha publicado el log del equipo.
