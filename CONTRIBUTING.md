# Cómo se trabaja en Kronos AI Assistant

Este documento fija el flujo de trabajo: ramas, commits, versiones y pruebas. Cómo se escribe el código (tamaño de los archivos, capas, nombres) está en [docs/CODIGO.md](docs/CODIGO.md).

## Ramas

```
main  ──●────────────────────────●── (tag v0.2.0)
         \                      /
dev   ────●──────●────────●────●
                  \      /
feat/instalador    ●──●──●
```

| Rama | Para qué |
|---|---|
| `main` | Lo publicado. Cada commit de `main` es una versión con su tag. |
| `dev` | Donde se juntan las features terminadas. Es la rama por defecto. |
| `feat/…`, `fix/…`, `docs/…`, `chore/…` | Una rama por cambio. Sale de `dev` y vuelve a `dev`. |

- **Nunca se trabaja directo sobre `main` ni sobre `dev`.** Las dos están protegidas: solo aceptan pull requests con los chequeos en verde.
- Los pull requests se mergean con **merge commit**, para conservar los commits de la rama.

## Paso a paso de un cambio

1. Crear la rama desde `dev`:
   ```
   git switch dev && git pull
   git switch -c feat/nombre-corto
   ```
2. Trabajar y hacer commits (ver "Commits").
3. Si el cambio sube la versión (ver "Versiones"), correr `pnpm version:set X.Y.Z` y commitear.
4. Subir la rama y abrir un pull request hacia `dev`.
5. Mergear cuando los chequeos pasan.

**Publicar una versión:** pull request de `dev` a `main`. Una vez mergeado, crear el tag en `main`:

```
git switch main && git pull
git tag vX.Y.Z && git push origin vX.Y.Z
```

## Commits

[Conventional Commits](https://www.conventionalcommits.org/es/), con la descripción en español:

| Prefijo | Cuándo |
|---|---|
| `feat:` | Funcionalidad nueva |
| `fix:` | Corrección de un error |
| `docs:` | Solo documentación |
| `test:` | Solo tests |
| `refactor:` | Cambio interno que no altera el comportamiento |
| `chore:` | Herramientas, dependencias, configuración |

## Versiones

Se sigue [semver](https://semver.org/lang/es/). Mientras la app esté en `0.x`:

| Cambio | Sube | Ejemplo |
|---|---|---|
| Feature nueva, o cambio que rompe compatibilidad | Minor | `0.1.0` → `0.2.0` |
| Corrección de un error | Patch | `0.2.0` → `0.2.1` |
| Solo documentación, tests o tareas internas | Nada | — |

- `1.0.0` será la primera versión estable para usar a diario. Desde ahí, romper compatibilidad sube el major.
- La versión se cambia **en la rama de la feature**, con `pnpm version:set X.Y.Z`. Ese comando la escribe en todos los archivos donde vive (los `package.json`, Tauri, Cargo y el motor). `pnpm version:check` confirma que coinciden.
- La versión del **protocolo** motor ↔ interfaz (`PROTOCOL_VERSION`) es independiente: solo sube si cambia el formato de los mensajes.

## Pruebas y TDD

Se usa TDD (primero el test que falla, después el código) **donde hay lógica**:

| Parte | Cómo se prueba |
|---|---|
| Motor Python: protocolo, permisos, clave secreta, memoria, rutinas, proveedores de LLM | **TDD** |
| Lógica de Rust que se pueda separar de las ventanas | **TDD** |
| Lógica de React sin dibujo (por ejemplo `useEngine`) | Tests después, cuando el comportamiento esté estable |
| Parte visual: bolita, ventanas, estilos | Sin TDD: revisión a ojo y con capturas |

En permisos y seguridad un error es grave y un test lo detecta barato. En lo visual el test cuesta mucho, se rompe con cada cambio de diseño y detecta poco.

## Chequeos

Antes de abrir un pull request, y de nuevo de forma automática en GitHub:

```
pnpm check
```

Corre todos los chequeos: estilo, formato, tipos, capas, tests, tamaño de los archivos y versión. El detalle de cada uno, y cómo correrlos por separado, está en [docs/CODIGO.md](docs/CODIGO.md#8-chequeos).
