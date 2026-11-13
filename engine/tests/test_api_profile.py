from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.profile import ABOUT_MAX, NAME_MAX
from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoProfile

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def profile() -> DemoProfile:
    return DemoProfile()


@pytest.fixture
def client(profile: DemoProfile) -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, profile=profile)) as client:
        yield client


def test_exige_token(client: TestClient) -> None:
    assert client.get("/profile").status_code == 401
    assert client.put("/profile", json={"name": "a", "about": "b"}).status_code == 401


def test_sin_perfil_devuelve_textos_vacios(client: TestClient) -> None:
    assert client.get("/profile", headers=AUTH).json() == {"name": "", "about": ""}


def test_lo_que_se_guarda_se_vuelve_a_leer(client: TestClient) -> None:
    body = {"name": "Carlos", "about": "Programo y me gusta correr."}

    assert client.put("/profile", headers=AUTH, json=body).status_code == 204
    assert client.get("/profile", headers=AUTH).json() == body


def test_quita_los_espacios_de_los_bordes(client: TestClient) -> None:
    client.put("/profile", headers=AUTH, json={"name": "  Carlos ", "about": "\nhola\n"})

    assert client.get("/profile", headers=AUTH).json() == {"name": "Carlos", "about": "hola"}


@pytest.mark.parametrize(
    "body",
    [
        {"name": "x" * (NAME_MAX + 1), "about": ""},
        {"name": "", "about": "x" * (ABOUT_MAX + 1)},
        {"name": "Carlos"},
    ],
)
def test_rechaza_un_perfil_demasiado_largo_o_incompleto(
    client: TestClient, body: dict[str, str]
) -> None:
    assert client.put("/profile", headers=AUTH, json=body).status_code == 422
