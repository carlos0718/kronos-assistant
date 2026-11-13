# Cómo se escribe el código de Kronos AI Assistant

> Decisiones tomadas el 13 nov. 2026. Qué partes tiene el proyecto está en [ARQUITECTURA.md](ARQUITECTURA.md); cómo se trabaja (ramas, versiones, pruebas), en [CONTRIBUTING.md](../CONTRIBUTING.md). Este documento fija cómo se escribe el código dentro de cada parte.

Casi todas las reglas las verifica un comando (ver [Chequeos](#8-chequeos)). Las que no, se revisan en cada pull request.

## 1. Tamaño

| Qué | Objetivo | Tope |
|---|---|---|
| Archivo de código | Unas 150 líneas | **300 líneas** (falla el CI) |
| Función | Unas 40 líneas | Complejidad 10 en Python (falla el CI) |

- **El objetivo es una señal, no una regla.** Un archivo que lo pasa suele estar haciendo dos cosas: conviene mirar si se puede partir por responsabilidad. Si se lee mejor entero, se deja.
- **El tope sí es una regla.** Si un archivo llega a 300 líneas, se parte antes de mergear.
- **Fuera del tope:** tests, CSS, documentación y código generado.
- **No se parte para cumplir el número.** Dos archivos que solo se entienden juntos son peores que uno largo.

## 2. Capas del motor

Cada paquete del motor solo importa de los que tiene debajo:

```
__main__.py          arranca el proceso
    │
pipeline.py          arma las piezas concretas
    │
api/   voice/ …      el servidor  ·  las implementaciones (voz, modelo, herramientas…)
    │
core/                el orquestador, el protocolo y las interfaces
```

| Paquete | Qué contiene | Puede importar |
|---|---|---|
| `core/` | Orquestador, protocolo e interfaces (`Protocol`) | Nada más del motor |
| `voice/`, `llm/`, `tools/`, `memory/`… | Implementaciones de las interfaces | `core/`. Nunca entre sí ni a `api/` |
| `api/` | Servidor local: rutas y estado compartido | `core/`. No conoce implementaciones |
| `pipeline.py` | Elige qué implementación va en cada lugar | Todo |
| `__main__.py` | Token, puerto y arranque del servidor | Todo |

- **`core/` depende de interfaces, no de tecnologías.** El orquestador recibe un `Listener`, un `Responder` y un `Speaker`; no sabe si detrás hay whisper u otra cosa. Cambiar una tecnología no toca `core/`.
- **Cada paquete nuevo se agrega a la lista de capas** en `engine/pyproject.toml` (`[tool.importlinter]`), al mismo nivel que `voice/`.
- **Las librerías pesadas se importan dentro de la función que las usa**, con un comentario que lo explique. Así no demoran el arranque ni se cargan en el modo demo.

## 3. Interfaz (React)

```
apps/desktop/src/
├─ engine/      conexión con el motor: useEngine y el protocolo
├─ shared/      componentes que usa más de una ventana (la bolita)
├─ overlay/     la ventana del overlay
└─ settings/    la ventana de configuración
   ├─ controls.tsx   controles reutilizables
   └─ tabs/          una pestaña por archivo
```

- **Una carpeta por ventana.** Una ventana no importa de otra: lo que usan las dos va en `shared/`.
- **El motor se toca solo a través de `engine/useEngine`.** Ningún componente abre su propia conexión.
- **Un componente principal por archivo**, con el mismo nombre. Los controles chicos que siempre van juntos pueden compartir archivo (`controls.tsx`).
- **Sin lógica de negocio.** La interfaz muestra estado y recoge respuestas; lo demás vive en el motor.
- **El CSS va junto a su componente**, con el mismo nombre. Los colores salen de `theme.css`, no se escriben sueltos.
- **Los valores provisorios se marcan** con un comentario, como el estado de muestra de las pestañas.

## 4. App de escritorio (Rust)

- **Un módulo por responsabilidad del sistema:** `engine.rs` (proceso del motor), `overlay.rs`, `tray.rs`. `lib.rs` solo los conecta.
- **La lógica que no depende de Tauri va en funciones puras**, con tests en el mismo archivo. Ejemplo: `parse_ready` en `engine.rs`.
- **Los errores llegan a la interfaz como texto en español**, listos para mostrar.
- **`unwrap` solo en candados** (`lock().unwrap()`). Para lo demás, `expect` con el motivo por el que no puede fallar, o devolver el error.

## 5. Protocolo motor ↔ interfaz

Los estados y los tipos de mensaje están escritos dos veces, una por lado:

| Lado | Archivo |
|---|---|
| Motor | `engine/src/kronos_engine/core/protocol.py` |
| Interfaz | `apps/desktop/src/engine/protocol.ts` |

- **Nunca se escribe un estado o un tipo de mensaje como texto suelto.** Se usa `AssistantState.IDLE`, no `"idle"`.
- **Cambiar un lado obliga a cambiar el otro.** `engine/tests/test_protocol.py` compara los dos archivos y falla si no coinciden.
- **Solo figura lo que existe.** Un mensaje se agrega cuando el motor empieza a enviarlo, no antes.
- **`PROTOCOL_VERSION` sube** si cambia el formato de un mensaje existente (ver [CONTRIBUTING.md](../CONTRIBUTING.md)).

## 6. Nombres y comentarios

- **Identificadores en inglés:** variables, funciones, clases, archivos.
- **En español:** comentarios, docstrings, nombres de los tests y todo texto que ve el usuario.
- **Los comentarios explican el porqué**, no repiten lo que el código ya dice.
- **Cada módulo abre con una línea** que dice de qué se ocupa.
- **`PROVISORIO:`** marca lo que se va a reemplazar, y dice por qué cosa.
- **Las variables de entorno `KRONOS_*`** se declaran como constantes al principio del archivo que las lee.
- **Una excepción a un chequeo lleva su motivo** en la misma línea (`# noqa: BLE001 - …`, `// biome-ignore …: …`).

## 7. Tests

Cuándo se usa TDD está en [CONTRIBUTING.md](../CONTRIBUTING.md). Cómo se escriben:

- **Un archivo de test por módulo con lógica:** `core/sentences.py` → `tests/test_sentences.py`.
- **El nombre del test dice el comportamiento**, en español: `test_cancel_corta_el_ciclo`.
- **Piezas falsas escritas a mano** (`FakeListener`, `FakeSpeaker`) en lugar de mocks. Como `core/` depende de interfaces, alcanza con una clase chica.
- **Sin micrófono, modelos ni red.** Los tests corren con las piezas falsas o con `KRONOS_PIPELINE=demo`.

## 8. Chequeos

`pnpm check` corre todos. Son los mismos que corre GitHub en cada pull request.

| Regla | Comando | Herramienta |
|---|---|---|
| Errores y estilo de Python | `pnpm engine:lint` | ruff |
| Formato de Python | `pnpm engine:format` | ruff |
| Tipos de Python | `pnpm engine:types` | mypy, modo estricto |
| Capas del motor | `pnpm engine:layers` | import-linter |
| Tests del motor y protocolo | `pnpm engine:test` | pytest |
| Estilo y formato de la interfaz | `pnpm desktop:lint` | Biome |
| Tipos de la interfaz | `pnpm --filter @kronos/desktop build` | TypeScript |
| Formato, avisos y tests de Rust | `pnpm desktop:rust` | rustfmt, clippy, cargo test |
| Tope de 300 líneas | `pnpm size:check` | `scripts/check-size.mjs` |
| Misma versión en todos los archivos | `pnpm version:check` | `scripts/version.mjs` |

Para corregir el formato en lugar de solo verificarlo:

```
uv run --project engine ruff format engine     # Python
pnpm --filter @kronos/desktop format           # interfaz
cargo fmt --manifest-path apps/desktop/src-tauri/Cargo.toml
```

Reglas apagadas a propósito en Biome (`apps/desktop/biome.json`):

| Regla | Por qué |
|---|---|
| `noImportantStyles` | `!important` se usa para apagar animaciones con `prefers-reduced-motion`. |
| `useSemanticElements` | Los interruptores y las opciones son botones con `role`, para poder darles el estilo propio. |
