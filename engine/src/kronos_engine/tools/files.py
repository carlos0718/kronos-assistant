"""Acción: abrir un archivo que está dentro de las carpetas que el usuario le permite mirar.

Lo abre con la aplicación que el usuario tiene para ese tipo de archivo. Solo
abre los tipos de `OPENABLE_SUFFIXES`: nunca programas, scripts ni documentos
con macros. Busca como `open_folder`: por el nombre, y si no lo encuentra, el
modelo elige por el significado en una pregunta aparte.
"""

import asyncio
import logging
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kronos_engine.core.choosing import Chooser
from kronos_engine.core.folder_access import FolderAccess, path_key
from kronos_engine.core.platform import OPENABLE_SUFFIXES, App, Files
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec
from kronos_engine.tools.apps import find_app
from kronos_engine.tools.folder_search import (
    FILLER,
    Scope,
    below,
    compact,
    roots_for,
    scope_for,
    sharing_a_word,
    similar,
)
from kronos_engine.tools.folders import OpenFolderTool

log = logging.getLogger(__name__)

# «Abrí el archivo del presupuesto»: se dice alrededor del nombre.
_FILLER = FILLER | {"archivo", "documento", "file"}
# Una carpeta con miles de archivos no traba la respuesta.
_MAX_FILES = 5000
# Cuántos se le ofrecen al modelo para que elija por el significado (ver `folder_search`).
_MAX_CANDIDATES = 80
# Cuántos se nombran cuando hay que preguntarle al usuario cuál.
_MAX_LISTED = 3
# Windows marca así los archivos que no se muestran.
_HIDDEN = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM


@dataclass(frozen=True)
class _Found:
    path: Path
    where: str  # «la carpeta Documentos».


@dataclass(frozen=True)
class _Target:
    found: _Found
    # Lo pedido, si no coincidió con el nombre del archivo.
    guessed: str = ""


def _visible_files(folder: Path) -> list[Path]:
    try:
        entries = sorted(folder.iterdir(), key=lambda entry: entry.name.casefold())
    except OSError:
        return []
    found = []
    for entry in entries:
        # «~$informe.docx» es el archivo que Word deja mientras el documento está abierto.
        if entry.name.startswith((".", "~$")):
            continue
        try:
            info = entry.stat()
        except OSError:
            continue
        if stat.S_ISREG(info.st_mode) and not getattr(info, "st_file_attributes", 0) & _HIDDEN:
            found.append(entry)
    return found


def _files_in(bases: Sequence[tuple[Path, str]], scope: Scope) -> list[_Found]:
    """Los archivos visibles de cada carpeta de partida y de las que tiene adentro."""
    found: list[_Found] = []
    seen: set[str] = set()
    for base, label in bases:
        for folder in [base, *below(base, scope)]:
            where = label if folder == base else f"la carpeta {folder.name}"
            for path in _visible_files(folder):
                if (key := path_key(path)) not in seen:
                    seen.add(key)
                    found.append(_Found(path, where))
                if len(found) >= _MAX_FILES:
                    return found
    return found


def _matches(name: str, found: Sequence[_Found]) -> list[_Found]:
    """Los archivos que podrían ser el pedido, de la forma más estricta a la más suelta."""
    wanted = compact(name)
    exact = [f for f in found if wanted in (compact(f.path.stem), compact(f.path.name))]
    if exact:
        return exact
    entries = [App(f.path.stem, str(index)) for index, f in enumerate(found)]
    if hit := find_app(name, entries, ignore=_FILLER):
        return [found[int(hit.id)]]
    if shared := sharing_a_word(name, [f.path for f in found]):
        return [f for f in found if f.path == shared]
    return []


def _openable(found: _Found) -> bool:
    return found.path.suffix.lower() in OPENABLE_SUFFIXES


def _listed(found: Sequence[_Found]) -> str:
    names = [f"«{f.path.name}» en {f.where}" for f in found[:_MAX_LISTED]]
    more = len(found) - len(names)
    return ", ".join(names) + (f" y {more} más" if more else "")


