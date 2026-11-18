"""Acciones: abrir una aplicación instalada y cerrar una que está abierta."""

import asyncio
import difflib
import logging
import re
import unicodedata
from collections.abc import Mapping, Sequence
from collections.abc import Set as AbstractSet
from typing import Any

from kronos_engine.core.platform import App, Platform, Window
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec

log = logging.getLogger(__name__)

# Qué tan parecida tiene que ser una palabra para tomarla por un error de
# transcripción. Con 0,75 entra una letra cambiada en una palabra de cuatro:
# «blog de notas» es «Bloc de notas».
_TYPO = 0.75
# Y para ofrecerlo como «¿quisiste decir…?».
_SIMILAR = 0.65
_MAX_SUGGESTIONS = 4
# «Abrí la calculadora»: el artículo no es parte del nombre.
_ARTICLES = {"el", "la", "los", "las", "un", "una", "the"}
# En el título de una ventana, el nombre de la aplicación va al final:
# «Documento - Aplicación». También se usan la raya y la barra.
_TITLE_SEPARATOR = re.compile(r"\s+[-\u2013\u2014|]\s+")
# Las ventanas del propio Kronos (el overlay, la configuración) no se cierran por voz.
_OWN_TITLE = "kronos"


def _normalize(text: str) -> str:
    """Minúsculas, sin acentos ni signos: así llega lo que se transcribe de la voz."""
    plain = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def _alike(word: str, other: str) -> bool:
    return difflib.SequenceMatcher(None, word, other).ratio() >= _TYPO


def _candidates(
    name: str, apps: Sequence[App], ignore: AbstractSet[str] = frozenset()
) -> list[App]:
    """Las aplicaciones que podrían ser la pedida, de la más probable a la menos."""
    wanted = _normalize(name)
    if not wanted:
        return []
    names = {app: _normalize(app.name) for app in apps}
    if exact := [app for app in apps if names[app] == wanted]:
        return exact[:1]
    skip = _ARTICLES | ignore
    words = [word for word in wanted.split() if word not in skip] or wanted.split()
    # Primero con las palabras tal cual; si no, tolerando un error de transcripción.
    for same in (str.__eq__, _alike):
        partial = [
            app
            for app in apps
            if all(any(same(word, other) for other in names[app].split()) for word in words)
        ]
        if partial:
            # «Chrome» es «Google Chrome» antes que «Chrome Remote Desktop».
            return sorted(partial, key=lambda app: len(names[app]))
    return []


def find_app(name: str, apps: Sequence[App], ignore: AbstractSet[str] = frozenset()) -> App | None:
    """La aplicación pedida, o `None` si no hay ninguna o no se puede decidir entre varias.

    `ignore` son palabras (normalizadas) que se dicen alrededor del nombre y no son parte de él.
    """
    found = _candidates(name, apps, ignore)
    if not found:
        return None
    first, second = found[0], found[1] if len(found) > 1 else None
    # Dos nombres de lo mismo no son una duda: «Videos» y «Vídeos».
    if (
        second
        and second.id != first.id
        and len(_normalize(first.name)) == len(_normalize(second.name))
    ):
        return None
    return first


def app_of(title: str) -> str:
    """El nombre de la aplicación, sacado del título de una de sus ventanas."""
    return _TITLE_SEPARATOR.split(title.strip())[-1]


def find_windows(name: str, windows: Sequence[Window]) -> list[Window]:
    """Las ventanas de la aplicación pedida. Vacío si no está abierta o no se puede decidir."""
    by_app: dict[str, list[Window]] = {}
    for window in windows:
        if not _normalize(window.title).startswith(_OWN_TITLE):
            by_app.setdefault(app_of(window.title), []).append(window)
    # Se busca por el nombre de la aplicación, no por todo el título: «notas»
    # no cierra el navegador porque una pestaña se llame «Notas de la reunión».
    app = find_app(name, [App(app_name, app_name) for app_name in by_app])
    return by_app[app.name] if app else []


def _name(arguments: Mapping[str, Any]) -> str:
    return str(arguments.get("name") or "").strip()


