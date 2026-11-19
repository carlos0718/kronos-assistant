# Mediciones de Kronos AI Assistant

> Primera medición: 14 nov. 2026, sobre la versión 0.8.0; el 15 nov. se sumó Parakeet, que pasó a ser el reconocedor de fábrica (versión 0.9.0), y el 19 nov. una comparación de modelos de lenguaje locales (versión 0.19.0). Sirve para decidir el hardware mínimo y recomendado (ver "Preguntas abiertas" en el [README](../README.md)). Falta medir en un equipo más modesto y con un modelo en la nube.

## Cómo se mide

Hay dos formas, y miden lo mismo: cuánto pasa entre que el usuario termina de hablar y que Kronos empieza a responder.

| Forma | Cuándo sirve |
|---|---|
| `pnpm engine:measure` | Para comparar equipos y modelos. No usa micrófono ni altavoz: genera una pregunta con la voz de Kronos y la pasa por las piezas reales (transcribir → modelo → voz). Repite cinco veces e informa la mediana, más el consumo del motor. Necesita Ollama abierto. |
| La línea `Tiempos del turno` de la terminal | Para ver una conversación real. El motor la escribe después de cada respuesta: `Tiempos del turno: transcribir 2,24 s · modelo 0,31 s · voz 0,09 s · total 2,64 s.` |

Para comparar qué tan bien entienden los reconocedores con una voz real hay un tercer comando, `pnpm engine:compare-stt`:

1. `pnpm engine:compare-stt grabar` pide doce frases cortas («Sí.», «No.», «Sí, confirmo.», «Abrí el bloc de notas.»…) y las graba con el micrófono, con el mismo detector de voz y la misma pausa de fin de frase que Kronos. Las guarda fuera del repositorio, en `%LOCALAPPDATA%\Kronos\pruebas-voz`. Con `--tomas 2` pide cada frase dos veces.
2. `pnpm engine:compare-stt comparar` pasa las grabaciones por Parakeet v3, whisper `small` con el español fijo y Scribe v3 de ElevenLabs. Muestra qué entendió cada uno en cada frase y una tabla con aciertos y tiempo por frase. Una frase vale como acertada si coincide sin contar mayúsculas, tildes ni signos.

ElevenLabs corre en la nube y es de pago: las grabaciones salen de la computadora. Solo se usa si está la clave, en la variable `ELEVENLABS_API_KEY` o en un archivo `.env` en la raíz del proyecto (copia de `.env.example`, que no se sube al repositorio); si no está, se compara el resto. Con `--reconocedores parakeet,base` se elige qué comparar.

Para comparar modelos de lenguaje locales está `pnpm engine:compare-llm`. Le pasa a cada modelo quince pedidos escritos («¿Qué hora es?», «Abrí el blog de notas.», «Abrí la carpeta de mi portafolio.», «Escribí hola en el bloc de notas.», «Chau, gracias.»…) con las mismas instrucciones y las mismas acciones que una conversación. Las acciones no se ejecutan: el comando anota cuál pidió el modelo y le devuelve un resultado simulado, así no se abre ni se cierra nada en la pantalla. Un pedido vale como acertado si el modelo pidió la acción que corresponde con los datos correctos, o ninguna cuando no correspondía, y contestó algo. Aparte cuenta cuántas respuestas traen algo que no se puede decir en voz alta (Markdown, viñetas, emojis), y mide la primera palabra, la velocidad y cuánto ocupa el modelo en la placa de video. Repite cada pedido tres veces (`--rondas 5` para más) y con `--respuestas` muestra todo lo que contestó. De fábrica compara `qwen3:8b`, `qwen3.5:9b` y `gemma4:12b`; con `--modelos` se eligen otros. Los modelos tienen que estar descargados (`ollama pull <modelo>`); entre uno y otro saca de la memoria el anterior, para que el siguiente entre entero en la placa.

`pnpm engine:measure` lee los mismos ajustes que el motor. Para probar otra pieza se usa la variable de entorno de siempre, por ejemplo `KRONOS_STT_MODEL=small` (whisper) o `KRONOS_LLM_MODEL=qwen3:4b`.

