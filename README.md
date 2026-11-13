# Kronos AI Assistant — Asistente de escritorio autónomo

> Nombre del proyecto: **Kronos AI Assistant** (antes "Proyecto X"). Palabra de activación: **"Kronos"**.
>
> Arquitectura técnica: [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md). Diseño de la interfaz: [docs/DISENO.md](docs/DISENO.md). Flujo de trabajo (ramas, versiones, pruebas): [CONTRIBUTING.md](CONTRIBUTING.md).

> Estado: **Fase 0 completa (v0.1.0).** Hay esqueleto, interfaz e instalador de Windows; el asistente todavía no conversa: la voz llega en la Fase 1.

## La idea

Crear un software para computadora parecido a **Siri** en el celular, pero con **mucha más autonomía**, impulsado por un LLM.

Es un **asistente general controlado por voz**: puede tener el control de la computadora y hacer lo que el usuario le pide mediante comandos de voz. El propósito principal es **superar el límite de las simples notificaciones**: en lugar de un aviso que se ignora, el asistente **toma la iniciativa, habla y conversa** con el usuario.

## Ejemplos de uso

- **Rutinas y calendario:** creo una rutina semanal (en Claude o en Google Calendar). A la hora indicada, el asistente se activa solo, me habla y puedo responderle para posponer, ajustar o pedir más contexto.
- **Comandos de voz:** "abre el navegador en tal página", "busca el archivo del informe", "silencia las notificaciones por una hora".
- **Notificaciones habladas:** si está configurado, lee en voz alta las notificaciones importantes y permite responder o actuar sobre ellas.
- **Conversación libre:** preguntar, pedir resúmenes, planificar el día, etc.

## Decisiones tomadas

### Proyecto y alcance
- **Licencia:** proyecto **open source**, con el código público en GitHub, bajo licencia **GPL v3** (elección preliminar).
  - GPL v3 **no prohíbe vender** el software, pero obliga a quien lo distribuya a publicar su código con la misma licencia. Así nadie puede hacer una versión cerrada.
  - **Modelo de negocio posible (*open core*):** el núcleo es libre y el autor puede ofrecer funciones o servicios de pago aparte, porque conserva los derechos de autor.
  - Para mantener esa libertad, quienes aporten código deberán firmar un **acuerdo de contribución (CLA)**.
- **Público de la primera versión:** uso personal del autor. Después se pule para otros usuarios.
- **Nivel de control:** un catálogo de **acciones definidas** (abrir apps, buscar archivos, volumen, recordatorios, calendario) más la **ejecución de comandos de terminal y scripts**, siempre con confirmación. El control por visión de pantalla (mouse y teclado) queda fuera por ahora.
- **Funciones del MVP**, en el orden de construcción propuesto:
  1. Conversar por voz (atajo o palabra clave → escuchar → responder hablando).
  2. Ejecutar acciones y comandos pedidos por voz.
  3. Rutinas proactivas (se activa solo por horario o evento).
  4. Leer notificaciones del sistema en voz alta.

### Modelo de lenguaje (LLM)
Hay que separar dos conceptos:
- **Proveedor:** la empresa o el servicio que da acceso a la IA (Anthropic/Claude, OpenAI/ChatGPT, Google/Gemini, Ollama en local).
- **Modelo:** la versión concreta que usa ese proveedor (p. ej. Opus, Sonnet o Haiku en Claude; distintos GPT en OpenAI; Llama o Qwen en Ollama).

**No se asume ningún proveedor.** En el primer arranque, un asistente de configuración le pide al usuario:
1. Elegir con qué se conecta: local, API key o inicio de sesión.
2. Elegir el **modelo por defecto** entre los que ofrece ese proveedor.
3. Si elige local y no tiene Ollama, la app le ofrece instalarlo y descargar un modelo. Si ya usa Claude o ChatGPT, no necesita descargar nada.

El usuario puede cambiar de proveedor o de modelo cuando quiera. Formas de conexión:

