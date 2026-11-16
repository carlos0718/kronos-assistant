"""Decide si una acción que propone el modelo se ejecuta.

Es código, no modelo: un texto malicioso puede convencer al modelo de pedir
cualquier cosa, pero no de saltarse este control.
"""

import logging
from collections.abc import Sequence

from kronos_engine.core.approval import ApprovalRequest, Approver
from kronos_engine.core.tools import PermissionLevel, Tool, ToolCall, ToolError, ToolSpec

log = logging.getLogger(__name__)

# Lo que recibe el modelo cuando la acción no se ejecuta. Se lo cuenta al usuario.
_UNKNOWN = "Esa acción no existe. No se ejecutó nada."
_FORBIDDEN = "Esa acción está prohibida y no se ejecuta nunca. No se ejecutó nada."
_DENIED = (
    "Ya se le preguntó al usuario y contestó que no. No se ejecutó nada. "
    "Decí en una frase que no lo hiciste y no vuelvas a preguntar."
)
_NO_APPROVER = (
    "Esa acción necesita la aprobación del usuario y no hay cómo pedirla. No se ejecutó nada."
)
# PROVISORIO: la clave secreta (nivel 3) llega en el próximo cambio de la
# Fase 2. Hasta entonces, lo que la pide se rechaza.
_NEEDS_SECRET = (
    "Esa acción necesita la clave secreta y Kronos todavía no puede pedirla. No se ejecutó nada."
)
_FAILED = "La acción falló por un error inesperado."


class PermissionGate:
    """Las acciones del motor, detrás del control de permisos."""

    def __init__(self, tools: Sequence[Tool], approver: Approver | None = None) -> None:
        self._tools = {tool.spec.name: tool for tool in tools}
        self._approver = approver

    def specs(self) -> list[ToolSpec]:
        # Lo prohibido ni se le ofrece al modelo.
        return [
            tool.spec for tool in self._tools.values() if tool.level < PermissionLevel.FORBIDDEN
        ]

    async def run(self, call: ToolCall) -> str:
        tool = self._tools.get(call.name)
        if tool is None:
            return self._reject(call, "no existe", _UNKNOWN)
        if refusal := await self._refusal(tool, call):
            return refusal
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

    async def _refusal(self, tool: Tool, call: ToolCall) -> str | None:
        """Por qué la acción no se ejecuta, o `None` si puede ejecutarse."""
        if tool.level >= PermissionLevel.FORBIDDEN:
            return self._reject(call, "prohibida", _FORBIDDEN)
        if tool.level >= PermissionLevel.CRITICAL:
            return self._reject(call, "nivel 3, sin clave secreta", _NEEDS_SECRET)
        if tool.level >= PermissionLevel.SENSITIVE:
            if self._approver is None:
                return self._reject(call, "nivel 2, sin cómo pedir aprobación", _NO_APPROVER)
            try:
                summary = await tool.describe(call.arguments)
            except ToolError as exc:
                # Ya se sabe que no se puede: no se molesta al usuario con la pregunta.
                return self._reject(call, "no se puede hacer", f"No se pudo: {exc}")
            request = ApprovalRequest(call.name, summary)
            if not await self._approver.confirm(request):
                return self._reject(call, "el usuario no la aprobó", _DENIED)
            log.info("Acción %s aprobada por el usuario.", call.name)
        return None

    def _reject(self, call: ToolCall, reason: str, answer: str) -> str:
        # Queda qué acción fue, no con qué datos: pueden ser privados.
        log.info("Acción %s rechazada (%s).", call.name, reason)
        return answer
