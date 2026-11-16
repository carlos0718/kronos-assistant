from collections.abc import Iterator
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoFollowUp
from kronos_engine.core.follow_up import DEFAULT_SECONDS, MAX_SECONDS

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def follow_up() -> DemoFollowUp:
    return DemoFollowUp()


@pytest.fixture
def client(follow_up: DemoFollowUp) -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, follow_up=follow_up)) as client:
        yield client


def test_exige_token(client: TestClient) -> None:
    assert client.get("/follow-up").status_code == 401
    assert client.put("/follow-up", json={"seconds": 5}).status_code == 401


def test_sin_elegir_nada_informa_la_espera_de_fabrica(client: TestClient) -> None:
    assert client.get("/follow-up", headers=AUTH).json() == {"seconds": DEFAULT_SECONDS}


def test_lo_que_se_guarda_se_vuelve_a_leer(client: TestClient, follow_up: DemoFollowUp) -> None:
    assert client.put("/follow-up", headers=AUTH, json={"seconds": 20}).status_code == 204

    assert client.get("/follow-up", headers=AUTH).json() == {"seconds": 20}
    assert follow_up.get() == 20


def test_acepta_cero_para_no_seguir_escuchando(client: TestClient) -> None:
    assert client.put("/follow-up", headers=AUTH, json={"seconds": 0}).status_code == 204
    assert client.get("/follow-up", headers=AUTH).json() == {"seconds": 0}


@pytest.mark.parametrize("seconds", [-1, MAX_SECONDS + 1, 2.5, "mucho", None])
def test_rechaza_una_espera_fuera_de_rango(client: TestClient, seconds: Any) -> None:
    assert client.put("/follow-up", headers=AUTH, json={"seconds": seconds}).status_code == 422
