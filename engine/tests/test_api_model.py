from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoModel
from kronos_engine.core.model_choice import ANTHROPIC, ANTHROPIC_MODELS, ModelChoice

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}


@pytest.fixture
def model() -> DemoModel:
    return DemoModel()


@pytest.fixture
def client(model: DemoModel) -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, model=model)) as client:
        yield client


def test_exige_token(client: TestClient) -> None:
    assert client.get("/model").status_code == 401
    assert client.put("/model", json={"provider": "ollama", "model": ""}).status_code == 401
    assert client.put("/model/key", json={"provider": ANTHROPIC, "key": "x"}).status_code == 401


def test_de_fabrica_responde_ollama_y_ofrece_los_modelos_de_claude(client: TestClient) -> None:
    assert client.get("/model", headers=AUTH).json() == {
        "provider": "ollama",
        "model": "",
        "models": list(ANTHROPIC_MODELS),
        "has_key": False,
    }


def test_la_eleccion_se_guarda(client: TestClient, model: DemoModel) -> None:
    chosen = {"provider": ANTHROPIC, "model": "claude-haiku-5-5"}

    assert client.put("/model", headers=AUTH, json=chosen).status_code == 204

    assert model.get() == ModelChoice(ANTHROPIC, "claude-haiku-5-5")
    assert client.get("/model", headers=AUTH).json()["model"] == "claude-haiku-5-5"


@pytest.mark.parametrize(
    "chosen",
    [{"provider": "openai", "model": ""}, {"provider": ANTHROPIC, "model": "claude-2"}],
)
def test_rechaza_lo_que_no_existe(client: TestClient, chosen: dict[str, str]) -> None:
    assert client.put("/model", headers=AUTH, json=chosen).status_code == 422


def test_la_clave_se_guarda_pero_nunca_se_devuelve(client: TestClient, model: DemoModel) -> None:
    sent = {"provider": ANTHROPIC, "key": "sk-ant-secreta"}

    assert client.put("/model/key", headers=AUTH, json=sent).status_code == 204

    assert model.key(ANTHROPIC) == "sk-ant-secreta"
    read = client.get("/model", headers=AUTH)
    assert read.json()["has_key"] is True
    assert "sk-ant-secreta" not in read.text


def test_una_clave_vacia_la_borra(client: TestClient, model: DemoModel) -> None:
    model.set_key(ANTHROPIC, "sk-ant-secreta")

    client.put("/model/key", headers=AUTH, json={"provider": ANTHROPIC, "key": ""})

    assert client.get("/model", headers=AUTH).json()["has_key"] is False


def test_ollama_no_lleva_clave(client: TestClient) -> None:
    sent = {"provider": "ollama", "key": "algo"}

    assert client.put("/model/key", headers=AUTH, json=sent).status_code == 422


def test_rechaza_una_clave_enorme(client: TestClient) -> None:
    sent = {"provider": ANTHROPIC, "key": "x" * 5000}

    assert client.put("/model/key", headers=AUTH, json=sent).status_code == 422
