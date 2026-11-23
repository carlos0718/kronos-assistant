"""Interfaz de lo que Kronos le pide al sistema operativo.

Cada sistema la implementa en `platform/` (hoy solo Windows).
"""

from collections.abc import Sequence
from dataclasses import dataclass
from enum import Enum
from pathlib import Path
from typing import Protocol


@dataclass(frozen=True)
class App:
    """Una aplicación instalada."""

    name: str  # Como figura en el menú del sistema.
    id: str  # Con qué la identifica el sistema para abrirla.


@dataclass(frozen=True)
class Window:
    """Una ventana abierta, a la vista del usuario."""

    title: str
    id: int  # Con qué la identifica el sistema.
    # Si es una ventana del explorador de archivos: se reusa para abrir otra carpeta.
    file_browser: bool = False


# Los tipos de archivo que Kronos abre: documentos, planillas, presentaciones,
# texto, imágenes, audio y video. Es una lista de permitidos, no de prohibidos:
# lo que no está (programas, scripts, accesos directos, documentos con macros
# como .docm o .xlsm) no se abre, aunque sea un tipo que no se conocía.
OPENABLE_SUFFIXES = frozenset(
    {
        *(".pdf", ".epub", ".txt", ".md", ".rtf", ".csv"),
        *(".doc", ".docx", ".odt", ".xls", ".xlsx", ".ods", ".ppt", ".pptx", ".odp"),
        *(".jpg", ".jpeg", ".png", ".gif", ".bmp", ".webp", ".heic", ".tif", ".tiff"),
        *(".mp3", ".wav", ".m4a", ".flac", ".ogg", ".aac"),
        *(".mp4", ".mkv", ".avi", ".mov", ".wmv", ".webm"),
    }
)


@dataclass(frozen=True)
class CommandResult:
    """Lo que dejó un comando de terminal."""

    output: str  # Lo que escribió, sin recortar.
    exit_code: int | None  # `None` si se cortó por tardar demasiado.


class Shell(Protocol):
    async def run(self, command: str, seconds: float) -> CommandResult:
        """Ejecuta el comando en la terminal del usuario, sin permisos de administrador.

        Si pasan `seconds` segundos lo corta (a él y a lo que haya lanzado) y
        devuelve lo que alcanzó a escribir, con `exit_code` en `None`.
        """
        ...


class Volume(Protocol):
    """El volumen general de la computadora."""

    def level(self) -> int:
        """De 0 a 100."""
        ...

    def set_level(self, percent: int) -> None: ...

    def muted(self) -> bool: ...

    def set_muted(self, muted: bool) -> None: ...


class Folder(Enum):
    """Las carpetas que todo usuario tiene, estén donde estén en el disco."""

    DESKTOP = "desktop"
    DOCUMENTS = "documents"
    DOWNLOADS = "downloads"
    PICTURES = "pictures"
    MUSIC = "music"
    VIDEOS = "videos"
    HOME = "home"  # La carpeta personal, la que contiene a las demás.


class Folders(Protocol):
    def folder_path(self, folder: Folder) -> Path:
        """Dónde está la carpeta en el disco de este usuario."""
        ...

    def open_path(self, path: Path) -> None:
        """Abre la carpeta en el explorador de archivos del sistema, adelante de todo."""
        ...


class Files(Folders, Protocol):
    def open_file(self, path: Path) -> None:
        """Abre el archivo con la aplicación que el usuario tiene para ese tipo, adelante de todo.

        Solo si su tipo está en `OPENABLE_SUFFIXES`: si no, no hace nada.
        """
        ...


class Platform(Files, Protocol):
    def apps(self) -> Sequence[App]:
        """Las aplicaciones instaladas que el usuario puede abrir."""
        ...

    def open_app(self, app: App) -> None:
        """Abre una aplicación de la lista."""
        ...

    def windows(self) -> Sequence[Window]:
        """Las ventanas abiertas que el usuario tiene a la vista."""
        ...

    def focus_window(self, window: Window) -> None:
        """Trae la ventana al frente."""
        ...

    def close_window(self, window: Window) -> None:
        """Le pide a la ventana que se cierre, como al tocar la X.

        No la fuerza: si hay cambios sin guardar, la aplicación puede preguntar.
        """
        ...
