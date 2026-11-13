# Arquitectura de Kronos AI Assistant

> Estado: **Fase 0 implementada.** Este documento define cómo se organiza el proyecto. Las decisiones funcionales están en el [README](../README.md).

## 1. Dos procesos

```
┌──────────────────────────────┐   WebSocket + HTTP    ┌───────────────────────────────┐
│  App de escritorio (Tauri)   │   en 127.0.0.1        │  Motor (Python, sidecar)      │
│                              │◄─────────────────────►│                               │
│  · Bandeja del sistema       │   con token           │  · Audio y voz                │
│  · Overlay (React)           │                       │  · LLM y agente               │
│  · Configuración (React)     │                       │  · Herramientas y permisos    │
│  · Atajo global              │                       │  · Memoria                    │
│  · Inicio automático         │   arranca y detiene   │  · Rutinas y notificaciones   │
│  · Actualizaciones           │──────────────────────►│                               │
└──────────────────────────────┘                       └───────────────────────────────┘
```

| Proceso | Tecnología | Responsabilidad |
|---|---|---|
| **App de escritorio** | Tauri 2 (Rust) + React + TypeScript + Vite | Bandeja, overlay, pantalla de configuración, atajo global, inicio automático, actualizaciones, arrancar y detener el motor |
| **Motor** (sidecar) | Python 3.12 | Audio, voz, LLM, agente, herramientas, permisos, memoria, rutinas, notificaciones |

**Regla de diseño:** toda la lógica vive en el motor. La interfaz solo muestra estado y recoge respuestas del usuario.

### Por qué React
- Se evaluaron **Svelte** y **SolidJS**, que generan una interfaz algo más liviana. La diferencia es marginal: la interfaz es pequeña, el trabajo pesado está en el motor y la memoria la consume la ventana web de Tauri, no el framework.
- React gana porque el autor ya lo conoce y por su ecosistema de componentes.
- Como la interfaz no tiene lógica de negocio, cambiar de framework más adelante sería barato.
- **Astro** se descarta para la app, porque está pensado para sitios de contenido. Sí se usa para la **landing page** (`apps/landing/`).

## 2. Comunicación entre procesos

1. Tauri lanza el motor y le pasa un **token aleatorio**.
2. El motor elige un puerto libre en `127.0.0.1` y lo informa por la salida estándar.
3. La interfaz se conecta por **WebSocket** con ese token. Nada se expone fuera de la máquina.

Los mensajes son JSON, tipados y con número de versión del protocolo.

| Dirección | Mensaje | Para qué |
|---|---|---|
| Motor → interfaz | `state_changed` | Estado actual: inactivo, escuchando, pensando, hablando |
| Motor → interfaz | `transcript_partial` / `transcript_final` | Lo que el motor entendió de la voz del usuario |
| Motor → interfaz | `assistant_delta` | Texto de la respuesta, a medida que se genera |
| Motor → interfaz | `confirmation_request` | Pedir confirmación de una acción de nivel 2 |
| Motor → interfaz | `secret_request` | Pedir la clave secreta para una acción de nivel 3 |
| Motor → interfaz | `proactive_notice` | Avisar que el asistente quiere hablar (rutina o notificación) |
| Motor → interfaz | `error` | Informar un fallo |
| Interfaz → motor | `activate` / `cancel` | Empezar a escuchar o cortar lo que esté haciendo |
| Interfaz → motor | `confirm` / `deny` | Responder a una confirmación |
| Interfaz → motor | `submit_secret` | Enviar la clave secreta |
| Interfaz → motor | `text_input` | Enviar texto escrito o una transcripción corregida |
| Interfaz → motor | `allow_proactive` | Dar permiso para que el asistente hable |

La **configuración** (proveedores, rutinas, permisos, memoria) se lee y se escribe por HTTP en el mismo servidor local, con el mismo token.

## 3. Estructura del repositorio

Un solo repositorio (monorepo) con las dos partes, la landing y la documentación.