def _suggestions(name: str, apps: Sequence[App]) -> list[str]:
    if found := _candidates(name, apps):
        return [app.name for app in found[:_MAX_SUGGESTIONS]]
    by_name = {_normalize(app.name): app.name for app in apps}
    close = difflib.get_close_matches(
        _normalize(name), list(by_name), n=_MAX_SUGGESTIONS, cutoff=_SIMILAR
    )
    return [by_name[match] for match in close]


class OpenAppTool:
    spec = ToolSpec(
        "open_app",
        "Abre una aplicación instalada en la computadora del usuario.",
        {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Nombre de la aplicación, tal como lo dijo el usuario. "
                        "Ejemplos: Bloc de notas, Chrome, Spotify."
                    ),
                },
                "new_window": {
                    "type": "boolean",
                    "description": (
                        "true solo si el usuario pide expresamente otra ventana u otra "
                        "instancia de una aplicación que ya está abierta."
                    ),
                },
            },
        },
    )
    level = PermissionLevel.NORMAL

    def __init__(self, platform: Platform) -> None:
        self._platform = platform

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return f"abrir {_name(arguments)}"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        name = _name(arguments)
        if not name:
            raise ToolError("Falta el nombre de la aplicación.")
        # El sistema puede tardar en contestar: no se frena al resto del motor.
        apps = await asyncio.to_thread(self._platform.apps)
        # Solo se abre algo de la lista del sistema: el modelo no elige qué se ejecuta.
        app = find_app(name, apps)
        if app is None:
            raise ToolError(self._not_found(name, apps))
        if not arguments.get("new_window"):
            # Si ya está abierta no se abre otra: se la trae al frente.
            windows = find_windows(app.name, await asyncio.to_thread(self._platform.windows))
            if windows:
                await asyncio.to_thread(self._platform.focus_window, windows[0])
                # Sin el nombre: el registro no guarda qué aplicaciones usa el usuario.
                log.info("La aplicación ya estaba abierta: quedó al frente, no se abrió otra.")
                return f"{app.name} ya estaba abierta: quedó al frente y no se abrió otra ventana."
        await asyncio.to_thread(self._platform.open_app, app)
        log.info("La aplicación se abrió en una ventana nueva.")
        return f"Se abrió {app.name}."

    def _not_found(self, name: str, apps: Sequence[App]) -> str:
        message = f"No hay una aplicación instalada que se llame «{name}»."
        if similar := _suggestions(name, apps):
            message += f" Las más parecidas son: {', '.join(similar)}. Preguntale al usuario cuál."
        return message


class CloseAppTool:
    spec = ToolSpec(
        "close_app",
        "Cierra una aplicación que está abierta en la computadora del usuario. "
        "Kronos le pide la confirmación al usuario por su cuenta antes de cerrarla: "
        "llamá a la acción directamente, sin preguntarle antes.",
        {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Nombre de la aplicación, tal como lo dijo el usuario. "
                        "Ejemplos: Chrome, Bloc de notas, Spotify."
                    ),
                }
            },
        },
    )
    # Cerrar puede hacer perder lo que no se guardó: pide aprobación.
    level = PermissionLevel.SENSITIVE

    def __init__(self, platform: Platform) -> None:
        self._platform = platform

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        # Se busca antes de preguntar: así la pregunta dice qué se va a cerrar
        # de verdad, y no se pide permiso para cerrar algo que no está abierto.
        return f"cerrar {_summary(await self._open_windows(arguments))}"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        windows = await self._open_windows(arguments)
        for window in windows:
            await asyncio.to_thread(self._platform.close_window, window)
        return f"Hecho: se cerró {_summary(windows)}."

    async def _open_windows(self, arguments: Mapping[str, Any]) -> list[Window]:
        name = _name(arguments)
        if not name:
            raise ToolError("Falta el nombre de la aplicación.")
        windows = find_windows(name, await asyncio.to_thread(self._platform.windows))
        if not windows:
            raise ToolError(f"No hay ninguna ventana abierta de «{name}».")
        return windows


def _summary(windows: Sequence[Window]) -> str:
    """«Google Chrome (2 ventanas)»."""
    app = app_of(windows[0].title)
    return app if len(windows) == 1 else f"{app} ({len(windows)} ventanas)"