| Forma | Proveedores | Notas |
|---|---|---|
| **Local** | Ollama, llama.cpp, LM Studio | Privado, sin costo, funciona sin internet. Exige más hardware. |
| **API key** | Claude, OpenAI, Gemini, OpenRouter, etc. | Pago por uso. La clave se guarda en el almacén seguro del sistema operativo. Siempre está permitido. |
| **Inicio de sesión (suscripción)** | **ChatGPT:** existe "Sign in with ChatGPT" (presentado en oct. 2026). Permite usar la suscripción Plus/Pro en apps de terceros, pero por ahora es una preview limitada y los desarrolladores deben postularse. | **Claude:** desde feb. 2026 Anthropic **prohíbe** usar el login de Free/Pro/Max fuera de Claude.ai y Claude Code. Para Claude, solo API key. |

**Modo híbrido (varios modelos):**
- **Modelo principal:** el que se usa por defecto.
- **Modelo de respaldo (opcional, recomendado):** un modelo local liviano que entra automáticamente cuando no hay internet o el proveedor en la nube falla. El asistente de configuración lo sugiere, pero no lo impone.
- **Modelo por función:** el usuario puede asignar un modelo distinto a cada tipo de tarea. Ejemplo:

  | Función | Modelo sugerido |
  |---|---|
  | Notificaciones y eventos locales del sistema | Local liviano (no necesita internet) |
  | Rutinas y recordatorios simples | Local liviano |
  | Conversación compleja, planificación, comandos | Principal (nube o local grande) |

- **Sin internet y sin modelo local:** la voz sigue funcionando porque STT y TTS son locales. El asistente avisa hablando que no tiene conexión y ofrece configurar un modelo de respaldo.
- A verificar: qué modelos locales pequeños ejecutan acciones (*tool calling*) con suficiente fiabilidad.

> **Se empieza con API key**, que no requiere ningún trámite y funciona con cualquier proveedor. El inicio de sesión con ChatGPT se suma después, si OpenAI aprueba la solicitud: el formulario de postulación es solo para "Sign in with ChatGPT". Conviene pedirlo cuando haya un prototipo para mostrar. También hay que seguir de cerca si Anthropic u otros proveedores abren algo parecido.

### Voz
- **MVP: pipeline en cascada**
  - Detección de voz (VAD): Silero.
  - Voz a texto (STT): faster-whisper / whisper.cpp.
  - LLM: el proveedor elegido por el usuario.
  - Texto a voz (TTS): Piper / Kokoro.
  - Todas las etapas trabajan en streaming para reducir la latencia.
- **A futuro, speech-to-speech nativo:** modelos donde el audio entra y el audio sale directamente, como Moshi, Qwen2.5-Omni o GLM-4-Voice. Por ahora son más débiles ejecutando acciones (*tool calling*) y requieren más GPU. Por eso la capa de voz será un **módulo intercambiable**.

### Flujo de conversación
- Tras responder, el asistente **sigue escuchando unos segundos** para que el usuario conteste sin volver a activarlo.
- En el MVP **no se lo puede interrumpir por voz** mientras habla; sí se lo puede cortar con el atajo de teclado.
- **Errores de transcripción:** el overlay muestra lo que el asistente entendió, así el error se ve al momento. Formas de corregir:
  - Repetir la frase o decir "corrige: ...".
  - Editar el texto con el teclado en el overlay antes de enviarlo.
  - Un **vocabulario personal** (nombres propios, apps, términos técnicos) que se le pasa al reconocedor de voz para que acierte más.
  - Deletrear, como último recurso.
  - Las acciones delicadas muestran el texto exacto antes de ejecutarse, así un error de transcripción no ejecuta nada por accidente.

### Overlay
El detalle está en [docs/DISENO.md](docs/DISENO.md).

