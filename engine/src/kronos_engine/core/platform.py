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


class Platform(Protocol):
    def apps(self) -> Sequence[App]:
        """Las aplicaciones instaladas que el usuario puede abrir."""
        ...

    def open_app(self, app: App) -> None:
        """Abre una aplicación de la lista."""
        ...
