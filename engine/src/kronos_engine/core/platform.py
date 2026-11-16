"""Interfaz de lo que Kronos le pide al sistema operativo.

Cada sistema la implementa en `platform/` (hoy solo Windows).
"""

from collections.abc import Sequence
from dataclasses import dataclass
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


class Platform(Protocol):
    def apps(self) -> Sequence[App]:
        """Las aplicaciones instaladas que el usuario puede abrir."""
        ...

    def open_app(self, app: App) -> None:
        """Abre una aplicación de la lista."""
        ...

    def windows(self) -> Sequence[Window]:
        """Las ventanas abiertas que el usuario tiene a la vista."""
        ...

    def close_window(self, window: Window) -> None:
        """Le pide a la ventana que se cierre, como al tocar la X.

        No la fuerza: si hay cambios sin guardar, la aplicación puede preguntar.
        """
        ...
