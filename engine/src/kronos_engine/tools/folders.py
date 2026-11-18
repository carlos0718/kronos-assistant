"""Acción: abrir una de las carpetas del usuario (Documentos, Descargas…)."""

import asyncio
import logging
from collections.abc import Mapping
from typing import Any

from kronos_engine.core.platform import App, Folder, Folders
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec
from kronos_engine.tools.apps import find_app

log = logging.getLogger(__name__)

# Cómo se nombra cada carpeta en la respuesta, y cómo puede pedirla el usuario.
# El primer nombre es el que se le muestra al modelo.
_FOLDERS: Mapping[Folder, tuple[str, tuple[str, ...]]] = {
    Folder.DESKTOP: ("la carpeta Escritorio", ("Escritorio", "Desktop")),
    Folder.DOCUMENTS: ("la carpeta Documentos", ("Documentos", "Documents")),
    Folder.DOWNLOADS: ("la carpeta Descargas", ("Descargas", "Downloads")),
    Folder.PICTURES: ("la carpeta Imágenes", ("Imágenes", "Fotos", "Pictures")),
    Folder.MUSIC: ("la carpeta Música", ("Música", "Music")),
    Folder.VIDEOS: ("la carpeta Videos", ("Videos", "Vídeos")),
    Folder.HOME: ("tu carpeta personal", ("Personal", "Usuario", "Perfil", "Home")),
}
# «Abrí la sección Documentos», «mis descargas»: se dicen alrededor del nombre.
_FILLER = frozenset({"carpeta", "carpetas", "seccion", "folder", "mi", "mis", "my", "de", "del"})
# Lo que el modelo lee, también para contarle al usuario qué se puede abrir.
_KNOWN = (
    "Escritorio, Documentos, Descargas, Imágenes (las fotos), Música, Videos y la carpeta personal"
)


def find_folder(name: str) -> Folder | None:
    """La carpeta pedida, o `None` si no es ninguna de las que se conocen."""
    entries = [
        App(alias, folder.value) for folder, (_, aliases) in _FOLDERS.items() for alias in aliases
    ]
    found = find_app(name, entries, ignore=_FILLER)
    return Folder(found.id) if found else None


class OpenFolderTool:
    spec = ToolSpec(
        "open_folder",
        f"Abre en el explorador de archivos una carpeta del usuario: {_KNOWN}. "
        "No abre otras carpetas ni archivos.",
        {
            "type": "object",
            "required": ["name"],
            "properties": {
                "name": {
                    "type": "string",
                    "description": (
                        "Nombre de la carpeta, tal como lo dijo el usuario. "
                        "Ejemplos: Documentos, Descargas, Escritorio."
                    ),
                }
            },
        },
    )
    level = PermissionLevel.NORMAL

    def __init__(self, folders: Folders) -> None:
        self._folders = folders

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return f"abrir {_FOLDERS[self._find(arguments)][0]}"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        folder = self._find(arguments)
        await asyncio.to_thread(self._folders.open_folder, folder)
        log.info("Se abrió una carpeta del usuario.")
        return f"Se abrió {_FOLDERS[folder][0]}."

    def _find(self, arguments: Mapping[str, Any]) -> Folder:
        name = str(arguments.get("name") or "").strip()
        if not name:
            raise ToolError("Falta el nombre de la carpeta.")
        folder = find_folder(name)
        if folder is None:
            raise ToolError(f"No puedo abrir «{name}». Las carpetas que puedo abrir son: {_KNOWN}.")
        return folder
