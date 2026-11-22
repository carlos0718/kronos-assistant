from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoRecognizer
from kronos_engine.core.recognizer import DEFAULT_RECOGNIZER, ELEVENLABS, RECOGNIZERS

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def recognizer() -> DemoRecognizer:
    return DemoRecognizer()


@pytest.fixture
def client(recognizer: DemoRecognizer) -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, recognizer=recognizer)) as client:
        yield client


def test_exige_token(client: TestClient) -> None:
    assert client.get("/recognizer").status_code == 401
    assert client.put("/recognizer", json={"model": ELEVENLABS}).status_code == 401


def test_sin_elegir_nada_informa_el_de_fabrica_y_los_que_hay(client: TestClient) -> None:
    body = client.get("/recognizer", headers=AUTH).json()

    assert body == {"model": DEFAULT_RECOGNIZER, "models": list(RECOGNIZERS), "has_key": False}


def test_lo_que_se_elige_se_vuelve_a_leer(client: TestClient, recognizer: DemoRecognizer) -> None:
    assert client.put("/recognizer", headers=AUTH, json={"model": ELEVENLABS}).status_code == 204

    assert client.get("/recognizer", headers=AUTH).json()["model"] == ELEVENLABS
    assert recognizer.get() == ELEVENLABS


def test_rechaza_un_reconocedor_desconocido(client: TestClient) -> None:
    response = client.put("/recognizer", headers=AUTH, json={"model": "loro"})

    assert response.status_code == 422
    assert "desconocido" in response.json()["detail"]
