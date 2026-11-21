"""Qué carpetas no se pueden mirar: las que el usuario no permitió en la pestaña Permisos."""

from collections.abc import Sequence
from pathlib import Path

from kronos_engine.core.folder_access import path_key
from kronos_engine.core.platform import Folder, Folders
from kronos_engine.tools.folder_search import FOLDERS, Root, Scope, find_folder, join_names, locate

NO_ACCESS = (
    "El usuario no le dio permiso a Kronos para mirar {where}. "
    "Lo puede cambiar en la pestaña Permisos de la configuración."
)


def turned_off(
    step: str, folders: Folders, scope: Scope, inside: Path | None = None
) -> Folder | None:
    """La carpeta conocida y apagada que nombra `step` («Videos»), si está en `inside`."""
    folder = find_folder(step)
    if folder is None:
        return None
    path = folders.folder_path(folder)
    if path_key(path) not in scope.skip:
        return None
    if inside is not None and path_key(path.parent) != path_key(inside):
        return None
    return folder


def off_elsewhere(off: Folder, name: str, searched: Sequence[Root], scope: Scope) -> str:
    """Que no tiene permiso, y dónde hay otras con ese nombre: quizás quería una de esas."""
    said = NO_ACCESS.format(where=f"en {FOLDERS[off][0]}")
    places = [root.name for root in searched if locate(name, root.path, scope)]
    if places:
        said += (
            f" Hay otras carpetas «{name}» en {join_names(places)}: si quería una de esas, "
            "preguntale cuál."
        )
    return said
