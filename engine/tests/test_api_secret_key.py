from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoSecretKey

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
GOOD = "una-clave-larga"


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, secret_key=DemoSecretKey())) as client:
        yield client


def test_exige_token(client: TestClient) -> None:
    assert client.get("/secret-key").status_code == 401
    assert client.put("/secret-key", json={"new": GOOD}).status_code == 401
    assert client.post("/secret-key/remove", json={"current": GOOD}).status_code == 401


def test_al_principio_no_hay_clave(client: TestClient) -> None:
    assert client.get("/secret-key", headers=AUTH).json() == {"is_set": False, "locked_for": 0}


def test_se_pone_la_primera_clave_sin_pedir_otra(client: TestClient) -> None:
    assert client.put("/secret-key", headers=AUTH, json={"new": GOOD}).status_code == 204
    assert client.get("/secret-key", headers=AUTH).json()["is_set"] is True


def test_la_respuesta_nunca_trae_la_clave(client: TestClient) -> None:
    client.put("/secret-key", headers=AUTH, json={"new": GOOD})

    assert GOOD not in client.get("/secret-key", headers=AUTH).text


def test_cambiarla_pide_la_actual(client: TestClient) -> None:
    client.put("/secret-key", headers=AUTH, json={"new": GOOD})

    wrong = client.put(
        "/secret-key", headers=AUTH, json={"current": "otra-clave-larga", "new": "nueva-clave"}
    )
    missing = client.put("/secret-key", headers=AUTH, json={"new": "nueva-clave"})
    right = client.put("/secret-key", headers=AUTH, json={"current": GOOD, "new": "nueva-clave"})

    assert wrong.status_code == 422
    assert missing.status_code == 422
    assert right.status_code == 204


def test_una_clave_corta_se_rechaza_con_el_motivo(client: TestClient) -> None:
    response = client.put("/secret-key", headers=AUTH, json={"new": "corta"})

    assert response.status_code == 422
    assert "al menos" in response.json()["detail"]


def test_borrarla_pide_la_actual(client: TestClient) -> None:
    client.put("/secret-key", headers=AUTH, json={"new": GOOD})

    wrong = client.post("/secret-key/remove", headers=AUTH, json={"current": "otra-clave-larga"})
    right = client.post("/secret-key/remove", headers=AUTH, json={"current": GOOD})

    assert wrong.status_code == 422
    assert right.status_code == 204
    assert client.get("/secret-key", headers=AUTH).json()["is_set"] is False
