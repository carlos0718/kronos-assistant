"""El nivel de permiso de cada acción: el de fábrica o el que eligió el usuario."""

import logging
from collections.abc import Sequence

from kronos_engine.core.secret import SecretVault
from kronos_engine.core.tool_levels import LABELS, ActionLevel, LevelStore, ToolLevelError
from kronos_engine.core.tools import GradedTool, PermissionLevel, Tool

log = logging.getLogger(__name__)

_NO_KEY = "Para bajar un nivel crítico hace falta la clave secreta, y todavía no creaste una."
_NEEDS_KEY = "Para bajar un nivel crítico escribí la clave secreta."
_WRONG_KEY = "La clave secreta no es correcta."


class ToolLevels:
    """Implementa `LevelOverrides` y `ToolLevelsControl` sobre las acciones del motor."""

    def __init__(self, tools: Sequence[Tool], store: LevelStore, vault: SecretVault) -> None:
        self._tools = {tool.spec.name: tool for tool in tools}
        self._store = store
        self._vault = vault

    def level_of(self, name: str, factory: PermissionLevel) -> PermissionLevel:
        """El nivel que vale: lo guardado, si sirve; si no, el de fábrica."""
        tool = self._tools.get(name)
        saved = self._store.get().get(name)
        if tool is None or saved is None or self._fixed(tool):
            return factory
        try:
            level = PermissionLevel(saved)
        except ValueError:
            return factory
        # Editado a mano, el archivo no puede dejar una acción más abajo de lo permitido.
        if not self._lowest(tool) <= level <= PermissionLevel.CRITICAL:
            return factory
        return level

    def actions(self) -> list[ActionLevel]:
        return [
            ActionLevel(
                name,
                LABELS.get(name, name),
                tool.level,
                self.level_of(name, tool.level),
                self._lowest(tool),
                self._fixed(tool),
            )
            for name, tool in self._tools.items()
        ]

    def set_level(self, name: str, level: int, secret: str | None = None) -> None:
        tool = self._tools.get(name)
        if tool is None:
            raise ToolLevelError("Esa acción no existe.")
        if self._fixed(tool):
            raise ToolLevelError("Esa acción está prohibida: su nivel no se puede cambiar.")
        lowest = self._lowest(tool)
        try:
            wanted = PermissionLevel(level)
        except ValueError:
            wanted = None
        if wanted is None or not lowest <= wanted <= PermissionLevel.CRITICAL:
            raise ToolLevelError(f"El nivel de esta acción va de {lowest.value} a 3.")
        current = self.level_of(name, tool.level)
        if wanted < current and current >= PermissionLevel.CRITICAL:
            self._check_secret(secret)
        levels = self._store.get()
        if wanted == tool.level:
            levels.pop(name, None)
        else:
            levels[name] = wanted.value
        self._store.set(levels)
        log.info(
            "Se cambió el nivel de la acción %s: de %s a %s.", name, current.value, wanted.value
        )

    def _check_secret(self, secret: str | None) -> None:
        if not self._vault.is_set():
            raise ToolLevelError(_NO_KEY)
        if (wait := self._vault.locked_for()) > 0:
            raise ToolLevelError(f"El nivel crítico está bloqueado. Probá de nuevo en {wait} s.")
        if not secret:
            raise ToolLevelError(_NEEDS_KEY)
        if not self._vault.verify(secret):
            raise ToolLevelError(_WRONG_KEY)

    @staticmethod
    def _fixed(tool: Tool) -> bool:
        return tool.level >= PermissionLevel.FORBIDDEN

    @staticmethod
    def _lowest(tool: Tool) -> PermissionLevel:
        # Una acción graduada (la terminal) decide su nivel por pedido y nunca baja del
        # suyo: no se puede dejar que corra sin confirmación.
        return tool.level if isinstance(tool, GradedTool) else PermissionLevel.NORMAL