```
kronos-assistant/
├─ apps/
│  ├─ desktop/               # App de escritorio (Tauri)
│  │  ├─ src/                # React
│  │  │  ├─ engine/          # Conexión con el motor y protocolo
│  │  │  ├─ shared/          # Componentes que usa más de una ventana
│  │  │  ├─ overlay/         # Ventana del overlay
│  │  │  └─ settings/        # Ventana de configuración
│  │  └─ src-tauri/          # Rust: bandeja, atajo, sidecar, autostart, updater
│  └─ landing/               # Landing page (Astro)
├─ engine/                   # Motor (Python, con uv + pyproject)
│  ├─ src/kronos_engine/
│  │  ├─ api/                # Servidor local (FastAPI + WebSocket)
│  │  ├─ core/               # Orquestador, protocolo e interfaces
│  │  ├─ voice/              # VAD, STT, TTS, wake word, entrada y salida de audio
│  │  ├─ llm/                # Proveedores y enrutador (por función y respaldo)
│  │  ├─ agent/              # Bucle del agente y armado de instrucciones
│  │  ├─ tools/              # Plugins de acciones: apps, archivos, sistema, terminal, calendario
│  │  ├─ permissions/        # Niveles 1–4, confirmaciones, clave secreta, registro
│  │  ├─ triggers/           # Rutinas (scheduler), calendario, notificaciones
│  │  ├─ memory/             # SQLite cifrada: perfil, historial, resúmenes
│  │  ├─ config/             # Ajustes (TOML) y secretos (keyring)
│  │  ├─ platform/           # Adaptadores por sistema: windows/, macos/, linux/
│  │  └─ pipeline.py         # Arma las piezas con las que arranca el motor
│  └─ tests/
├─ docs/                     # ARQUITECTURA.md, DISENO.md, CODIGO.md
├─ scripts/                  # Versión y tamaño de los archivos
└─ .github/workflows/        # Chequeos de cada pull request
```

