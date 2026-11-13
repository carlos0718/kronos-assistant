"""Aplicación FastAPI del motor.

Todo acceso exige el token que la app de escritorio le pasa al motor al
arrancarlo. El servidor solo escucha en 127.0.0.1.
"""

import secrets
from typing import Any

from fastapi import Depends, FastAPI, Header, HTTPException, WebSocket, status
from fastapi.middleware.cors import CORSMiddleware

from kronos_engine import PROTOCOL_VERSION, __version__
from kronos_engine.api.hub import Hub, message
from kronos_engine.api.voices import voices_router
from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import DemoVoices, demo_pipeline
from kronos_engine.core.protocol import ClientMessage, ServerMessage
from kronos_engine.core.voices import VoiceControl

# Código de cierre de WebSocket para "política violada" (token inválido).
WS_POLICY_VIOLATION = 1008

# Desde dónde carga la interfaz: el servidor de desarrollo de Vite y la app
# instalada. El navegador exige este permiso para los pedidos HTTP; el acceso
# lo sigue decidiendo el token.
UI_ORIGINS = [
    "http://localhost:1420",
    "http://tauri.localhost",
    "https://tauri.localhost",
    "tauri://localhost",
]


def create_app(
    token: str, pipeline: Pipeline | None = None, voices: VoiceControl | None = None
) -> FastAPI:
    """Crea el servidor. Sin `pipeline` o sin `voices` usa las piezas simuladas."""
    app = FastAPI(title="Kronos Engine", version=__version__, docs_url=None, redoc_url=None)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=UI_ORIGINS,
        allow_methods=["GET", "PUT", "POST"],
        allow_headers=["Authorization", "Content-Type"],
    )
    hub = Hub(pipeline or demo_pipeline())

    def token_ok(candidate: str | None) -> bool:
        return candidate is not None and secrets.compare_digest(candidate, token)

    def require_token(authorization: str | None = Header(default=None)) -> None:
        scheme, _, value = (authorization or "").partition(" ")
        if scheme.lower() != "bearer" or not token_ok(value):
            raise HTTPException(status.HTTP_401_UNAUTHORIZED, "Token inválido")

    app.include_router(voices_router(voices or DemoVoices(), require_token))

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
                if type_ == ClientMessage.ACTIVATE:
                    await hub.conversation.activate()
                elif type_ == ClientMessage.CANCEL:
                    await hub.conversation.cancel()
                else:
                    error = {"message": f"Mensaje no reconocido: {type_!r}"}
                    await websocket.send_json(message(ServerMessage.ERROR, error))
        finally:
            hub.leave(websocket)

    return app
