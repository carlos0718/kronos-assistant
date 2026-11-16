import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable, Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient
from starlette.testclient import WebSocketTestSession
from starlette.websockets import WebSocketDisconnect

from kronos_engine import PROTOCOL_VERSION
from kronos_engine.api.server import create_app
from kronos_engine.core.approval import ApprovalDesk, ApprovalRequest
from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import DEMO_REPLY, DEMO_TRANSCRIPT, DemoSpeaker, demo_pipeline

TOKEN = "token-de-prueba"
WS_URL = f"/ws?token={TOKEN}"


def make_client(demo_step_seconds: float) -> Iterator[TestClient]:
    # El bloque `with` mantiene un único bucle de eventos para todas las conexiones.
    with TestClient(create_app(TOKEN, demo_pipeline(demo_step_seconds))) as client:
        yield client


@pytest.fixture
def client() -> Iterator[TestClient]:
    yield from make_client(0.01)


@pytest.fixture
def slow_client() -> Iterator[TestClient]:
    yield from make_client(60)


def send(ws: WebSocketTestSession, type_: str) -> None:
    ws.send_json({"v": PROTOCOL_VERSION, "type": type_, "payload": {}})


def skip_greeting(ws: WebSocketTestSession) -> None:
    assert ws.receive_json()["type"] == "hello"
    assert ws.receive_json()["type"] == "state_changed"


def summary(msg: dict[str, Any]) -> tuple[str, str]:
    """Reduce un mensaje a (tipo, dato principal) para comparar secuencias."""
    payload = msg["payload"]
    return msg["type"], payload.get("state") or payload.get("text") or ""


DEMO_SEQUENCE = [
    ("state_changed", "listening"),
    ("transcript_final", DEMO_TRANSCRIPT),
    ("state_changed", "thinking"),
    ("state_changed", "speaking"),
    ("assistant_delta", DEMO_REPLY),
    ("state_changed", "listening"),  # Escucha por si el usuario sigue.
    ("state_changed", "idle"),
]


def test_health_exige_token(client: TestClient) -> None:
    assert client.get("/health").status_code == 401
    assert client.get("/health", headers={"Authorization": "Bearer otro"}).status_code == 401


def test_health_con_token(client: TestClient) -> None:
    response = client.get("/health", headers={"Authorization": f"Bearer {TOKEN}"})
    assert response.status_code == 200
    assert response.json()["protocol"] == PROTOCOL_VERSION


def test_ws_rechaza_token_invalido(client: TestClient) -> None:
    with pytest.raises(WebSocketDisconnect), client.websocket_connect("/ws?token=otro"):
        pass


def test_ws_saluda_con_el_estado_actual(client: TestClient) -> None:
    with client.websocket_connect(WS_URL) as ws:
        hello = ws.receive_json()
        assert hello["type"] == "hello"
        assert hello["v"] == PROTOCOL_VERSION
        assert ws.receive_json() == {
            "v": PROTOCOL_VERSION,
            "type": "state_changed",
            "payload": {"state": "idle"},
        }


def test_activate_recorre_el_ciclo_y_lo_difunde_a_todas_las_ventanas(client: TestClient) -> None:
    with client.websocket_connect(WS_URL) as overlay, client.websocket_connect(WS_URL) as settings:
        skip_greeting(overlay)
        skip_greeting(settings)

        send(overlay, "activate")

        for ws in (overlay, settings):
            assert [summary(ws.receive_json()) for _ in DEMO_SEQUENCE] == DEMO_SEQUENCE


def test_cancel_corta_el_ciclo(slow_client: TestClient) -> None:
    with slow_client.websocket_connect(WS_URL) as ws:
        skip_greeting(ws)

        send(ws, "activate")
        assert summary(ws.receive_json()) == ("state_changed", "listening")

        send(ws, "cancel")
        assert summary(ws.receive_json()) == ("state_changed", "idle")


class PatientListener:
    """Oye un pedido y después se queda esperando: la respuesta llega con un clic."""

    def __init__(self) -> None:
        self._heard = False

    async def listen(
        self,
        on_speech_end: Callable[[], Awaitable[None]] | None = None,
        wait_seconds: float | None = None,
    ) -> str | None:
        if self._heard:
            await asyncio.Event().wait()
        self._heard = True
        return "Cerrá Spotify"


class AskingResponder:
    def __init__(self, desk: ApprovalDesk) -> None:
        self._desk = desk

    async def respond(self, text: str) -> AsyncIterator[str]:
        approved = await self._desk.confirm(ApprovalRequest("close_app", "cerrar Spotify"))
        yield "Listo." if approved else "No lo hago."


def until(ws: WebSocketTestSession, type_: str) -> dict[str, Any]:
    """Lee mensajes hasta el primero de ese tipo y devuelve lo que trae."""
    while (msg := ws.receive_json())["type"] != type_:
        pass
    payload: dict[str, Any] = msg["payload"]
    return payload


@pytest.mark.parametrize(
    ("answer", "approved", "reply"), [("confirm", True, "Listo."), ("deny", False, "No lo hago.")]
)
def test_un_clic_en_la_interfaz_contesta_la_confirmacion(
    answer: str, approved: bool, reply: str
) -> None:
    desk = ApprovalDesk()
    pipeline = Pipeline(PatientListener(), AskingResponder(desk), DemoSpeaker(0), approvals=desk)
    with (
        TestClient(create_app(TOKEN, pipeline)) as client,
        client.websocket_connect(WS_URL) as ws,
    ):
        skip_greeting(ws)
        send(ws, "activate")
        request = until(ws, "confirmation_request")
        assert request == {"id": "1", "summary": "cerrar Spotify", "detail": ""}

        ws.send_json({"v": PROTOCOL_VERSION, "type": answer, "payload": {"id": request["id"]}})

        assert until(ws, "confirmation_resolved") == {"id": "1", "approved": approved}
        assert until(ws, "assistant_delta") == {"text": reply}
        send(ws, "cancel")
        assert until(ws, "state_changed")["state"] in {"listening", "idle"}


def test_mensaje_desconocido_devuelve_error(client: TestClient) -> None:
    with client.websocket_connect(WS_URL) as ws:
        skip_greeting(ws)
        send(ws, "no_existe")
        assert ws.receive_json()["type"] == "error"
