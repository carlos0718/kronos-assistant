"""Estado del asistente compartido por todas las ventanas conectadas."""

import contextlib
from collections.abc import AsyncIterator
from typing import Any

from fastapi import WebSocket, WebSocketDisconnect

from kronos_engine import PROTOCOL_VERSION, __version__
from kronos_engine.core.conversation import Conversation, Pipeline
from kronos_engine.core.protocol import AssistantState, ServerMessage
from kronos_engine.core.standby import Standby


def message(type_: ServerMessage, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Arma un mensaje del protocolo motor ↔ interfaz."""
    return {"v": PROTOCOL_VERSION, "type": type_, "payload": payload or {}}


class Hub:
    def __init__(self, pipeline: Pipeline, standby: Standby) -> None:
        self.state = AssistantState.IDLE
        self._clients: set[WebSocket] = set()
        self.conversation = Conversation(pipeline, self.set_state, self.emit)
        self.standby = standby
        # Oír el nombre empieza una conversación, igual que el atajo.
        standby.connect(self.conversation.activate)

    @contextlib.asynccontextmanager
    async def lifespan(self, _app: object) -> AsyncIterator[None]:
        """Lo que dura el servidor: Kronos arranca inactivo y ya puede esperar su nombre."""
        self.standby.resume()
        try:
            yield
        finally:
            self.standby.pause()

    async def join(self, websocket: WebSocket) -> None:
        self._clients.add(websocket)
        hello = {"engine_version": __version__}
        await websocket.send_json(message(ServerMessage.HELLO, hello))
        await websocket.send_json(message(ServerMessage.STATE_CHANGED, {"state": self.state}))

    def leave(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        for client in list(self._clients):
            try:
                await client.send_json(msg)
            except (RuntimeError, WebSocketDisconnect):  # La ventana ya se cerró.
                self._clients.discard(client)

    async def emit(self, type_: ServerMessage, payload: dict[str, Any]) -> None:
        await self.broadcast(message(type_, payload))

    async def set_state(self, state: AssistantState) -> None:
        self.state = state
        # El nombre solo se espera en reposo: al conversar, el micrófono es de la conversación.
        if state is AssistantState.IDLE:
            self.standby.resume()
        else:
            self.standby.pause()
        await self.emit(ServerMessage.STATE_CHANGED, {"state": state})
