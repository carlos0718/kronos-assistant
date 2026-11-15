# Mediciones de Kronos AI Assistant

> Primera medición: 14 nov. 2026, sobre la versión 0.8.0. Sirve para decidir el hardware mínimo y recomendado (ver "Preguntas abiertas" en el [README](../README.md)). Falta medir en un equipo más modesto y con un modelo en la nube.

## Cómo se mide

Hay dos formas, y miden lo mismo: cuánto pasa entre que el usuario termina de hablar y que Kronos empieza a responder.

| Forma | Cuándo sirve |
|---|---|
| `pnpm engine:measure` | Para comparar equipos y modelos. No usa micrófono ni altavoz: genera una pregunta con la voz de Kronos y la pasa por las piezas reales (transcribir → modelo → voz). Repite cinco veces e informa la mediana, más el consumo del motor. Necesita Ollama abierto. |
| La línea `Tiempos del turno` de la terminal | Para ver una conversación real. El motor la escribe después de cada respuesta: `Tiempos del turno: transcribir 2,24 s · modelo 0,31 s · voz 0,09 s · total 2,64 s.` |

`pnpm engine:measure` lee los mismos ajustes que el motor. Para probar otra pieza se usa la variable de entorno de siempre, por ejemplo `KRONOS_STT_MODEL=base` o `KRONOS_LLM_MODEL=qwen3:4b`.

A los dos totales hay que sumarles **0,8 s**: es el silencio que Kronos espera para dar la frase por terminada.

## Resultados del 14 nov. 2026

Equipo: AMD Ryzen 7 5700G (8 núcleos, 16 hilos), 48 GB de memoria, placa AMD Radeon RX 6650 XT, Windows 11. Modelo `qwen3:8b` en Ollama, corriendo entero en la placa de video. Voz `es_ES-davefx-medium`.

### Latencia

| Paso | Con whisper `small` (el actual) | Con whisper `base` |
|---|---|---|
| Transcribir una frase de 2,5 s | 2,24 s | 0,78 s |
| Modelo: primera palabra | 0,06 s | 0,06 s |
| Modelo: primera frase | 0,31 s | 0,30 s |
| Voz: primera frase | 0,09 s | 0,09 s |
| **Total hasta que empieza a hablar** | **2,64 s** | **1,18 s** |
| Total con el silencio de fin de frase | 3,44 s | 1,98 s |

### Consumo

| Qué | Con whisper `small` | Con whisper `base` |
|---|---|---|
| Memoria del motor con todo cargado | 516 MB | 365 MB |
| Procesador por cada frase transcrita | 9,1 s | 3,3 s |
| Detector de voz con el micrófono abierto | 0,4 % de un núcleo | 0,4 % de un núcleo |
| Memoria del modelo en Ollama | 5,2 GB, en la placa de video | igual |
| Velocidad del modelo | 38 tokens por segundo | igual |

## Qué dicen los números

- **La transcripción es casi toda la demora:** 2,24 s de los 2,64 s con whisper `small`. El modelo y la voz, juntos, tardan 0,4 s.
- **No se arregla con ajustes de whisper.** Con ocho hilos en lugar de cuatro baja de 2,25 s a 2,06 s y gasta el doble de procesador. Con la búsqueda más simple (`beam_size=1`) baja a 2,14 s. Whisper procesa siempre una ventana de 30 segundos, dure lo que dure la frase.
- **Un modelo de whisper más chico sí lo arregla:** con `base` la transcripción tarda un tercio. Falta comprobar cuánto peor entiende una voz real; la medición usa una voz sintética, que es fácil de transcribir.
- **El modelo local responde rápido** porque corre en la placa de video. En un equipo sin placa este paso va a ser el más lento, y hay que medirlo.
- **La palabra de activación es cara cuando hay gente hablando.** Con el micrófono en silencio el motor casi no gasta (0,4 % de un núcleo). Pero cada frase que se oye cerca se transcribe para buscar «Kronos», y cuesta 9 s de procesador con `small`. Es el argumento a favor de un detector entrenado para una sola palabra (ver "Riesgos técnicos" en [ARQUITECTURA.md](ARQUITECTURA.md)).

## Qué falta medir

- La calidad de la transcripción con voz real y cada modelo de whisper, para elegir entre `small` y `base`.
- Un equipo sin placa de video, con el modelo local en el procesador.
- Un modelo en la nube, cuando exista ese proveedor.
- Cuántas veces se activa sola la palabra de activación en un día de uso.
