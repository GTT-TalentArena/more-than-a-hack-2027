# Prompts (variante B + Claude)

Mensajes de Edu a Claude Code en esta variante, en orden. Las respuestas, resumidas.

## 1. 2026-10-21 · ~21:31
> vale si consideras que podríamos añadir alguna mejora, tienes que hacerla tu, y lo anotamos que hemos usado claude para la mejora, y asi comparamos tambien el resultado solo de codex el v0 y con la mejora el v1

**Respuesta:** Claude avisó de que mezclar proveedores cambia el protocolo y propuso una variante aparte (tag `b-gpt-v0` + rama `cand/b-gpt-claude` + registro propio), condicionada a la aprobación de Alejandro.

## 2. 2026-10-21 · 21:33
> (captura de WhatsApp) Alejandro: «Me parece bien» · «Muy buena idea»

**Respuesta:** Claude creó el tag `b-gpt-v0` y la rama, leyó el código de `solution/b_gpt/` (no los datos) y propuso un único cambio justificado por las reglas del juego: tratar como parada el hueco de tracking que sigue a una salida clara del balón del campo.

## 3. 2026-10-21 · durante la sesión
> anota la hora de entrada y salida, y el modelo, estas en Opus 5.5 y el effort no estoy seguro

> el effort esta en medium

**Respuesta:** Claude implementó el cambio con 3 tests sintéticos (el principal falla con la v0 y pasa con la v1), comprobó el determinismo con 199.319 frames sintéticos, documentó la variante y abrió este registro.
