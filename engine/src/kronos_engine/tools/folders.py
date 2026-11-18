"""Acción: abrir una carpeta del usuario (Documentos, Descargas…) o una de sus subcarpetas."""

import asyncio
import difflib
import logging
import re
import stat
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from kronos_engine.core.platform import App, Folder, Folders
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec
from kronos_engine.tools.apps import alike, find_app, normalize

log = logging.getLogger(__name__)

# Cómo se nombra cada carpeta en la respuesta, y cómo puede pedirla el usuario.
_FOLDERS: Mapping[Folder, tuple[str, tuple[str, ...]]] = {
    Folder.DESKTOP: ("Escritorio", ("Escritorio", "Desktop")),
    Folder.DOCUMENTS: ("Documentos", ("Documentos", "Documents")),
    Folder.DOWNLOADS: ("Descargas", ("Descargas", "Downloads")),
    Folder.PICTURES: ("Imágenes", ("Imágenes", "Fotos", "Pictures")),
    Folder.MUSIC: ("Música", ("Música", "Music")),
    Folder.VIDEOS: ("Videos", ("Videos", "Vídeos")),
    Folder.HOME: ("tu carpeta personal", ("Personal", "Usuario", "Perfil", "Home")),
}
# «Abrí la sección Documentos», «mis descargas»: se dicen alrededor del nombre.
_FILLER = frozenset({"carpeta", "carpetas", "seccion", "folder", "mi", "mis", "my", "de", "del"})
# Lo que el modelo lee, también para contarle al usuario qué se puede abrir.
_KNOWN = "Escritorio, Documentos, Descargas, Imágenes, Música, Videos y la carpeta personal"
# Lo que se aclara entre paréntesis no es parte del nombre: «Imágenes (fotos)».
_ASIDE = re.compile(r"\([^)]*\)")
# Cuántas subcarpetas se ofrecen cuando la pedida no existe.
_MAX_LISTED = 20
_SIMILAR = 0.6
# Si no está justo ahí, se busca más adentro: hasta tantos niveles y tantas carpetas.
_DEPTH = 3
_MAX_SCANNED = 3000
# Las palabras más cortas («web», «app») coinciden con demasiadas carpetas.
_MIN_WORD = 4
# Windows marca así las carpetas que no se muestran (como «AppData»).
_HIDDEN = stat.FILE_ATTRIBUTE_HIDDEN | stat.FILE_ATTRIBUTE_SYSTEM


def _compact(name: str) -> str:
    """El nombre sin acentos, signos ni espacios: «Work Space» y «work-space» son «workspace»."""
    return normalize(_ASIDE.sub(" ", name)).replace(" ", "")


def find_folder(name: str) -> Folder | None:
    """La carpeta pedida, o `None` si no es ninguna de las que se conocen."""
    entries = [
        App(alias, folder.value) for folder, (_, aliases) in _FOLDERS.items() for alias in aliases
    ]
    found = find_app(_ASIDE.sub(" ", name), entries, ignore=_FILLER)
    return Folder(found.id) if found else None


def subfolders(path: Path) -> list[Path]:
    """Las carpetas que hay adentro y que el usuario ve: sin archivos ni carpetas ocultas."""
    try:
        entries = list(path.iterdir())
    except OSError:
        return []
    found: list[Path] = []
    for entry in entries:
        try:
            info = entry.stat()
        except OSError:
            continue
        hidden = getattr(info, "st_file_attributes", 0) & _HIDDEN
        if stat.S_ISDIR(info.st_mode) and not hidden and not entry.name.startswith("."):
            found.append(entry)
    return sorted(found, key=lambda entry: entry.name.casefold())


def find_child(name: str, folders: Sequence[Path]) -> Path | None:
    """La subcarpeta pedida, de entre las que hay: se elige de la lista, nunca se arma una ruta."""
    compact = _compact(name)
    if not compact:
        return None
    # «Work Space» es «Workspace»: la transcripción a veces parte una palabra.
    if same := [path for path in folders if _compact(path.name) == compact]:
        return same[0]
    found = find_app(name, [App(path.name, str(path)) for path in folders], ignore=_FILLER)
    return Path(found.id) if found else None