- Es una **bolita flotante**: una esfera con un anillo orbital, en violeta e índigo.
- **Aparece solo cuando hace falta:** al invocar a Kronos y cuando quiere avisar algo. Al terminar se oculta sola. El ícono de la bandeja queda siempre.
- **Posición:** abajo al centro de la pantalla, sobre la barra de tareas.
- Muestra una **animación de estado** (escucha, piensa, habla) y la **transcripción** de lo que dice el usuario y lo que responde el asistente, en una burbuja arriba de la bolita.
- Las confirmaciones aparecen con botones.

### Identidad
- **Nombre del proyecto: Kronos AI Assistant.** Es el nombre de la app y de la landing page. El repositorio se llama `kronos-assistant`.
- **Palabra de activación: "Kronos".** Al hablarle se usa solo esa palabra.
- **Personalidad: asistente profesional.** Educado, preciso y discreto, como un secretario eficiente. Esto guía la voz elegida y las instrucciones del modelo.
- **Concepto:** compañía (alguien que está con el usuario) y tiempo (rutinas, horarios, calendario).
- **Logo y colores:** esfera con anillo orbital; paleta violeta (`#7C5CFF`) e índigo (`#4F46E5`) sobre fondo oscuro. Detalle en [docs/DISENO.md](docs/DISENO.md).
- **Voz neutra respecto al género:** el asistente debe funcionar con cualquier voz, que elige el usuario.
- **Descartados:** Robin, Ari, Noa, Remi, Sami, Nilo. La búsqueda del nombre sigue abierta y no bloquea el resto de la planificación.
- **Por qué Kronos:** suena fuerte y claro como palabra de activación, igual en español e inglés, y se asocia al tiempo (rutinas, calendario). En contra: es más imponente que "compañía neutra" y el nombre ya lo usan un modelo de IA financiero (Kronos, de Tsinghua), el software de control horario UKG Kronos, el modelo Chronos de Amazon y un troyano bancario antiguo. No se encontró un asistente de voz con ese nombre.

### Notificaciones
- El asistente solo lee las notificaciones de las **apps que el usuario elija** (lista de apps permitidas).

### Calendarios
Cada calendario es un **plugin** con la misma interfaz (leer eventos, crear, modificar), así se suman de a uno. Orden propuesto:

1. **Google Calendar** (API oficial con inicio de sesión de Google).
2. **Archivo o enlace `.ics` / CalDAV:** estándar genérico que cubre iCloud y muchos otros.
3. **Outlook / Microsoft 365** (Microsoft Graph). Es el calendario de Windows.
4. **Notion** (API oficial, leyendo bases de datos con fechas).

- Se usan siempre las **APIs**, no el navegador. Abrir el navegador para "mirar" el calendario es lento y frágil, y depende del control por visión, que quedó fuera del MVP.
- Google exige verificar las apps que leen el calendario. Para uso personal se publica la app de Google en modo "producción" sin verificar, porque en modo "prueba" el acceso caduca cada 7 días. Detalle en "Verificaciones realizadas".

### Idiomas
- **Español e inglés** desde el inicio. El usuario elige el idioma, que se aplica a la voz (STT/TTS) y a la interfaz.
- Para el MVP: whisper es multilingüe, y Piper/Kokoro tienen voces en ambos idiomas.

### Activación
- **Atajo de teclado** global.
- **Palabra o frase de activación** (wake word, p. ej. con openWakeWord).
- **Activación automática** (configurable) para leer notificaciones o recordatorios en voz alta.

### Autonomía
El usuario **configura qué acciones son autónomas** y cuáles requieren su confirmación antes de ejecutarse.

- **Confirmación de acciones delicadas** (comandos de terminal, borrar archivos, enviar mensajes): el asistente dice qué va a hacer y lo muestra en pantalla. El usuario confirma **por voz ("sí") o con un clic**.
- **Comportamiento proactivo: avisar y esperar.** Cuando el asistente quiere hablar por su cuenta (rutina o notificación), muestra un aviso visual o un sonido corto y solo habla si el usuario le da permiso.

**Niveles de permiso de las acciones:**

