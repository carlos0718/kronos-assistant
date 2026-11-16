"""Le pregunta al usuario si aprueba una acción delicada, por voz y en pantalla.

Kronos hace la pregunta en voz alta y la interfaz la muestra con dos botones.
Vale lo primero que llegue: un sí o un no dichos con claridad, o un clic.
"""

import asyncio
import contextlib
import logging
from collections.abc import Awaitable, Callable
from typing import Any

from kronos_engine.core.approval import ApprovalRequest, parse_answer
from kronos_engine.core.protocol import AssistantState, ServerMessage

log = logging.getLogger(__name__)

# Cuánto se espera a que el usuario empiece a contestar. Si no contesta, es un no.
ANSWER_WAIT_SECONDS = 15.0
# Cuántas veces se vuelve a escuchar si lo que se oyó no fue un sí ni un no.
ANSWER_ATTEMPTS = 3
# El reconocedor entiende mal las respuestas de una sola palabra: por eso se
# pide una más larga para aprobar. Para negar alcanza con cualquier cosa.
HOW_TO_ANSWER = "Respondé «sí, confirmo» o «no»."

Listen = Callable[[float], Awaitable[str | None]]
AskAloud = Callable[[str], Awaitable[None]]
SetState = Callable[[AssistantState], Awaitable[None]]
Emit = Callable[[ServerMessage, dict[str, Any]], Awaitable[None]]


class Confirmations:
    def __init__(self, listen: Listen, ask_aloud: AskAloud, set_state: SetState, emit: Emit):
        self._listen = listen
        self._ask_aloud = ask_aloud
        self._set_state = set_state
        self._emit = emit
        self._count = 0
        # La pregunta en curso: su identificador y dónde se anota el clic.
        self._pending: tuple[str, asyncio.Future[bool]] | None = None

    def answer(self, request_id: str, approved: bool) -> None:
        """El usuario contestó con un clic. Una respuesta a otra pregunta se ignora."""
        if self._pending is None:
            return
        pending_id, clicked = self._pending
        if request_id == pending_id and not clicked.done():
            clicked.set_result(approved)

    async def confirm(self, request: ApprovalRequest) -> bool:
        self._count += 1
        request_id = str(self._count)
        clicked: asyncio.Future[bool] = asyncio.get_running_loop().create_future()
        self._pending = (request_id, clicked)
        approved = False
        try:
            shown = {"id": request_id, "summary": request.summary, "detail": request.detail}
            await self._emit(ServerMessage.CONFIRMATION_REQUEST, shown)
            # El micrófono se abre cuando Kronos terminó de preguntar: si no, se oiría a sí mismo.
            await self._ask_aloud(f"¿Confirmás {request.summary}? {HOW_TO_ANSWER}")
            approved = await self._first_answer(clicked)
        finally:
            self._pending = None
            # También si el usuario cortó la conversación: la interfaz saca la pregunta.
            await self._emit(
                ServerMessage.CONFIRMATION_RESOLVED, {"id": request_id, "approved": approved}
            )
        await self._set_state(AssistantState.THINKING)
        return approved

    async def _first_answer(self, clicked: asyncio.Future[bool]) -> bool:
        hearing = asyncio.ensure_future(self._hear_answer())
        try:
            await asyncio.wait({hearing, clicked}, return_when=asyncio.FIRST_COMPLETED)
            # Si llegaron los dos a la vez, vale el clic: no depende de una transcripción.
            by_click = clicked.done()
            approved = clicked.result() if by_click else hearing.result()
            log.info(
                "Confirmación %s %s.",
                "aprobada" if approved else "rechazada",
                "con un clic" if by_click else "por voz",
            )
            return approved
        finally:
            hearing.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await hearing

    async def _hear_answer(self) -> bool:
        for attempt in range(ANSWER_ATTEMPTS):
            if attempt:
                # Sin este aviso, el usuario no sabe si Kronos lo oyó.
                await self._ask_aloud(f"No te entendí. {HOW_TO_ANSWER}")
            await self._set_state(AssistantState.LISTENING)
            text = await self._listen(ANSWER_WAIT_SECONDS)
            if text is None:
                log.info("Nadie contestó la confirmación en %g s: es un no.", ANSWER_WAIT_SECONDS)
                return False
            answer = parse_answer(text)
            if answer is not None:
                return answer
            # Queda cuánto se oyó, no qué: puede ser privado. El texto, solo al depurar.
            log.info("No quedó claro si fue un sí o un no (%d caracteres).", len(text))
            log.debug("Respuesta que no quedó clara: %r", text)
        log.info("No se entendió la respuesta a la confirmación: es un no.")
        return False
