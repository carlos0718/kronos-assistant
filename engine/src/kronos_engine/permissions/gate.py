"""Decide si una acción que propone el modelo se ejecuta.

Es código, no modelo: un texto malicioso puede convencer al modelo de pedir
cualquier cosa, pero no de saltarse este control.
"""

import logging
from collections.abc import Sequence

from kronos_engine.core.tools import PermissionLevel, Tool, ToolCall, ToolError, ToolSpec

log = logging.getLogger(__name__)

# Lo que recibe el modelo cuando la acción no se ejecuta. Se lo cuenta al usuario.
_UNKNOWN = "Esa acción no existe. No se ejecutó nada."
_FORBIDDEN = "Esa acción está prohibida y no se ejecuta nunca. No se ejecutó nada."
# PROVISORIO: la confirmación (nivel 2) y la clave secreta (nivel 3) llegan en
# los próximos cambios de la Fase 2. Hasta entonces, lo que las pide se rechaza.
_NEEDS_APPROVAL = (
    "Esa acción necesita la aprobación del usuario y Kronos todavía no puede pedirla. "
    "No se ejecutó nada."
)
_FAILED = "La acción falló por un error inesperado."


class PermissionGate:
    """Las acciones del motor, detrás del control de permisos."""

    def __init__(self, tools: Sequence[Tool]) -> None:
        self._tools = {tool.spec.name: tool for tool in tools}

    def specs(self) -> list[ToolSpec]:
        # Lo prohibido ni se le ofrece al modelo.
        return [
            tool.spec for tool in self._tools.values() if tool.level < PermissionLevel.FORBIDDEN
        ]

    async def run(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            return self._reject(call, "no existe", _UNKNOWN)
        if tool.level >= PermissionLevel.FORBIDDEN:
            return self._reject(call, "prohibida", _FORBIDDEN)
        if tool.level > PermissionLevel.NORMAL:
            return self._reject(call, f"nivel {tool.level.value}, sin aprobación", _NEEDS_APPROVAL)
        try:
            result = await tool.run(call.arguments)
        except ToolError as exc:
            log.info("Acción %s ejecutada: no se pudo hacer.", call.name)
            return f"No se pudo: {exc}"
        except Exception:
            # Un fallo de la acción no corta la conversación: el modelo lo cuenta.
            log.exception("Acción %s ejecutada: falló.", call.name)
            return _FAILED
        log.info("Acción %s ejecutada.", call.name)
        return result

    def _reject(self, call: ToolCall, reason: str, answer: str) -> str:
        # Queda qué acción fue, no con qué datos: pueden ser privados.
        log.info("Acción %s rechazada (%s).", call.name, reason)
        return answer
