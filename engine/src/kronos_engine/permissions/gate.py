"""Decide si una acción que propone el modelo se ejecuta.

Es código, no modelo: un texto malicioso puede convencer al modelo de pedir
cualquier cosa, pero no de saltarse este control.
"""

import logging
from collections.abc import Sequence

from kronos_engine.core.approval import ApprovalRequest, Approver, SecretAsker
from kronos_engine.core.secret import SecretVault
from kronos_engine.core.tools import (
    GradedTool,
    PermissionLevel,
    Tool,
    ToolCall,
    ToolError,
    ToolSpec,
)

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
_NEEDS_SECRET = (
    "Esa acción necesita la clave secreta y Kronos no puede pedirla. No se ejecutó nada."
)
_NO_SECRET_SET = (
    "Esa acción necesita la clave secreta y no hay una clave secreta configurada. "
    "Decile al usuario que la cree en la pestaña Permisos. No se ejecutó nada."
)
_LOCKED = (
    "El nivel crítico está bloqueado por intentos fallidos con la clave secreta. "
    "No se ejecutó nada."
)
_WRONG_SECRET = "La clave secreta no fue correcta. No se ejecutó nada."
_NO_SECRET_GIVEN = "El usuario no dio la clave secreta. No se ejecutó nada."
_FAILED = "La acción falló por un error inesperado."


class PermissionGate:
    """Las acciones del motor, detrás del control de permisos."""

    def __init__(
        self,
        tools: Sequence[Tool],
        approver: Approver | None = None,
        vault: SecretVault | None = None,
        secret_asker: SecretAsker | None = None,
    ) -> None:
        self._tools = {tool.spec.name: tool for tool in tools}
        self._approver = approver
        self._vault = vault
        self._secret_asker = secret_asker

    def specs(self) -> list[ToolSpec]:
        # Lo prohibido ni se le ofrece al modelo.
        return [
            tool.spec for tool in self._tools.values() if tool.level < PermissionLevel.FORBIDDEN
        ]

    @staticmethod
    def _level(tool: Tool, call: ToolCall) -> PermissionLevel:
        # El nivel de fábrica es el piso: una acción graduada solo puede subirlo.
        if isinstance(tool, GradedTool):
            return max(tool.level, tool.level_for(call.arguments))
        return tool.level

    @staticmethod
    def _detail(tool: Tool, call: ToolCall) -> str:
        return tool.detail_for(call.arguments) if isinstance(tool, GradedTool) else ""

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
            # El motivo puede nombrar archivos o carpetas del usuario: solo con KRONOS_DEBUG=1.
            log.debug("Motivo: %s", exc)
            return f"No se pudo: {exc}"
        except Exception:
            # Un fallo de la acción no corta la conversación: el modelo lo cuenta.
            log.exception("Acción %s ejecutada: falló.", call.name)
            return _FAILED
        log.info("Acción %s ejecutada.", call.name)
        return result

    async def _refusal(self, tool: Tool, call: ToolCall) -> str | None:
        """Por qué la acción no se ejecuta, o `None` si puede ejecutarse."""
        level = self._level(tool, call)
        if level >= PermissionLevel.FORBIDDEN:
            return self._reject(call, "prohibida", _FORBIDDEN)
        if level >= PermissionLevel.CRITICAL:
            return await self._secret_refusal(tool, call)
        if level >= PermissionLevel.SENSITIVE:
            if self._approver is None:
                return self._reject(call, "nivel 2, sin cómo pedir aprobación", _NO_APPROVER)
            try:
                summary = await tool.describe(call.arguments)
            except ToolError as exc:
                # Ya se sabe que no se puede: no se molesta al usuario con la pregunta.
                log.debug("Motivo: %s", exc)
                return self._reject(call, "no se puede hacer", f"No se pudo: {exc}")
            request = ApprovalRequest(call.name, summary, self._detail(tool, call))
            if not await self._approver.confirm(request):
                return self._reject(call, "el usuario no la aprobó", _DENIED)
            log.info("Acción %s aprobada por el usuario.", call.name)
        return None

    async def _secret_refusal(self, tool: Tool, call: ToolCall) -> str | None:
        """El nivel 3 solo se ejecuta con la clave secreta, comprobada acá y no por el modelo."""
        if self._vault is None or self._secret_asker is None:
            return self._reject(call, "nivel 3, sin cómo pedir la clave", _NEEDS_SECRET)
        if not self._vault.is_set():
            return self._reject(call, "nivel 3, sin clave configurada", _NO_SECRET_SET)
        if self._vault.locked_for() > 0:
            return self._reject(call, "nivel 3, bloqueado", _LOCKED)
        try:
            summary = await tool.describe(call.arguments)
        except ToolError as exc:
            log.debug("Motivo: %s", exc)
            return self._reject(call, "no se puede hacer", f"No se pudo: {exc}")
        typed = await self._secret_asker.ask_secret(
            ApprovalRequest(call.name, summary, self._detail(tool, call))
        )
        if not typed:
            return self._reject(call, "el usuario no dio la clave", _NO_SECRET_GIVEN)
        if not self._vault.verify(typed):
            return self._reject(call, "clave secreta incorrecta", _WRONG_SECRET)
        log.info("Acción %s autorizada con la clave secreta.", call.name)
        return None

    def _reject(self, call: ToolCall, reason: str, answer: str) -> str:
        # Queda qué acción fue, no con qué datos: pueden ser privados.
        log.info("Acción %s rechazada (%s).", call.name, reason)
        return answer
