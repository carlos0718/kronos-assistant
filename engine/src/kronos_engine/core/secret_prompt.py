"""Le pide al usuario que escriba la clave secreta, en la pantalla.

La clave se escribe y no se dicta: así no queda en la transcripción ni en el
historial, y nadie la oye. Viaja por el WebSocket local hasta quien la
pidió; no se registra ni se le muestra al modelo.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from kronos_engine.core.approval import ApprovalRequest
from kronos_engine.core.protocol import AssistantState, ServerMessage

log = logging.getLogger(__name__)

# Cuánto se espera a que el usuario escriba. Si no escribe, es un no.
WAIT_SECONDS = 60.0

AskAloud = Callable[[str], Awaitable[None]]
SetState = Callable[[AssistantState], Awaitable[None]]
Emit = Callable[[ServerMessage, dict[str, Any]], Awaitable[None]]


class SecretPrompts:
    def __init__(
        self,
        ask_aloud: AskAloud,
        set_state: SetState,
        emit: Emit,
        wait_seconds: float = WAIT_SECONDS,
    ) -> None:
        self._ask_aloud = ask_aloud
        self._set_state = set_state
        self._emit = emit
        self._wait_seconds = wait_seconds
        self._count = 0
        # El pedido en curso: su identificador y dónde llega lo que escribe el usuario.
        self._pending: tuple[str, asyncio.Future[str | None]] | None = None

    def answer(self, request_id: str, value: str | None) -> None:
        """El usuario escribió la clave (o canceló, con `None`). Si es de otro pedido, se ignora."""
        if self._pending is None:
            return
        pending_id, typed = self._pending
        if request_id == pending_id and not typed.done():
            typed.set_result(value or None)

    async def ask_secret(self, request: ApprovalRequest) -> str | None:
        self._count += 1
        request_id = str(self._count)
        typed: asyncio.Future[str | None] = asyncio.get_running_loop().create_future()
        self._pending = (request_id, typed)
        value: str | None = None
        try:
            shown = {"id": request_id, "summary": request.summary, "detail": request.detail}
            await self._emit(ServerMessage.SECRET_REQUEST, shown)
            await self._ask_aloud("Escribí tu clave secreta en la pantalla.")
            value = await asyncio.wait_for(typed, self._wait_seconds)
        except TimeoutError:
            log.info("Nadie escribió la clave secreta en %g s: es un no.", self._wait_seconds)
        finally:
            self._pending = None
            # También si el usuario cortó la conversación: la interfaz saca el pedido.
            await self._emit(ServerMessage.SECRET_RESOLVED, {"id": request_id})
        await self._set_state(AssistantState.THINKING)
        return value