def below(path: Path, depth: int = _DEPTH) -> list[Path]:
    """Las carpetas visibles hasta `depth` niveles adentro, primero las más cercanas."""
    found: list[Path] = []
    level = [path]
    for _ in range(depth):
        deeper = [child for folder in level for child in subfolders(folder)]
        found += deeper
        # Una carpeta enorme (como Descargas) no traba la respuesta.
        if not deeper or len(found) >= _MAX_SCANNED:
            break
        level = deeper
    return found[:_MAX_SCANNED]


def sharing_a_word(name: str, folders: Sequence[Path]) -> Path | None:
    """La única carpeta que comparte una palabra importante con lo pedido: «Portfolio Web» es
    «Portfolio-master» si no hay otra con «portfolio». Con dos o más, no se adivina."""
    words = {
        word
        for word in normalize(_ASIDE.sub(" ", name)).split()
        if len(word) >= _MIN_WORD and word not in _FILLER
    }
    hits = [
        path
        for path in folders
        if any(alike(word, other) for word in words for other in normalize(path.name).split())
    ]
    return hits[0] if len(hits) == 1 else None


# Cómo se busca, de la más estricta a la más suelta: justo adentro, más adentro,
# y por último por una sola palabra.
_Search = Callable[[str, Path], Path | None]
_SEARCHES: tuple[_Search, ...] = (
    lambda name, root: find_child(name, subfolders(root)),
    lambda name, root: find_child(name, below(root)),
    lambda name, root: sharing_a_word(name, subfolders(root)) or sharing_a_word(name, below(root)),
)


def locate(name: str, root: Path) -> Path | None:
    """La carpeta pedida, adentro de `root`: justo ahí o hasta unos niveles más abajo."""
    for search in _SEARCHES:
        if found := search(name, root):
            return found
    return None


@dataclass(frozen=True)
class _Target:
    path: Path
    label: str  # «la carpeta Workspace, en Escritorio».
    # Lo pedido que no coincidió exacto con el nombre de la carpeta.
    guessed: tuple[str, ...] = ()


def _label(folder: Folder) -> str:
    name = _FOLDERS[folder][0]
    return name if folder == Folder.HOME else f"la carpeta {name}"


def _names(paths: Sequence[Path]) -> str:
    names = [path.name for path in paths[:_MAX_LISTED]]
    more = len(paths) - len(names)
    return ", ".join(names) + (f" y {more} más" if more > 0 else "")


