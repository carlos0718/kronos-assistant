"""Aplicación FastAPI del motor.

Todo acceso exige el token que la app de escritorio le pasa al motor al
arrancarlo. El servidor solo escucha en 127.0.0.1.
"""

import secrets
from typing import Any

from fastapi import (
    Depends,
    FastAPI,
    Header,
    HTTPException,
    WebSocket,
    WebSocketDisconnect,
    status,
)

from kronos_engine import PROTOCOL_VERSION, __version__
from kronos_engine.core.conversation import Conversation, Pipeline
from kronos_engine.core.demo import demo_pipeline

# Código de cierre de WebSocket para "política violada" (token inválido).
WS_POLICY_VIOLATION = 1008


def message(type_: str, payload: dict[str, Any] | None = None) -> dict[str, Any]:
    """Arma un mensaje del protocolo motor ↔ interfaz."""
    return {"v": PROTOCOL_VERSION, "type": type_, "payload": payload or {}}


class Hub:
    """Estado del asistente compartido por todas las ventanas conectadas."""

    def __init__(self, pipeline: Pipeline) -> None:
        self.state = "idle"
        self._clients: set[WebSocket] = set()
        self.conversation = Conversation(pipeline, self.set_state, self.emit)

    async def join(self, websocket: WebSocket) -> None:
        self._clients.add(websocket)
        await websocket.send_json(message("hello", {"engine_version": __version__}))
        await websocket.send_json(message("state_changed", {"state": self.state}))

    def leave(self, websocket: WebSocket) -> None:
        self._clients.discard(websocket)

    async def broadcast(self, msg: dict[str, Any]) -> None:
        for client in list(self._clients):
            try:
                await client.send_json(msg)
            except (RuntimeError, WebSocketDisconnect):  # La ventana ya se cerró.
                self._clients.discard(client)

    async def emit(self, type_: str, payload: dict[str, Any]) -> None:
        await self.broadcast(message(type_, payload))

    async def set_state(self, state: str) -> None:
        self.state = state
        await self.emit("state_changed", {"state": state})


def create_app(token: str, pipeline: Pipeline | None = None) -> FastAPI:
    """Crea el servidor. Sin `pipeline` usa las piezas simuladas."""
    app = FastAPI(title="Kronos Engine", version=__version__, docs_url=None, redoc_url=None)
    hub = Hub(pipeline or demo_pipeline())

    def token_ok(candidate: str | None) -> bool:
        return candidate is not None and secrets.compare_digest(candidate, token)

    def require_token(authorization: str | None = Header(default=None)) -> None:
        scheme, _, value = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token_ok(value):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")

    @app.get("/health", dependencies=[Depends(require_token)])
    def health() -> dict[str, Any]:
        return {"status": "ok", "version": __version__, "protocol": PROTOCOL_VERSION}

    @app.websocket("/ws")
    async def ws(websocket: WebSocket, token: str | None = None) -> None:
        # El navegador no permite cabeceras propias en WebSocket: el token va en la URL.
        if not token_ok(token):
            await websocket.close(code=WS_POLICY_VIOLATION)
            return

        await websocket.accept()
        await hub.join(websocket)
        try:
            async for incoming in websocket.iter_json():
                type_ = incoming.get("type") if isinstance(incoming, dict) else None
                if type_ == "activate":
                    await hub.conversation.activate()
                elif type_ == "cancel":
                    await hub.conversation.cancel()
                else:
                    error = {"message": f"Mensaje no reconocido: {type_!r}"}
                    await websocket.send_json(message("error", error))
        finally:
            hub.leave(websocket)

    return app
