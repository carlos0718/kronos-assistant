import asyncio
from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DEMO_REPLY, demo_pipeline
from kronos_engine.core.standby import Standby

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
WS_URL = f"/ws?token={TOKEN}"


class FakeWakeWord:
    """Oye el nombre una sola vez, si está configurada para oírlo."""

    def __init__(self, hears: str | None = None) -> None:
        self._hears = hears
        self.waits = 0

    async def wait(self) -> str:
        self.waits += 1
        if self._hears is None or self.waits > 1:
            await asyncio.Event().wait()
        return self._hears or ""


def make_client(wake: FakeWakeWord, enabled: bool, remember: Any = None) -> Iterator[TestClient]:
    standby = Standby(wake, enabled=enabled, remember=remember)
    with TestClient(create_app(TOKEN, demo_pipeline(0.01), standby=standby)) as client:
        yield client


@pytest.fixture
def remembered() -> list[bool]:
    return []


@pytest.fixture
def client(remembered: list[bool]) -> Iterator[TestClient]:
    yield from make_client(FakeWakeWord(), enabled=False, remember=remembered.append)


def test_exige_token(client: TestClient) -> None:
    assert client.get("/wake-word").status_code == 401
    assert client.put("/wake-word", json={"enabled": True}).status_code == 401


def test_informa_si_esta_encendida(client: TestClient) -> None:
    assert client.get("/wake-word", headers=AUTH).json() == {"enabled": False}


def test_encenderla_la_deja_encendida_y_la_recuerda(
    client: TestClient, remembered: list[bool]
) -> None:
    response = client.put("/wake-word", headers=AUTH, json={"enabled": True})

    assert response.status_code == 204
    assert client.get("/wake-word", headers=AUTH).json() == {"enabled": True}
    assert remembered == [True]


def test_rechaza_un_valor_que_no_es_si_o_no(client: TestClient) -> None:
    assert client.put("/wake-word", headers=AUTH, json={"enabled": "tal vez"}).status_code == 422


def test_oir_el_nombre_con_un_pedido_empieza_la_conversacion_y_lo_responde() -> None:
    wake = FakeWakeWord(hears="¿estás ahí?")
    seen: list[tuple[str, str]] = []
    for client in make_client(wake, enabled=False):
        with client.websocket_connect(WS_URL) as ws:
            assert ws.receive_json()["type"] == "hello"
            assert ws.receive_json()["type"] == "state_changed"
            # Se enciende con la ventana ya conectada, para no perder ningún mensaje.
            client.put("/wake-word", headers=AUTH, json={"enabled": True})
            while ("state_changed", "listening") not in seen:
                msg = ws.receive_json()
                payload = msg["payload"]
                seen.append((msg["type"], payload.get("state") or payload.get("text") or ""))

    assert seen == [
        ("transcript_final", "¿estás ahí?"),
        ("state_changed", "thinking"),
        ("state_changed", "speaking"),
        ("assistant_delta", DEMO_REPLY),
        ("state_changed", "listening"),
    ]
