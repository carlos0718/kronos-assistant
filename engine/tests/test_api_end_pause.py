from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoEndPause
from kronos_engine.core.end_pause import DEFAULT_MS, MAX_MS, MIN_MS

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def end_pause() -> DemoEndPause:
    return DemoEndPause()


@pytest.fixture
def client(end_pause: DemoEndPause) -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, end_pause=end_pause)) as client:
        yield client


def test_exige_token(client: TestClient) -> None:
    assert client.get("/end-pause").status_code == 401
    assert client.put("/end-pause", json={"milliseconds": 2000}).status_code == 401


def test_sin_elegir_nada_informa_la_pausa_de_fabrica(client: TestClient) -> None:
    assert client.get("/end-pause", headers=AUTH).json() == {"milliseconds": DEFAULT_MS}


def test_lo_que_se_guarda_se_vuelve_a_leer(client: TestClient, end_pause: DemoEndPause) -> None:
    assert client.put("/end-pause", headers=AUTH, json={"milliseconds": 2500}).status_code == 204

    assert client.get("/end-pause", headers=AUTH).json() == {"milliseconds": 2500}
    assert end_pause.get() == 2500


@pytest.mark.parametrize("milliseconds", [MIN_MS, MAX_MS])
def test_acepta_los_extremos_del_rango(client: TestClient, milliseconds: int) -> None:
    body = {"milliseconds": milliseconds}

    assert client.put("/end-pause", headers=AUTH, json=body).status_code == 204


@pytest.mark.parametrize("milliseconds", [0, MIN_MS - 1, MAX_MS + 1, 1500.5, "mucho", None])
def test_rechaza_una_pausa_fuera_de_rango(client: TestClient, milliseconds: Any) -> None:
    body = {"milliseconds": milliseconds}

    assert client.put("/end-pause", headers=AUTH, json=body).status_code == 422
