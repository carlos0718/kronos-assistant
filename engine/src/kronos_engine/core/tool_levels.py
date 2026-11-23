"""Interfaces del nivel de permiso de cada acción y de cómo lo cambia el usuario.

Reglas (ver «Cambiar una acción de nivel» en el README): subir una acción siempre
se puede; bajarla entre los niveles 1 y 2 también; bajar algo del nivel 3 exige la
clave secreta; el nivel 4 es fijo. Las comprueba el código, no el modelo: el modelo
no puede cambiar un nivel, solo la interfaz de configuración.
"""

from dataclasses import dataclass
from typing import Protocol

from kronos_engine.core.tools import PermissionLevel

# Cómo se llama cada acción en la pantalla de configuración. Una acción nueva que no
# esté acá se muestra con su nombre.
LABELS = {
    "current_time": "Decir la hora y la fecha",
    "weather": "Decir el clima",
    "open_app": "Abrir aplicaciones",
    "close_app": "Cerrar aplicaciones",
    "open_folder": "Abrir carpetas",
    "open_file": "Abrir archivos",
    "volume": "Cambiar el volumen",
    "run_command": "Ejecutar comandos de terminal",
}


@dataclass(frozen=True)
class ActionLevel:
    """Una acción y el nivel que tiene hoy."""

    name: str
    label: str
    factory: PermissionLevel  # El nivel de fábrica.
    level: PermissionLevel  # El que vale ahora.
    lowest: PermissionLevel  # El más bajo al que se la puede llevar.
    # El nivel 4 no se cambia desde la app.
    fixed: bool = False


class ToolLevelError(ValueError):
    """No se puede cambiar el nivel. El mensaje se le muestra al usuario."""


class LevelStore(Protocol):
    """Dónde se guardan los niveles que el usuario cambió (la implementa `config/`)."""

    def get(self) -> dict[str, int]: ...

    def set(self, levels: dict[str, int]) -> None: ...


class LevelOverrides(Protocol):
    """Lo que el control de permisos sabe de los niveles cambiados: cuál vale ahora."""

    def level_of(self, name: str, factory: PermissionLevel) -> PermissionLevel: ...


class ToolLevelsControl(Protocol):
    """Lo que la interfaz puede hacer con los niveles."""

    def actions(self) -> list[ActionLevel]: ...

    def set_level(self, name: str, level: int, secret: str | None = None) -> None:
        """Cambia el nivel. `secret` es la clave, que hace falta para bajar algo del nivel 3.

        Lanza `ToolLevelError`.
        """
        ...