A los dos totales hay que sumarles el silencio que Kronos espera para dar la frase por terminada: **1,5 s** de fábrica desde la v0.12.0 (antes 0,8 s y 1,2 s). Se elige en la pestaña Voz de la configuración, entre 0,5 y 5 s.

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
- **Un modelo de whisper más chico sí lo baja:** con `base` la transcripción tarda un tercio. Falta comprobar cuánto peor entiende una voz real; la medición usa una voz sintética, que es fácil de transcribir.
- **El modelo local responde rápido** porque corre en la placa de video. En un equipo sin placa este paso va a ser el más lento, y hay que medirlo.
- **La palabra de activación es cara cuando hay gente hablando.** Con el micrófono en silencio el motor casi no gasta (0,4 % de un núcleo). Pero cada frase que se oye cerca se transcribe para buscar «Kronos», y cuesta 9 s de procesador con `small`. Es el argumento a favor de un detector entrenado para una sola palabra (ver "Riesgos técnicos" en [ARQUITECTURA.md](ARQUITECTURA.md)).

## Resultados del 15 nov. 2026: otro reconocedor de voz

Como whisper `small` era casi toda la demora, se probaron dos caminos en el mismo equipo: modelos de whisper más grandes, para entender mejor, y Parakeet v3, un modelo distinto que corre con ONNX.

| Reconocedor | Transcribir una frase de 2,5 s | Procesador por frase | Memoria del motor |
|---|---|---|---|
| whisper `base` | 0,78 s | 3,3 s | 365 MB |
| whisper `small` (el de fábrica hasta la versión 0.8.0) | 2,24 s | 9,1 s | 516 MB |
| whisper `medium` | 5,00 s | 20,1 s | 1040 MB |
| whisper `large-v3-turbo` | 6,99 s | 28,0 s | 1091 MB |
| **Parakeet v3** (el de fábrica desde la versión 0.9.0) | **0,15 s** | **1,0 s** | 937 MB |

- **Parakeet transcribe unas quince veces más rápido que whisper `small`** y gasta la novena parte del procesador. Tarda según lo que dura la frase: 0,5 s para una de diez segundos.
- **Un whisper más grande no sirve en este equipo:** corre en el procesador, y `medium` ya tarda 5 s por frase.
- **Con cuatro hilos Parakeet tarda lo mismo que con todos los núcleos** y gasta la mitad de procesador; quedó en cuatro.
- **La palabra de activación gasta menos:** cada frase que se oye en reposo cuesta 1,0 s de procesador en lugar de 9,1 s.
- **Ocupa más memoria que whisper `small`:** unos 420 MB más. El modelo pesa 640 MB en disco.
- **No se probó en la placa de video.** Con 0,15 s en el procesador queda poco por ganar, y así la memoria de la placa es toda para el modelo de lenguaje.

### Qué tan bien entiende

Se compararon 32 grabaciones sintéticas: ocho frases con tres voces de Piper (España, Argentina y México) y una tanda con ruido de fondo. No reemplaza la prueba con voz real.

- **En frases completas entienden parecido.** Los dos tropiezan con las palabras raras («goblin») y aciertan las frases comunes.
- **El nombre «Kronos»:** Parakeet lo escribió bien con las tres voces; whisper `small`, con una de las tres.
- **Una palabra suelta («No.») falla en los dos:** whisper `small` no la acertó nunca y Parakeet una vez de cuatro.
- **Parakeet no deja fijar el idioma.** Lo reconoce solo, y con frases muy cortas a veces contesta en inglés: «No.» salió como «Yeah» o «North», y «Sí, dale, seguí» como «See, that's it». Es su riesgo principal para una conversación con respuestas de una palabra.

### Con voz real

El 16 nov. se usó Parakeet en una conversación de tres minutos con micrófono, en el mismo equipo. Trece turnos, según la línea `Tiempos del turno`:

| Paso | Mediana | Mínimo | Máximo |
|---|---|---|---|
| Transcribir | 0,16 s | 0,08 s | 0,32 s |
| Modelo: primera frase | 0,67 s | 0,26 s | 2,51 s |
| Voz: primera frase | 0,05 s | 0,04 s | 0,51 s |
| **Total hasta que empieza a hablar** | **0,95 s** | 0,47 s | 2,80 s |

- **Quien lo usó lo encontró más fluido y con menos errores que whisper `small`.** Por eso Parakeet pasó a ser el reconocedor de fábrica; whisper sigue disponible con `KRONOS_STT_MODEL=small`.
- **Ahora el paso más lento es el modelo de lenguaje**, no la transcripción.
- **Se perdieron algunas frases, pocas.** El motor no registró ninguna como «se oyó algo que no se entendió»: las frases perdidas no llegaron al reconocedor. Hay que mirar el detector de voz y el momento en que se vuelve a abrir el micrófono.
- **Las respuestas de una o dos palabras se transcribieron** (hubo turnos de 2 y de 7 caracteres). No se contó cuántas salieron bien.