| Nivel | Qué incluye | Qué se exige |
|---|---|---|
| 1. Normal | Abrir apps, buscar archivos, volumen, recordatorios | Nada, o lo que el usuario configure |
| 2. Delicado | Comandos de terminal, borrar archivos, enviar mensajes | Confirmación por voz o clic |
| 3. Crítico | Desactivar antivirus, firewall o protecciones; modificar el arranque o el registro; descargar y ejecutar un programa; crear usuarios, cambiar contraseñas o pedir permisos de administrador | **Clave secreta** configurada previamente |
| 4. Prohibido | Formatear o borrar discos y particiones; borrar de forma masiva carpetas del sistema o la carpeta del usuario; leer o enviar a otro lado contraseñas guardadas, claves SSH o el almacén de credenciales | No se ejecuta nunca |

**Cambiar una acción de nivel:**
- **Subirla** (hacerla más estricta): siempre permitido.
- **Bajarla entre los niveles 1 y 2:** permitido. Se puede acotar, por ejemplo "borrar sin preguntar solo en Descargas".
- **Bajar algo del nivel 3:** solo ingresando la clave secreta.
- **Nivel 4:** fijo, no se puede cambiar desde la app.

**Clave secreta del nivel crítico:**
- La **verifica el código de la app, no el modelo**. El modelo nunca conoce la clave, así un texto malicioso no puede convencerlo de saltarse el control.
- Se guarda como *hash* (p. ej. Argon2), nunca en texto plano.
- Formas de ingresarla: **escrita**, con **Windows Hello / huella / PIN del sistema**, o **dictada** (con aviso de que alguien puede oírla).
- Si se dicta, no aparece en el overlay ni queda en la transcripción, el historial o los registros.
- Tras varios intentos fallidos, el nivel crítico se bloquea por un tiempo.
- Las acciones que requieren administrador muestran además el aviso de permisos del propio sistema (UAC en Windows).

**Defensas adicionales**, porque una lista de prohibidos nunca es completa:
- El asistente **nunca corre como administrador**.
- Toda acción delicada muestra el **comando exacto** antes de confirmarse.
- Se guarda un **registro** de todo lo ejecutado.
- **Contenido no confiable:** el texto de notificaciones, correos o páginas web se trata solo como información. Nunca puede dar órdenes al asistente (protección contra *prompt injection*).

### Memoria
- **Memoria persistente:** recuerda preferencias, datos del usuario y conversaciones pasadas.
- Todo se guarda **en la computadora del usuario**, que puede ver y borrar lo que el asistente recuerda.
- **Almacenamiento:** una base de datos **SQLite** local, **cifrada** (SQLCipher). La clave del cifrado vive en el almacén seguro del sistema operativo. A verificar: que SQLCipher se empaquete bien con PyInstaller.
- **Qué se guarda:**
  - *Perfil y datos:* preferencias y cosas que el usuario pide recordar.
  - *Historial:* las conversaciones, con un resumen de cada una.
  - *Nunca:* contraseñas ni datos dictados en modo sensible.
- **Qué recibe el modelo en cada conversación:** el perfil, los últimos mensajes y solo los recuerdos relevantes al tema, no todo el historial. La búsqueda por significado (embeddings) queda para más adelante.
- **Privacidad:** si el modelo está en la nube, esos recuerdos viajan al proveedor. El usuario puede limitar qué memoria se comparte con modelos en la nube.

### Rutinas
Las rutinas proactivas se pueden crear y editar de cuatro formas, que comparten un mismo almacén:
- **Por voz:** se le pide al asistente y él crea la rutina.
- **Pantalla de la app:** lista de rutinas con horarios y edición.
- **Desde el calendario:** lee eventos (Google Calendar u otro) y actúa cuando llegan.
- **Archivo de texto:** archivo de configuración editable a mano.

### Privacidad y seguridad
- **Micrófono:** manejo explícito y obligatorio, con indicador visible cuando está escuchando.
- **Credenciales y datos personales:** se guardan en el **almacén seguro del sistema operativo** (Windows Credential Manager, macOS Keychain o Secret Service/libsecret en Linux; por ejemplo, con la librería `keyring` de Python). Nunca se guardan en texto plano ni en el historial de conversación.
- **Modo sensible:** al dictar datos privados no se guarda audio ni transcripción, y se ofrece la opción de escribir el dato en lugar de decirlo en voz alta, porque alguien cerca podría oírlo.