Hoy existen `api/`, `core/` y `voice/`; los demás paquetes del motor llegan con su fase. Qué puede importar cada uno está en [CODIGO.md](CODIGO.md#2-capas-del-motor).

## 4. Piezas intercambiables

Cada pieza se define como una interfaz con implementaciones reemplazables. Así se puede cambiar una tecnología sin tocar el resto.

| Pieza | Interfaz | Implementación inicial | Qué permite cambiar |
|---|---|---|---|
| Detección de voz | `VAD` | Silero (ONNX) | Otro detector |
| Voz a texto | `STT` | faster-whisper | whisper.cpp u otro |
| Texto a voz | `TTS` | Piper / Kokoro | Otras voces o motores |
| Palabra de activación | `WakeWord` | openWakeWord | Otro detector |
| Modelo de lenguaje | `LLMProvider` | Ollama, Anthropic, OpenAI | Gemini, OpenRouter, "Sign in with ChatGPT" |
| Acciones | `Tool` | Apps, archivos, sistema, terminal | Nuevos plugins |
| Calendario | `CalendarProvider` | Google Calendar | `.ics`/CalDAV, Outlook, Notion |
| Sistema operativo | `Platform` | Windows | macOS, Linux |

- **`LLMProvider`** ofrece respuesta en streaming y llamadas a herramientas.
- **Enrutador de modelos:** elige el modelo según la función (conversación, acciones, notificaciones, rutinas) y cae al modelo de respaldo si no hay conexión.
- **`Tool`:** cada plugin declara su nombre, sus parámetros, su **nivel de permiso** por defecto y la función que ejecuta.
- **Speech-to-speech:** como `STT`, `LLMProvider` y `TTS` están separados del orquestador, más adelante se puede sumar un modelo que haga las tres cosas juntas.

## 5. Flujo de una conversación

```
Disparador ──► Capturar audio ──► VAD ──► STT ──► Agente + LLM ──► TTS ──► Altavoz
(atajo, wake                      (fin de  (texto   (streaming,      (frase
 word, rutina)                     frase)   en el    herramientas,    por
                                            overlay) memoria)         frase)
                                                          │
                                                          ▼
                                              Escucha unos segundos más
                                              y, si no hay respuesta, vuelve a inactivo
```

1. **Disparador:** el atajo lo detecta Tauri; la palabra de activación y las rutinas, el motor.
2. **Escucha:** el motor captura audio, el VAD detecta el fin de la frase y el STT transcribe. El overlay muestra el texto.
3. **Razonamiento:** el agente llama al modelo en streaming, con las herramientas disponibles y los recuerdos relevantes.
4. **Habla:** la respuesta se corta por frases y pasa al TTS mientras se genera, para bajar la latencia.
5. **Seguimiento:** al terminar, el motor escucha unos segundos por si el usuario sigue. Si no, vuelve a inactivo.

En el MVP no se puede interrumpir al asistente por voz; el atajo envía `cancel` y lo corta.

## 6. Flujo de permisos

El modelo **propone** una acción. El módulo `permissions`, que es código y no modelo, **decide** qué se exige.

```
Acción propuesta ──► Clasificar nivel ──┬─ Nivel 1 ──► Ejecutar
                                        ├─ Nivel 2 ──► Confirmación (voz o clic) ──► Ejecutar
                                        ├─ Nivel 3 ──► Clave secreta ──────────────► Ejecutar
                                        └─ Nivel 4 ──► Rechazar
```

- **Comandos de terminal:** pasan por un clasificador de reglas que los sube a nivel 3 o 4 según el patrón.
- **Clave secreta:** se verifica con Argon2 y se bloquea tras varios intentos fallidos. El modelo nunca la ve.
- **Contenido no confiable:** el texto de notificaciones, correos o páginas web se marca como dato. Toda acción pedida en un turno que lo incluya exige, como mínimo, confirmación.
- **Auditoría:** cada acción ejecutada o rechazada queda en un registro local.
- **Privilegios:** el motor nunca corre como administrador.

## 7. Datos en disco

| Qué | Dónde | Formato |
|---|---|---|
| Ajustes | Carpeta de la app en el perfil del usuario | `config.toml` |
| Rutinas | Misma carpeta | `routines.toml`, editable a mano |
| Memoria | Misma carpeta | `kronos.db` (SQLite cifrada con SQLCipher) |
| Registros | Misma carpeta | `logs/` |
| Modelos de voz y wake word | Carpeta de caché | Se descargan en el primer arranque |
| Secretos (API keys, clave de la base de datos) | Almacén seguro del sistema operativo | Mediante `keyring` |

## 8. Fases de construcción

| Fase | Qué se construye | Cómo se verifica |
|---|---|---|
| 0 | Esqueleto del monorepo y prueba de empaquetado: motor "hola mundo" como sidecar | El instalador de Windows instala la app y la interfaz recibe un mensaje del motor |
| 1 | Bucle de voz: atajo → escuchar → modelo → hablar, con overlay | Conversación hablada de ida y vuelta, en español e inglés |
| 2 | Herramientas y niveles de permiso, con confirmación y clave secreta | Una acción de cada nivel se comporta como define el README |
| 3 | Memoria persistente cifrada | El asistente recuerda un dato entre dos sesiones; se puede ver y borrar |
| 4 | Rutinas, "avisar y esperar" y Google Calendar | Una rutina programada avisa a la hora y habla al dar permiso |
| 5 | Lectura de notificaciones de apps elegidas | Una notificación de una app permitida se lee en voz alta |
| 6 | Palabra de activación "Kronos", asistente de configuración inicial, modo híbrido | Se activa por voz; sin internet cae al modelo local |
| 7 | CI para los tres sistemas, firma, landing page | Instaladores publicados en GitHub Releases |

## 9. Riesgos técnicos a comprobar pronto

| Riesgo | Por qué importa | Cuándo se comprueba |
|---|---|---|
| **Notificaciones de Windows** | La API para leerlas puede exigir que la app esté empaquetada con identidad (MSIX) | Antes de la fase 5 |
| **SQLCipher + PyInstaller** | La base de datos cifrada debe empaquetarse bien en el ejecutable | Fase 0 o 3 |
| **Peso del instalador** | Las librerías de voz pueden engordarlo; el objetivo es una app liviana, sin PyTorch | Fase 1 |
| **Palabra de activación propia** | "Kronos" requiere entrenar un modelo de openWakeWord para español e inglés | Fase 6 |
| **Latencia del bucle de voz** | Si la respuesta tarda, la conversación deja de sentirse natural | Fase 1, con modelo en la nube y con modelo local |
