# Diseño de la interfaz de Kronos AI Assistant

> Decisiones tomadas el 12 nov. 2026. La arquitectura técnica está en [ARQUITECTURA.md](ARQUITECTURA.md) y las decisiones funcionales en el [README](../README.md).

## 1. Las tres piezas

| Pieza | Qué es | Cuándo se ve |
|---|---|---|
| **Ícono de bandeja** | La presencia permanente de Kronos, junto al reloj | Siempre |
| **Overlay** (la bolita) | Ventana transparente, sin bordes y siempre encima | Solo cuando hace falta |
| **Ventana de configuración** | Ventana normal | Cuando el usuario la abre |

### Ícono de bandeja
- **Clic izquierdo:** invoca a Kronos (igual que el atajo).
- **Clic derecho:** menú con "Hablar con Kronos", "Configuración" y "Salir".
- "Salir" es la única forma de cerrar la app. Cerrar la ventana de configuración solo la oculta.

### Overlay
- Aparece **abajo al centro** de la pantalla, sobre la barra de tareas, en el monitor donde está el cursor.
- La **transcripción** se muestra en una burbuja arriba de la bolita: primero lo que dijo el usuario y después la respuesta.
- **No roba el foco:** el usuario sigue escribiendo en la ventana en la que estaba.

### Ventana de configuración
- Se abre desde la bandeja.
- **Barra de título propia** (sin el marco de Windows): logo, nombre, y botones de minimizar y cerrar. Cerrar solo la oculta.
- **Izquierda, el escenario:** la bolita grande con su estado, el indicador del motor, un medidor vertical y el botón de micrófono para invocar a Kronos.
- **Derecha, el panel:** pestañas con las opciones definidas en el README. Cada opción es una fila con el nombre y una explicación a la izquierda y el control a la derecha.

  | Pestaña | Opciones |
  |---|---|
  | General | Probar a Kronos, idioma, atajo, palabra de activación, activación automática |
  | Modelo | Forma de conexión, proveedor, modelo principal, modelo de respaldo, modelo por función |
  | Voz | Voz, segundos de escucha tras responder, vocabulario personal |
  | Permisos | Los cuatro niveles y la clave secreta |
  | Rutinas | Rutinas, calendarios, apps con notificaciones permitidas |
  | Memoria | Perfil, historial, compartir con la nube, modo sensible |

- Por ahora las opciones son una vista previa: no se guardan ni llegan al motor, y el medidor refleja el estado, no el audio real. Cada fase conecta las suyas.

## 2. Cuándo aparece y cuándo se oculta la bolita

| Situación | Qué pasa |
|---|---|
| El usuario la invoca (atajo `Ctrl+Shift+K`, clic en la bandeja o, desde la Fase 6, la palabra "Kronos") | Aparece y empieza a escuchar |
| El usuario la invoca mientras Kronos escucha, piensa o habla | Corta lo que esté haciendo |
| Kronos vuelve a inactivo | Se oculta sola a los 2,5 segundos |
| El motor no responde | Muestra el error y se oculta a los 5 segundos |
| Aviso proactivo: rutina o notificación (Fase 4) | Aparece la bolita chica con un latido y un sonido corto, y **espera permiso** antes de hablar |

## 3. La bolita

Una **esfera con un anillo orbital** inclinado. El anillo alude a una órbita y a la aguja de un reloj: el tiempo, por Kronos. Un tramo brillante recorre el anillo y pasa por detrás de la esfera.

| Estado | Esfera | Anillo |
|---|---|---|
| Inactivo | Quieta, brillo bajo | Gira lento (una vuelta cada 9 s) |
| Escuchando | Late suave | Se ensancha, pulsa y gira más rápido |
| Pensando | Brillo medio | Gira rápido (una vuelta por segundo) |
| Hablando | Pulsa con ritmo irregular, como una voz | Gira lento |
| Sin motor | Gris | Detenido |

- **Movimiento reducido:** si el sistema lo pide (`prefers-reduced-motion`), no hay animaciones y el estado se distingue por el brillo y por la etiqueta de texto.
- La etiqueta de texto bajo la bolita ("Escuchando", "Pensando"…) hace que el estado nunca dependa solo del color o del movimiento.

## 4. Identidad visual

- **Logo:** la misma esfera con anillo, en versión estática y con trazos más gruesos para que se lea a 16 px. El archivo fuente es `apps/desktop/src-tauri/icons/kronos.svg`; de ahí salen el ícono de la app, el de la bandeja y el del instalador.
- **Tema:** oscuro.
- **Tipografía:** la del sistema (Segoe UI en Windows).

| Uso | Color |
|---|---|
| Violeta (principal) | `#7C5CFF` |
| Índigo (secundario) | `#4F46E5` |
| Acento claro | `#C4B5FD` |
| Fondo | `#0F0E17` |
| Superficie (tarjetas) | `#1A1826` |
| Superficie elevada (botones, íconos) | `#262338` |
| Correcto / conectado | `#4ADE80` |
| Advertencia | `#FBBF24` |
| Texto | `#F2F1F8` |
| Texto secundario | `#A5A1B8` |
| Error | `#F87171` |

Los colores viven como variables en `apps/desktop/src/theme.css`.

## 5. Pendientes de diseño

- Tamaño y comportamiento de la bolita en el aviso proactivo (Fase 4).
- Botones de confirmación de acciones dentro del overlay (Fase 2).
- Edición de la transcripción con el teclado: hoy el overlay no toma el foco; habrá que dárselo solo cuando el usuario quiera corregir (Fase 1).
- Tema claro, si se decide ofrecerlo.
- Atajo configurable desde la ventana de configuración.