### Tipo de aplicación
| Tipo | Qué es | ¿Sirve? |
|---|---|---|
| App con ventana | Se abre, se usa y se cierra | ❌ No está siempre activa |
| **App de bandeja (tray)** | Corre en segundo plano desde el inicio de sesión, con un ícono junto al reloj | ✅ **Elegida** |
| Servicio del sistema | Proceso del sistema sin sesión de usuario | ❌ No puede usar el micrófono, la UI ni los atajos del usuario |

**Decisión:** una app de bandeja con **inicio automático** y un **overlay flotante** (estilo Siri). El motor (voz + LLM + scheduler) corre como proceso local en segundo plano.

### Plataformas
- **Multiplataforma:** Windows, macOS y Linux. Se empieza por Windows.
- Diferencias que hay que tener en cuenta:
  - En macOS, los atajos globales y el control del sistema requieren permisos de **Accesibilidad** y **Micrófono**.
  - En Linux, la bandeja del sistema depende del entorno de escritorio.

### Stack tecnológico
- **Motor (backend): Python.** Es el ecosistema más fuerte para IA y voz: faster-whisper, Piper/Kokoro, openWakeWord, Silero VAD, los SDKs de todos los proveedores de LLM y Ollama.
  - Rust se descarta para el motor por ahora. Es más rápido y liviano, pero tiene menos librerías de IA y voz, y desarrollar sería más lento.
- **Interfaz (bandeja + overlay): Tauri** ✅ (decidido). Comparativa que se evaluó:

| Opción | Multiplataforma | Peso | Comentario |
|---|---|---|---|
| **Tauri** (Rust + web) | ✅ Win/macOS/Linux | Liviano (~10 MB) | **Recomendada.** Ofrece bandeja, atajos globales e inicio automático. Usa Rust justo donde aporta. |
| Electron (Node + web) | ✅ Win/macOS/Linux | Pesado (~150 MB, mucha RAM) | El más maduro y fácil, pero consume demasiado para una app siempre activa. |
| .NET + **Avalonia** | ✅ Win/macOS/Linux | Medio | La opción si se prefiere C#. |
| .NET WPF / WinForms | ❌ Solo Windows | Medio | No sirve si se quiere multiplataforma. |
| .NET MAUI | ⚠️ Win/macOS (sin Linux) | Medio | Soporte de escritorio limitado. |

- **Comunicación UI ↔ motor:** el motor de Python corre como proceso local. La UI se comunica con él por WebSocket o HTTP en `localhost`.

### Empaquetado y distribución
El usuario final **no instala Python**. El motor se convierte en un ejecutable y viaja dentro del instalador de la app.

**¿Y PyPI?** No sirve para el usuario final, porque exige tener Python y saber usar `pip`. A futuro, el motor podría publicarse en PyPI solo para desarrolladores (p. ej. para crear plugins).

**Opciones para convertir el motor en ejecutable:**

| Herramienta | Cómo funciona | Pros | Contras |
|---|---|---|---|
| **PyInstaller** | Empaqueta el intérprete, el código y las librerías en una carpeta o un `.exe` | La más usada y documentada. Fácil de empezar. | Algunos antivirus la marcan como falso positivo. El modo "un solo archivo" arranca lento. |
| **Nuitka** | Compila el Python a C y luego a binario nativo | Más rápido. Menos falsos positivos. | Compila lento y la configuración es más compleja. |
| **Python embebido** (python-build-standalone + `uv`) | Incluye un Python portable y sus dependencias tal cual | Permite actualizar el motor por separado de la app. | Hay que armar el lanzador y la estructura a mano. |
| cx_Freeze / Briefcase | Alternativas parecidas a PyInstaller | — | Comunidades más chicas. |

