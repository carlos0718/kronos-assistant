from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoVoices, demo_pipeline

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
COMMON = {"language": "es", "region": "Demo"}


@pytest.fixture
def voices() -> DemoVoices:
    return DemoVoices()


@pytest.fixture
def client(voices: DemoVoices) -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, demo_pipeline(0.01), voices)) as client:
        yield client


def test_las_voces_exigen_token(client: TestClient) -> None:
    assert client.get("/voices").status_code == 401
    assert client.put("/voices/current", json={"id": "demo-luis"}).status_code == 401
    assert client.post("/voices/demo-luis/preview").status_code == 401


def test_lista_las_voces_y_dice_cual_esta_en_uso(client: TestClient) -> None:
    response = client.get("/voices", headers=AUTH)

    assert response.status_code == 200
    assert response.json() == {
        "current": "demo-ana",
        "voices": [
            {**COMMON, "id": "demo-ana", "name": "Ana", "gender": "female"},
            {**COMMON, "id": "demo-luis", "name": "Luis", "gender": "male"},
        ],
    }


def test_elegir_una_voz_cambia_la_que_esta_en_uso(client: TestClient) -> None:
    response = client.put("/voices/current", json={"id": "demo-luis"}, headers=AUTH)

    assert response.status_code == 204
    assert client.get("/voices", headers=AUTH).json()["current"] == "demo-luis"


def test_elegir_una_voz_que_no_existe_devuelve_404(client: TestClient) -> None:
    response = client.put("/voices/current", json={"id": "nadie"}, headers=AUTH)

    assert response.status_code == 404
    assert client.get("/voices", headers=AUTH).json()["current"] == "demo-ana"


def test_probar_una_voz_la_hace_sonar(client: TestClient, voices: DemoVoices) -> None:
    assert client.post("/voices/demo-luis/preview", headers=AUTH).status_code == 204
    assert voices.previewed == ["demo-luis"]


def test_probar_una_voz_que_no_existe_devuelve_404(client: TestClient) -> None:
    assert client.post("/voices/nadie/preview", headers=AUTH).status_code == 404


def test_la_interfaz_puede_pedir_desde_su_origen(client: TestClient) -> None:
    # El navegador pregunta antes de mandar un pedido con token (CORS).
    response = client.options(
        "/voices",
        headers={
            "Origin": "http://localhost:1420",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:1420"


def test_otro_origen_no_recibe_permiso(client: TestClient) -> None:
    response = client.options(
        "/voices",
        headers={
            "Origin": "https://sitio-ajeno.example",
            "Access-Control-Request-Method": "GET",
            "Access-Control-Request-Headers": "authorization",
        },
    )

    assert "access-control-allow-origin" not in response.headers
