"""Niveles de permiso simulados, para el modo demo (sin acciones reales)."""

from kronos_engine.core.tool_levels import LABELS, ActionLevel, ToolLevelError
from kronos_engine.core.tools import PermissionLevel

_ACTIONS = {
    "open_app": PermissionLevel.NORMAL,
    "close_app": PermissionLevel.SENSITIVE,
    "run_command": PermissionLevel.SENSITIVE,
}
_SECRET = "clave-de-prueba"


class DemoToolLevels:
    def __init__(self) -> None:
        self._levels = dict(_ACTIONS)

    def actions(self) -> list[ActionLevel]:
        return [
            ActionLevel(
                name,
                LABELS[name],
                factory,
                self._levels[name],
                # La terminal nunca baja de su nivel de fábrica.
                factory if name == "run_command" else PermissionLevel.NORMAL,
            )
            for name, factory in _ACTIONS.items()
        ]

    def set_level(self, name: str, level: int, secret: str | None = None) -> None:
        action = next((item for item in self.actions() if item.name == name), None)
        if action is None:
            raise ToolLevelError("Esa acción no existe.")
        if not action.lowest <= level <= PermissionLevel.CRITICAL:
            raise ToolLevelError(f"El nivel de esta acción va de {action.lowest.value} a 3.")
        if level < action.level and action.level >= PermissionLevel.CRITICAL and secret != _SECRET:
            raise ToolLevelError("La clave secreta no es correcta.")
        self._levels[name] = PermissionLevel(level)
