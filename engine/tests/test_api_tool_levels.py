from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def client() -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN)) as client:
        yield client


def level_of(client: TestClient, name: str) -> int:
    actions = client.get("/tool-levels", headers=AUTH).json()
    return int(next(action["level"] for action in actions if action["name"] == name))


def test_exige_token(client: TestClient) -> None:
    assert client.get("/tool-levels").status_code == 401
    assert client.put("/tool-levels/open_app", json={"level": 2}).status_code == 401


def test_lista_las_acciones_con_su_nivel(client: TestClient) -> None:
    actions = client.get("/tool-levels", headers=AUTH).json()

    open_app = next(action for action in actions if action["name"] == "open_app")
    assert open_app == {
        "name": "open_app",
        "label": "Abrir aplicaciones",
        "factory": 1,
        "level": 1,
        "lowest": 1,
        "fixed": False,
    }


def test_se_cambia_el_nivel(client: TestClient) -> None:
    assert client.put("/tool-levels/open_app", headers=AUTH, json={"level": 2}).status_code == 204

    assert level_of(client, "open_app") == 2


def test_un_nivel_que_no_se_puede_se_explica(client: TestClient) -> None:
    response = client.put("/tool-levels/run_command", headers=AUTH, json={"level": 1})

    assert response.status_code == 422
    assert "va de 2 a 3" in response.json()["detail"]


def test_una_accion_que_no_existe_es_un_error_claro(client: TestClient) -> None:
    response = client.put("/tool-levels/explotar", headers=AUTH, json={"level": 2})

    assert response.status_code == 422
    assert "no existe" in response.json()["detail"]


def test_el_nivel_tiene_que_ser_un_entero(client: TestClient) -> None:
    for bad in (2.5, "2", None):
        response = client.put("/tool-levels/open_app", headers=AUTH, json={"level": bad})
        assert response.status_code == 422


def test_bajar_del_nivel_3_pide_la_clave_y_la_respuesta_no_la_repite(client: TestClient) -> None:
    client.put("/tool-levels/open_app", headers=AUTH, json={"level": 3})

    wrong = client.put("/tool-levels/open_app", headers=AUTH, json={"level": 1, "secret": "x-mala"})
    assert wrong.status_code == 422
    assert "x-mala" not in wrong.text

    good = client.put(
        "/tool-levels/open_app", headers=AUTH, json={"level": 1, "secret": "clave-de-prueba"}
    )
    assert good.status_code == 204
