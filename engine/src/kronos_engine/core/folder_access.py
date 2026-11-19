"""Interfaz de las carpetas que Kronos puede mirar, y hasta qué profundidad busca en ellas.

La implementa `config/`; el servidor y la acción de abrir carpetas solo conocen esta interfaz.
Es un permiso: Kronos no busca ni abre nada fuera de estas carpetas.
"""

import os
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol

from kronos_engine.core.platform import Folder

# Cuántos niveles adentro de cada carpeta busca lo que no está justo ahí.
DEFAULT_DEPTH = 3
MIN_DEPTH = 1
# Más adentro casi nunca hay lo que el usuario nombra, y recorrer tarda.
MAX_DEPTH = 5


@dataclass(frozen=True)
class FolderAccess:
    # Las carpetas conocidas que puede mirar. De fábrica, todas.
    known: frozenset[Folder] = frozenset(Folder)
    # Otras carpetas que el usuario sumó, como `D:\proyectos`.
    extra: tuple[Path, ...] = ()
    depth: int = DEFAULT_DEPTH


class FolderAccessError(ValueError):
    """Lo elegido no se puede guardar. El mensaje es para el usuario."""


def path_key(path: Path) -> str:
    """Con qué se compara una carpeta con otra."""
    # En Windows `D:\Proyectos` y `d:\proyectos\` son la misma carpeta.
    return os.path.normcase(os.path.normpath(path))


def checked(access: FolderAccess) -> FolderAccess:
    """Lo elegido, sin repetidos. Lanza `FolderAccessError` si algo no sirve."""
    if not MIN_DEPTH <= access.depth <= MAX_DEPTH:
        raise FolderAccessError(f"Los niveles van de {MIN_DEPTH} a {MAX_DEPTH}.")
    extra: dict[str, Path] = {}
    for path in access.extra:
        # Una ruta relativa dependería de dónde arrancó el motor.
        if not path.is_absolute():
            raise FolderAccessError(f"«{path}» no es una ruta completa.")
        if not path.is_dir():
            raise FolderAccessError(f"No existe la carpeta «{path}».")
        extra.setdefault(path_key(path), Path(os.path.normpath(path)))
    return FolderAccess(access.known, tuple(extra.values()), access.depth)


class FolderAccessControl(Protocol):
    def get(self) -> FolderAccess:
        """Las carpetas que Kronos puede mirar."""
        ...

    def set(self, access: FolderAccess) -> None:
        """Guarda lo elegido; se usa desde el próximo pedido. Lanza `FolderAccessError`."""
        ...