class OpenFolderTool:
    spec = ToolSpec(
        "open_folder",
        f"Abre en el explorador de archivos una carpeta del usuario ({_KNOWN}) "
        "o una subcarpeta que esté adentro de ellas, a cualquier profundidad. "
        "Las fotos están en Imágenes. No abre archivos ni carpetas de otros lugares. "
        "Para seguir bajando desde una carpeta ya abierta, pasá el camino completo "
        "desde la carpeta del usuario.",
        {
            "type": "object",
            "properties": {
                "folder": {
                    "type": "string",
                    "description": (
                        "La carpeta del usuario de donde se parte: Escritorio, Documentos, "
                        "Descargas, Imágenes, Música, Videos o carpeta personal. Vacío si "
                        "el usuario no dijo dónde está la subcarpeta."
                    ),
                },
                "subfolders": {
                    "type": "array",
                    "items": {"type": "string"},
                    "description": (
                        "Las subcarpetas por las que hay que entrar, en orden y tal como las "
                        "dijo el usuario. Para «la carpeta Workspace del escritorio»: folder "
                        "Escritorio y subfolders [Workspace]. Vacío para abrir solo la carpeta."
                    ),
                },
            },
        },
    )
    level = PermissionLevel.NORMAL

    def __init__(self, folders: Folders) -> None:
        self._folders = folders

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        target = await asyncio.to_thread(self._find, arguments)
        return f"abrir {target.label}"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        target = await asyncio.to_thread(self._find, arguments)
        await asyncio.to_thread(self._folders.open_path, target.path)
        # Sin el nombre: el registro no guarda qué carpetas tiene el usuario.
        log.info("Se abrió una carpeta del usuario.")
        result = f"Se abrió {target.label}."
        if target.guessed:
            # El usuario tiene que saber qué se abrió de verdad.
            asked = ", ".join(f"«{name}»" for name in target.guessed)
            result += (
                f" No había ninguna que se llamara exactamente {asked}: decile al usuario "
                f"el nombre de la que se abrió, «{target.path.name}»."
            )
        return result

    def _find(self, arguments: Mapping[str, Any]) -> _Target:
        name = str(arguments.get("folder") or arguments.get("name") or "").strip()
        raw = arguments.get("subfolders") or []
        steps = (
            [str(step).strip() for step in raw if str(step).strip()]
            if isinstance(raw, list)
            else []
        )
        if not name and not steps:
            raise ToolError("Falta el nombre de la carpeta.")
        if name:
            folder = find_folder(name)
            if folder is None:
                if steps:
                    raise ToolError(f"No puedo abrir «{name}». Puedo partir de: {_KNOWN}.")
                # «Abrí Workspace»: puede ser una subcarpeta dicha sin decir dónde está.
                return self._search([name])
            try:
                return self._descend(folder, steps)
            except ToolError:
                # El modelo a veces adivina dónde está («Documentos») sin que el
                # usuario lo haya dicho: se la busca en las demás antes de rendirse.
                if not steps:
                    raise
                try:
                    return self._search(steps)
                except ToolError:
                    pass
                raise
        return self._search(steps)

    def _descend(self, folder: Folder, steps: Sequence[str]) -> _Target:
        base = self._folders.folder_path(folder)
        path, here = base, _label(folder)
        guessed: list[str] = []
        for step in steps:
            child = locate(step, path)
            if child is None:
                raise ToolError(self._missing(step, here, subfolders(path)))
            if _compact(step) != _compact(child.name):
                guessed.append(step)
            path, here = child, f"la carpeta {child.name}"
        if not steps or (folder == Folder.HOME and path.parent == base):
            return _Target(path, here, tuple(guessed))
        # Dónde quedó: la carpeta del usuario o la subcarpeta que la contiene.
        parent = _FOLDERS[folder][0] if path.parent == base else path.parent.name
        return _Target(path, f"{here}, en {parent}", tuple(guessed))

    def _search(self, steps: Sequence[str]) -> _Target:
        """Busca la primera subcarpeta en todas las carpetas del usuario, de la forma más estricta
        a la más suelta: una coincidencia estricta en un lugar le gana a una suelta en otro."""
        roots = [folder for folder in Folder if folder != Folder.HOME]
        for search in _SEARCHES:
            found = [
                folder for folder in roots if search(steps[0], self._folders.folder_path(folder))
            ]
            if len(found) > 1:
                places = ", ".join(_FOLDERS[folder][0] for folder in found)
                raise ToolError(
                    f"Hay una carpeta «{steps[0]}» en varios lugares: {places}. "
                    "Preguntale al usuario cuál quiere."
                )
            if found:
                return self._descend(found[0], steps)
        raise ToolError(
            f"No hay una carpeta «{steps[0]}» en {_KNOWN}. "
            "Preguntale al usuario en cuál de ellas está."
        )

    def _missing(self, name: str, where: str, inside: Sequence[Path]) -> str:
        message = f"En {where} no hay una carpeta que se llame «{name}»."
        if not inside:
            return message + " No tiene subcarpetas."
        if len(inside) <= _MAX_LISTED:
            return message + f" Las que hay son: {_names(inside)}."
        by_name = {normalize(path.name): path for path in inside}
        close = difflib.get_close_matches(normalize(name), list(by_name), n=5, cutoff=_SIMILAR)
        if close:
            return message + f" Las más parecidas son: {_names([by_name[c] for c in close])}."
        return message