Ese día Ollama respondió más lento que el 14 nov. (entre 10 y 20 tokens por segundo en lugar de 38), sin que se buscara la causa: los tiempos del modelo de lenguaje de las dos fechas no son comparables.

## Resultados del 16 nov. 2026: turnos con acciones

Desde la v0.10.0 el modelo puede pedir una acción (decir la hora, abrir una aplicación). Ese turno le pregunta dos veces al modelo: una para que elija la acción y otra para que cuente el resultado. Se midió solo el paso del modelo, con el texto escrito y sin voz, en el mismo equipo y con `qwen3:8b`:

| Turno | Cuántos | Primera palabra (mediana) | Mínimo | Máximo |
|---|---|---|---|---|
| Sin acción | 7 | 0,33 s | 0,19 s | 1,20 s |
| Con una acción | 11 | 1,83 s | 0,92 s | 2,71 s |

- **Un turno con acción tarda cerca de un segundo y medio más** en empezar a contestar. Casi todo es la segunda pregunta al modelo; ejecutar la acción no se nota.
- **Listar las aplicaciones de Windows tarda 1,1 s.** Por eso la lista se arma al arrancar y se guarda cinco minutos.

## Prueba con micrófono del 16 nov. 2026: acciones y confirmación

Siete minutos y 24 turnos con la v0.11.0, en el mismo equipo. Lo que se vio:

- **«Bloc de notas» se transcribió «blog de notas»** y no se encontró la aplicación. Desde la v0.11.1 se tolera una letra cambiada en una palabra de cuatro.
- **Un «sí» suelto se transcribió «C».** En tres de seis confirmaciones hubo al menos una respuesta que no se entendió; «sí, confirmo» se entendió siempre. Desde la v0.11.1 la pregunta pide esa respuesta, «c» vale como sí y Kronos avisa cuando no entendió.
- **Kronos cortó al usuario en una pausa.** El silencio que da por terminada la frase pasó de 0,8 s a 1,2 s, lo que suma 0,4 s a cada turno.
- **Transcribir siguió rápido** (0,09 a 0,32 s), pero el modelo tardó entre 1 y 10 s en la primera frase, sin que se buscara la causa.

En una segunda prueba ese mismo día, con la v0.11.1 (16 turnos), 1,2 s ya no cortó al usuario, que igual pidió una pausa más larga y poder elegirla. Desde la v0.12.0 es de 1,5 s de fábrica y se cambia en la pestaña Voz, sin reiniciar. La variable `KRONOS_END_SILENCE_MS` dejó de existir.

En esa prueba un turno quedó sin respuesta: pasaron 29 s entre la frase y la siguiente, y el usuario vio a Kronos «pensando». No se supo si el modelo no llegó a contestar o si contestó vacío, porque el registro no anotaba ninguno de los dos casos. Desde la v0.12.0 anota los dos: `Conversación cortada a los 29,0 s de estar esperando al modelo.` y `El modelo terminó sin decir nada.`

Para ver qué texto se oyó en una prueba así, el motor se arranca con `KRONOS_DEBUG=1`. De fábrica solo se anota cuántos caracteres.

## Prueba con micrófono del 17 nov. 2026: ElevenLabs

Con la v0.13.0 se probó Scribe v3 de ElevenLabs como reconocedor de todo el motor (conversación y palabra de activación), con `KRONOS_STT_MODEL=elevenlabs`. Fueron cuatro minutos y 13 turnos en el mismo equipo, según la línea `Tiempos del turno`:

| Paso | Mediana | Mínimo | Máximo |
|---|---|---|---|
| Transcribir (ElevenLabs) | 1,21 s | 0,92 s | 1,94 s |
| Modelo: primera frase | 4,87 s | 0,79 s | 7,79 s |
| Voz: primera frase | 0,13 s | 0,06 s | 0,22 s |
| **Total hasta que empieza a hablar** | **6,31 s** | 2,49 s | 8,87 s |