class OpenFileTool:
    level = PermissionLevel.NORMAL

    def __init__(
        self,
        files: Files,
        access: Callable[[], FolderAccess] = FolderAccess,
        chooser: Chooser | None = None,
    ) -> None:
        self._files = files
        # Se pide en cada uso: el usuario cambia los permisos sin reiniciar el motor.
        self._access = access
        self._chooser = chooser
        # Para encontrar la carpeta que dijo el usuario, como la encuentra `open_folder`.
        self._folders = OpenFolderTool(files, access, chooser)

    @property
    def spec(self) -> ToolSpec:
        roots = roots_for(self._access(), self._files)
        known = ", ".join(root.name for root in roots) or "ninguna por ahora"
        return ToolSpec(
            "open_file",
            "Abre un archivo del usuario (un documento, una planilla, una presentación, un PDF, "
            "un texto, una imagen, música o un video) con la aplicación que tiene para ese "
            f"tipo de archivo. Lo busca dentro de las carpetas que el usuario permite ({known}) "
            "y de las que tienen adentro. No abre programas, scripts ni documentos con macros. "
            "Usala con lo que dijo el usuario aunque no sepas el nombre exacto ni dónde está: "
            "la acción lo busca también por el significado. Para abrir una carpeta, usá "
            "open_folder.",
            {
                "type": "object",
                "required": ["file"],
                "properties": {
                    "file": {
                        "type": "string",
                        "description": (
                            "El nombre del archivo tal como lo dijo el usuario, con o sin la "
                            "extensión. Ejemplos: el informe de ventas, CV.pdf, las fotos del "
                            "viaje."
                        ),
                    },
                    "folder": {
                        "type": "string",
                        "description": (
                            f"La carpeta donde está, solo si el usuario la dijo ({known} o una "
                            "subcarpeta). Vacío si no la dijo."
                        ),
                    },
                },
            },
        )

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        target = await self._target(arguments)
        return f"abrir «{target.found.path.name}»"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        target = await self._target(arguments)
        await asyncio.to_thread(self._files.open_file, target.found.path)
        # Sin el nombre: el registro no guarda qué archivos tiene el usuario.
        log.info("Se abrió un archivo del usuario.")
        result = f"Se abrió «{target.found.path.name}», en {target.found.where}."
        if target.guessed:
            result += (
                f" No había ningún archivo que se llamara «{target.guessed}»: decile al usuario "
                "el nombre del que se abrió."
            )
        return result

    async def _target(self, arguments: Mapping[str, Any]) -> _Target:
        name = str(arguments.get("file") or arguments.get("name") or "").strip()
        if not name:
            raise ToolError("Falta el nombre del archivo.")
        access = self._access()
        if folder := str(arguments.get("folder") or "").strip():
            bases = [await self._folders.locate({"folder": folder})]
        else:
            roots = [root for root in roots_for(access, self._files) if root.searched]
            if not roots:
                raise ToolError("El usuario no le dio permiso a Kronos para mirar ninguna carpeta.")
            bases = [(root.path, root.label) for root in roots]
        found = await asyncio.to_thread(_files_in, bases, scope_for(access, self._files))
        matches = _matches(name, found)
        openable = [f for f in matches if _openable(f)]
        if matches and not openable:
            raise ToolError(
                f"«{matches[0].path.name}» es un programa, un script o un documento con macros: "
                "Kronos no abre programas, scripts ni documentos con macros."
            )
        if len(openable) > 1:
            raise ToolError(
                f"Hay varios archivos que pueden ser: {_listed(openable)}. "
                "Preguntale al usuario cuál quiere."
            )
        if openable:
            return _Target(openable[0])
        return await self._choose(name, [f for f in found if _openable(f)], bases)

    async def _choose(
        self, name: str, found: Sequence[_Found], bases: Sequence[tuple[Path, str]]
    ) -> _Target:
        """Segunda pasada: «mi hoja de vida» es «CV-Ana-2026.pdf». La lista va en una pregunta
        aparte, nunca en la conversación: el modelo la leería en voz alta."""
        places = ", ".join(label for _, label in bases)
        missing = ToolError(
            f"No encontré ningún archivo que se llame «{name}» en {places}. "
            "Preguntale al usuario cómo se llama o en qué carpeta está."
        )
        if self._chooser is None or not found:
            raise missing
        alike = similar(name, [f.path for f in found])
        rest = [index for index in range(len(found)) if index not in set(alike)]
        candidates = [found[index] for index in [*alike, *rest][:_MAX_CANDIDATES]]
        options = [f"{f.path.name} (en {f.where})" for f in candidates]
        index = await self._chooser.choose(name, options)
        if index is None:
            raise missing
        log.info("El archivo se eligió por el significado.")
        return _Target(candidates[index], name)