**Decisión para el MVP:** **PyInstaller en modo carpeta (`--onedir`)**, que la app de Tauri incluye y arranca como proceso aparte (*sidecar*). Más adelante se evalúa Nuitka si hay problemas de rendimiento o con antivirus.

**Cómo queda el flujo:**
1. Se construye el motor con PyInstaller (`pnpm engine:build`) → carpeta `engine/dist/kronos-engine/`, con el ejecutable y sus librerías.
2. Tauri incluye esa carpeta completa como **recurso** del instalador, y la app arranca y detiene el motor. No se usa `externalBin`, porque ese mecanismo espera un único archivo y el modo carpeta necesita sus librerías al lado del ejecutable.
3. Tauri genera un instalador por sistema: **MSI/NSIS** (Windows), **DMG/.app** (macOS) y **AppImage/deb/rpm** (Linux).
4. Como PyInstaller no hace compilación cruzada, cada sistema se construye en su propia máquina. Se automatiza con **GitHub Actions** (una matriz Windows/macOS/Linux).
5. **Firma de código:** Authenticode en Windows y firma + notarización en macOS, para evitar las advertencias de SmartScreen y Gatekeeper.

**Mantener el instalador liviano:**
- **Los modelos no van dentro del instalador** (whisper, voces de Piper, wake word, LLM local). Se descargan en el primer arranque según el idioma y el proveedor que elija el usuario.
- **Evitar PyTorch** (pesa más de 1 GB). Se prefieren librerías basadas en ONNX / CTranslate2: faster-whisper, Piper, Silero VAD (ONNX) y openWakeWord (ONNX).
- **Actualizaciones automáticas** con el *updater* de Tauri.

**Dónde se publica:**
- Los instaladores se suben a **GitHub Releases**.
- Una **landing page** pequeña presenta la app y enlaza al instalador de cada sistema.

**Firma de código (certificados):**
Un certificado demuestra quién publicó el instalador y que nadie lo modificó. Sin firma la app funciona igual, pero el sistema muestra advertencias al instalarla.

| Sistema | Sin firma | Cómo se firma | Costo aproximado (a verificar) |
|---|---|---|---|
| Windows | SmartScreen avisa "Windows protegió su PC"; el usuario debe pulsar "Más información → Ejecutar de todas formas" | Certificado Authenticode (OV/EV) de una autoridad certificadora, Azure Trusted Signing, o SignPath Foundation si el proyecto es open source | 200–500 USD/año (OV/EV); ~10 USD/mes (Azure, con restricciones por país); gratis (SignPath, solo open source) |
| macOS | Gatekeeper bloquea la app; abrirla exige pasos manuales en Ajustes | Apple Developer Program: certificado Developer ID + notarización | 99 USD/año |
| Linux | Sin advertencias | No hace falta (firma GPG opcional) | Gratis |

- El *updater* de Tauri usa su **propia clave de firma**, gratuita, que genera el mismo Tauri. Es independiente de los certificados anteriores.
- **Plan:** las primeras versiones de prueba salen sin firma en Windows, con instrucciones para el aviso de SmartScreen. La firma se resuelve antes del lanzamiento público, según se decida si el proyecto es open source.

## Arquitectura (resumen)

El detalle está en [docs/ARQUITECTURA.md](docs/ARQUITECTURA.md).

- **Dos procesos:** la app de escritorio (Tauri + React + TypeScript) y el motor (Python), que corre como *sidecar*.
- **Comunicación:** WebSocket y HTTP en `127.0.0.1`, protegidos con un token. Nada se expone fuera de la máquina.
- **Toda la lógica vive en el motor.** La interfaz solo muestra estado y recoge respuestas.
- **Un solo repositorio** con la app, el motor, la landing page (Astro) y la documentación.
- **Piezas intercambiables:** voz, modelos, acciones, calendarios y sistema operativo se definen como interfaces con implementaciones reemplazables.
- **Permisos decididos por código:** el modelo propone una acción y el módulo de permisos decide qué se exige.
- **Construcción en 8 fases**, cada una con su prueba, empezando por el empaquetado mínimo.