- **Quien lo usó dijo que le entendió todo.** Hubo acciones de abrir y cerrar aplicaciones, traer al frente una ya abierta y decir la hora; la confirmación por voz salió al primer intento.
- **Transcribir tarda unas ocho veces más que con Parakeet** (1,21 s contra 0,16 s): es el viaje a la nube con la frase entera. El modelo de tiempo real de ElevenLabs (`scribe_v3_live`) transcribe mientras se habla y debería bajarlo; no se probó.
- **Ese día el modelo de lenguaje fue el paso más lento** (4,87 s de mediana), como en otras pruebas: no es comparable con el 14 nov.
- Antes, con las doce frases cortas de `pnpm engine:compare-stt` dichas por una voz sintética de Piper, ElevenLabs acertó 5 y Parakeet 3. Los dos fallaron «Kronos» y «bloc de notas» con esa voz.

## Resultados del 18 nov. 2026: elegir una carpeta por el significado

Con la v0.17.0, cuando `open_folder` no encuentra la carpeta por las palabras, le pregunta al modelo (`qwen3:8b`, sin razonamiento) cuál de hasta 80 carpetas permitidas es la pedida, en una pregunta aparte. Se probó con las carpetas reales del equipo del usuario y ocho pedidos con respuesta conocida, sin abrir nada:

| Forma de preguntar | Aciertos | Tiempo por pregunta |
|---|---|---|
| Pedido arriba, lista abajo | 3 de 8 | — |
| **Lista arriba, pedido al final (la elegida)** | **7 de 8** | **0,2 s** |
| Lista arriba, con razonamiento (`think`) | 8 de 8 | 18 s de promedio |

- Los aciertos fueron, por ejemplo, «portafolio de diseño web» → `Portfolio-master`, «la app de préstamos» → `app-movile-prestar`, «mis apuntes de inglés» → `english space`. En «tesis» y «facturas de luz», que no existen, no eligió ninguna. El que no acertó («las recetas») tampoco abrió nada.
- **Con 100 opciones la pregunta pasó de 0,2 s a unos 5 s**; con 80, no. Por eso el tope es 80.
- **Pasarle la lista al modelo de la conversación no sirvió**: la leía en voz alta y no elegía. Por eso va en una pregunta aparte.
- «La carpeta de la aplicación de préstamos» a veces va a abrir aplicaciones en vez de carpetas; con «app» o «proyecto» va bien.
- Los tiempos cambian mucho según lo que haga el equipo: en una corrida la misma pregunta tardó 3,2 s.

## Resultados del 19 nov. 2026: tres modelos locales

Con la v0.19.0 y `pnpm engine:compare-llm` (quince pedidos, tres rondas) se compararon `qwen3:8b` (el de fábrica), `qwen3.5:9b` y `gemma4:12b`, los tres en Ollama 0.40.16, cuantizados a 4 bits (`Q4_K_M`) y sin razonamiento previo. Mismo equipo, sin juegos ni otros programas pesados abiertos.

| Modelo | Aciertos | Primera palabra sin acción | Primera palabra con acción | Turno más lento | Velocidad | Memoria de video |
|---|---|---|---|---|---|---|
| **`qwen3:8b`** | 38 de 45 | **0,33 s** | **1,36 s** | 8,7 s | **40 tokens/s** | 5,2 GB, entra entero |
| `qwen3.5:9b` | 16 de 45 | 1,26 s | 1,25 s | 3,2 s | 38 tokens/s | entra entero |
| `gemma4:12b` | **42 de 45** | 3,64 s | 17,74 s | más de 60 s | 6 tokens/s | no entra: 5,3 GB en la placa y 2,5 GB en la memoria compartida |

Las 45 respuestas de los tres se pueden decir en voz alta: ninguna trajo Markdown, viñetas ni emojis.

| Pedido | `qwen3:8b` | `qwen3.5:9b` | `gemma4:12b` |
|---|---|---|---|
| ¿Qué hora es? | 3 de 3 | 0 de 3 | 2 de 3 |
| ¿Qué día es mañana? | 0 de 3 | 0 de 3 | 2 de 3 |
| What time is it? | 3 de 3 | 0 de 3 | 3 de 3 |
| Abrí el bloc de notas. / Abrí el blog de notas. / Abrí Spotify. | 9 de 9 | 0 de 9 | 9 de 9 |
| Cerrá el bloc de notas. | 3 de 3 | 1 de 3 | 3 de 3 |
| Abrí la carpeta Documentos. / Abrí la carpeta de mi portafolio. | 6 de 6 | 0 de 6 | 6 de 6 |
| Abrí la carpeta de la aplicación de préstamos. | 2 de 3 | 0 de 3 | 3 de 3 |
| ¿Cuál es la capital de Francia? | 3 de 3 | 3 de 3 | 2 de 3 |
| Explicame qué es un agujero negro. | 0 de 3 | 3 de 3 | 3 de 3 |
| Escribí hola… / ¿Qué temperatura hace hoy? / Chau, gracias. | 9 de 9 | 9 de 9 | 9 de 9 |

