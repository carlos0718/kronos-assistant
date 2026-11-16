"""Acción: abrir una aplicación instalada."""

import asyncio
import difflib
import re
import unicodedata
from collections.abc import Mapping, Sequence
from typing import Any

from kronos_engine.core.platform import App, Platform
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec

# Qué tan parecido tiene que ser un nombre para tomarlo por un error de transcripción.
_TYPO = 0.8
# Y para ofrecerlo como «¿quisiste decir…?».
_SIMILAR = 0.65
_MAX_SUGGESTIONS = 4


def _normalize(text: str) -> str:
    """Minúsculas, sin acentos ni signos: así llega lo que se transcribe de la voz."""
    plain = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return " ".join(re.findall(r"[a-z0-9]+", plain))


def _alike(word: str, other: str) -> bool:
    return difflib.SequenceMatcher(None, word, other).ratio() >= _TYPO


def _candidates(name: str, apps: Sequence[App]) -> list[App]:
    """Las aplicaciones que podrían ser la pedida, de la más probable a la menos."""
    wanted = _normalize(name)
    if not wanted:
        return []
    names = {app: _normalize(app.name) for app in apps}
    if exact := [app for app in apps if names[app] == wanted]:
        return exact[:1]
    words = wanted.split()
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


def find_app(name: str, apps: Sequence[App]) -> App | None:
    """La aplicación pedida, o `None` si no hay ninguna o no se puede decidir entre varias."""
    found = _candidates(name, apps)
    if not found:
        return None
    if len(found) > 1 and len(_normalize(found[0].name)) == len(_normalize(found[1].name)):
        return None
    return found[0]


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
                }
            },
        },
    )
    level = PermissionLevel.NORMAL

    def __init__(self, platform: Platform) -> None:
        self._platform = platform

    async def run(self, arguments: Mapping[str, Any]) -> str:
        name = str(arguments.get("name") or "").strip()
        if not name:
            raise ToolError("Falta el nombre de la aplicación.")
        # El sistema puede tardar en contestar: no se frena al resto del motor.
        apps = await asyncio.to_thread(self._platform.apps)
        # Solo se abre algo de la lista del sistema: el modelo no elige qué se ejecuta.
        app = find_app(name, apps)
        if app is None:
            raise ToolError(self._not_found(name, apps))
        await asyncio.to_thread(self._platform.open_app, app)
        return f"Se abrió {app.name}."

    def _not_found(self, name: str, apps: Sequence[App]) -> str:
        message = f"No hay una aplicación instalada que se llame «{name}»."
        if similar := _suggestions(name, apps):
            message += f" Las más parecidas son: {', '.join(similar)}. Preguntale al usuario cuál."
        return message