## Verificaciones realizadas (11 nov. 2026)

| Tema | Resultado | Consecuencia |
|---|---|---|
| **Nombre** | No hay ningún repositorio llamado `kronos-assistant` en GitHub; solo 4 proyectos pequeños con nombres parecidos, sin estrellas. Los dominios `kronosassistant.com`, `kronos-assistant.com`, `kronosassistant.app`, `kronosassistant.dev` y `kronos-assistant.dev` no tienen registro DNS, así que probablemente están libres. | Falta confirmar los dominios en un registrador y buscar la marca. |
| **Piper (TTS)** | La versión activa (`OHF-Voice/piper1-gpl`) es **GPL v3**. La versión MIT original se archivó en oct. 2025. Cada voz tiene su propia licencia. | Compatible con la licencia GPL v3 del proyecto. Hay que revisar la licencia de cada voz elegida. Una versión cerrada de pago no podría incluir Piper. |
| **SignPath Foundation** | Gratis para open source. Exige licencia aprobada por OSI, repositorio público, autenticación en dos pasos y mencionar a SignPath. **No admite componentes cerrados** del mismo autor ni, según guías de terceros, doble licencia. | Choca con la idea de funciones de pago cerradas dentro del mismo proyecto. Ver preguntas abiertas. |
| **Azure Artifact Signing** (antes Trusted Signing) | 9,99 USD/mes. El alta de desarrolladores individuales está **pausada** y solo acepta organizaciones de ciertos países (EE. UU., Canadá; UE y Reino Unido según la documentación). | No es opción por ahora. |
| **Google Calendar** | Los permisos de calendario exigen verificar la app. En modo "prueba", el acceso **caduca cada 7 días** y hay un tope de 100 usuarios. En modo "producción" sin verificar no caduca, pero muestra una pantalla de advertencia y mantiene el tope de 100 usuarios. | Uso personal: publicar en "producción" sin verificar. Lanzamiento público: pasar la verificación de Google, o que cada usuario use sus propias credenciales, o usar el enlace `.ics` privado (solo lectura). |

**Pendientes que requieren el prototipo o una gestión:** elegir el modelo local, medir el hardware mínimo, probar SQLCipher con PyInstaller, confirmar la licencia de Kokoro, solicitar acceso a "Sign in with ChatGPT" y buscar la marca "Kronos Assistant".

## Preguntas abiertas

- **Modelo de negocio y firma (decidido por ahora):** todo el proyecto es open source y, si algún día se cobra, serán servicios (soporte, nube, sincronización). Así se mantiene la firma gratuita de SignPath y no se gasta en la fase inicial. Se revisa cuando el proyecto crezca.
- **Objetivo de peso:** la app debe ser liviana. El hardware mínimo y recomendado se define midiendo el prototipo.

- **Requisitos de hardware:** se definirán **probando el prototipo** y midiendo lo mínimo indispensable. Se espera que el usuario ya tenga cierta experiencia con IA. Los requisitos dependen mucho del modo:
  - *Con modelo en la nube:* basta con una PC común, porque solo corren en local la voz (STT/TTS) y la app.
  - *Con modelo local:* hace falta más RAM y probablemente una GPU, según el tamaño del modelo.
  - Publicar "mínimos" y "recomendados" para cada modo.
- ¿Qué modelos locales recomendar en el asistente de configuración (con buen soporte de *tool calling*)?
- Firma de código en Windows: la primera opción sigue siendo **SignPath Foundation** (gratis), si el proyecto se mantiene 100 % open source. Azure no está disponible para individuos.
- **Licencia open source:** elección preliminar **GPL v3**. Queda por confirmar si alcanza o si se prefiere una licencia que prohíba el uso comercial (ya no sería open source). Opciones evaluadas:

  | Licencia | Qué permite | Qué exige |
  |---|---|---|
  | **MIT** | Usar, modificar y vender el código, incluso en productos cerrados | Solo mantener el aviso de autoría |
  | **Apache 2.0** | Lo mismo que MIT | Además protege frente a patentes y no cede el uso del nombre o la marca |
  | **GPL v3** | Usar, modificar y vender | Quien distribuya una versión modificada debe publicar su código con la misma licencia |
  | **MPL 2.0** | Punto medio | Solo los archivos modificados deben seguir abiertos |

  Verificado: la versión activa de Piper (TTS) es GPL v3, compatible con esta elección. La licencia de Kokoro (sería Apache 2.0) falta confirmarla.