- **`qwen3:8b` sigue siendo el que conviene en esta placa.** Es el más rápido y acierta casi todas las acciones. Falla en dos cosas: dice que mañana es «jueves 19», el mismo día que le dio el reloj, y **se niega a explicar qué es un agujero negro** («no tengo acceso a información externa»). Lo segundo viene de las instrucciones: la regla de decir que no puede consultar internet la aplica también a lo que sabe de memoria. Hay que corregir esa regla, sea cual sea el modelo.
- **`qwen3.5:9b` casi nunca pide las acciones**, y después dice que las hizo («He cerrado el Bloc de notas»). Se probó aparte: sin instrucciones de sistema sí las pide, pero con cualquiera, aunque sea «Sos un asistente.», deja de pedirlas o lo hace al azar. Como Kronos siempre manda instrucciones, hoy no sirve. Puede ser un problema de cómo Ollama 0.40.16 arma la conversación para este modelo; no se buscó más.
- **`gemma4:12b` es el que mejor contesta, pero no entra en 8 GB.** Acierta las carpetas que `qwen3:8b` confunde con aplicaciones, entiende «mañana» y escribe la hora como se dice («las tres y cuarenta y dos»), como piden las instrucciones. Pero Windows pone 2,5 GB del modelo en la memoria común, que la placa lee mucho más despacio: va a 6 tokens/s y tarda 18 s en empezar a contestar un pedido con acción. Dos turnos pasaron los 60 s, los dos en la primera ronda. Con una placa de 12 GB o más debería andar rápido, pero no se probó.
- **Ollama informa mal la memoria de `gemma4:12b`**: `ollama ps` dice «1,0 GB, 100 % GPU». Lo que ocupa de verdad se vio con los contadores de Windows (`\GPU Adapter Memory(*)\Dedicated Usage` y `Shared Usage`), antes y después de cargarlo.
- **Desde la v0.19.1 las instrucciones separan las dos cosas**: lo que sabe (ciencia, historia, definiciones) lo contesta sin internet; lo que cambia y ninguna acción le da (clima, noticias, precios) dice que todavía no puede. Con eso `qwen3:8b` pasó de 38 a **42 de 45**: explicó el agujero negro las tres veces, siguió diciendo que no puede ver la temperatura y no rompió ninguna acción. Lo único que sigue fallando es «¿Qué día es mañana?».
- **Desde la v0.19.2 la acción de la hora trae la fecha de mañana ya calculada** («Hora: 15:42. Hoy: jueves 19… Mañana: viernes 20… Decí solo lo que te preguntaron.»): «¿Qué día es mañana?» pasó de 0 a 3 de 3 y `qwen3:8b` quedó en 44 de 45. Sin el «decí solo lo que te preguntaron», leía la fecha de mañana cada vez que le pedían la hora; con eso dejó de hacerlo en español, y en inglés todavía lo hace una de cada tres veces. A «What time is it?» contesta en español: pasaba también antes.
- **Con la v0.22.0 se sumó abrir archivos** (`open_file`) y tres pedidos al comparador («Abrí el archivo del presupuesto.», «Abrí el PDF del informe de ventas.», «Abrí mi currículum.»): `qwen3:8b` los mandó a `open_file` las nueve veces y quedó en 53 de 54. El único fallo fue «Abrí el blog de notas.», que una de tres veces fue a abrir una carpeta.
- En la primera corrida, con el mismo resultado de fondo, `gemma4:12b` acertó 43 y `qwen3:8b` 41, porque todavía no se exigía que la explicación del agujero negro hablara de la gravedad.

## Qué falta medir

- Un turno con acción de punta a punta, con voz real.
- Cuántas respuestas cortas («sí», «no») pasa Parakeet a otro idioma con voz real. `pnpm engine:compare-stt` lo mide con grabaciones del usuario; falta correrlo.
- Por qué se pierden algunas frases antes de llegar al reconocedor.
- Un equipo sin placa de video, con el modelo local en el procesador.
- Un modelo en la nube, cuando exista ese proveedor. `pnpm engine:compare-llm` debería poder compararlo con los locales.
- `gemma4:12b` en una placa de video de 12 GB o más.
- Cuántas veces se activa sola la palabra de activación en un día de uso.