- **Disponibilidad del nombre:** el repositorio y los dominios parecen libres (ver "Verificaciones realizadas"). Falta la **búsqueda de marca** de "Kronos" y "Kronos AI Assistant" en TMview y WIPO Global Brand Database, sin urgencia: solo importa antes de publicar. Lo que se registra para un nombre es una marca, no una patente (la patente protege inventos y aquí no aplica). Nombres descartados: Orbi (marca de Netgear), Kira (ya hay asistentes de IA con ese nombre), Talos, Lumen, Robin, Ari, Noa, Remi, Sami y Nilo.
- **Modelo local liviano de respaldo:** el asistente de configuración muestra una **lista de modelos descargables** y marca los recomendados. La descarga se hace a través de **Ollama**, que es el programa que ejecuta los modelos (no es un modelo). Recomendación inicial: **1.º Qwen** y **2.º Llama**, siempre en su última versión disponible. El orden definitivo se confirma probando los candidatos con las herramientas reales del asistente. Candidatos (búsqueda de nov. 2026, a verificar en ollama.com/library):
  - *Qwen3 (4B–8B):* opción general con buen soporte de herramientas.
  - *Phi-4-mini (3.8B):* muy liviano (~3 GB), rápido en equipos de 8 GB.
  - *Llama 3.1 8B:* el más usado en tutoriales de *tool calling*.
  - *Gemma (4B):* tiene soporte de herramientas; fiabilidad por comprobar.
  - *FunctionGemma (270M):* diminuto y entrenado solo para llamar funciones; posible para notificaciones y eventos simples.
  - Referencia de memoria: ~8 GB de RAM para modelos de 3–4B y ~16 GB para modelos de 7–8B.
  - **Grok no es opción local:** los pesos publicados (Grok-1, Grok 2.5) son enormes y no corren en Ollama ni en una PC común. Grok solo serviría como proveedor en la nube por API.

## Próximos pasos

- [x] Entrevista de especificaciones.
- [x] Definir la arquitectura ([docs/ARQUITECTURA.md](docs/ARQUITECTURA.md)).

Construcción, según las fases del documento de arquitectura:

- [x] **Fase 0:** esqueleto del monorepo y prueba de empaquetado (motor "hola mundo" con PyInstaller como recurso de Tauri, con instalador para Windows). Comprobado el 12 nov. 2026: el instalador pesa 14 MB y la app instalada arranca el motor y se conecta con él.
- [ ] **Fase 1:** bucle de voz con overlay (atajo → escuchar → modelo → hablar). Medir latencia y consumo para definir el hardware mínimo.
- [ ] **Fase 2:** herramientas y niveles de permiso, con confirmación y clave secreta.
- [ ] **Fase 3:** memoria persistente cifrada.
- [ ] **Fase 4:** rutinas, "avisar y esperar" y Google Calendar.
- [ ] **Fase 5:** lectura de notificaciones de apps elegidas.
- [ ] **Fase 6:** palabra de activación "Kronos", asistente de configuración inicial y modo híbrido. Elegir los modelos locales a recomendar.
- [ ] **Fase 7:** GitHub Actions para Windows, macOS y Linux, firma y landing page.

Gestiones aparte, sin urgencia:

- [ ] Solicitar acceso a "Sign in with ChatGPT" cuando haya un prototipo.
- [ ] Búsqueda de marca de "Kronos AI Assistant".
- [ ] Renombrar la carpeta del proyecto a `kronos-assistant`.
