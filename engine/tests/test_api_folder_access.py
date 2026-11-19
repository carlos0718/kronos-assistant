from collections.abc import Iterator
from pathlib import Path
from typing import Any

import pytest
from fastapi.testclient import TestClient

from kronos_engine.api.server import create_app
from kronos_engine.core.demo import DemoFolderAccess
from kronos_engine.core.folder_access import DEFAULT_DEPTH, MAX_DEPTH, FolderAccess
from kronos_engine.core.platform import Folder

TOKEN = "token-de-prueba"
AUTH = {"Authorization": f"Bearer {TOKEN}"}
ALL = [folder.value for folder in Folder]


@pytest.fixture
def access() -> DemoFolderAccess:
    return DemoFolderAccess()


@pytest.fixture
def client(access: DemoFolderAccess) -> Iterator[TestClient]:
    with TestClient(create_app(TOKEN, folder_access=access)) as client:
        yield client


def body(**changes: Any) -> dict[str, Any]:
    return {"known": ALL, "extra": [], "depth": DEFAULT_DEPTH, **changes}


def test_exige_token(client: TestClient) -> None:
    assert client.get("/folder-access").status_code == 401
    assert client.put("/folder-access", json=body()).status_code == 401


def test_sin_elegir_nada_informa_las_carpetas_de_fabrica(client: TestClient) -> None:
    assert client.get("/folder-access", headers=AUTH).json() == body()


def test_lo_que_se_guarda_se_vuelve_a_leer(
    client: TestClient, access: DemoFolderAccess, tmp_path: Path
) -> None:
    chosen = body(known=["desktop", "documents"], extra=[str(tmp_path)], depth=MAX_DEPTH)

    assert client.put("/folder-access", headers=AUTH, json=chosen).status_code == 204

    assert client.get("/folder-access", headers=AUTH).json() == chosen
    assert access.get() == FolderAccess(
        frozenset({Folder.DESKTOP, Folder.DOCUMENTS}), (tmp_path,), MAX_DEPTH
    )


def test_las_conocidas_salen_siempre_en_el_mismo_orden(client: TestClient) -> None:
    client.put("/folder-access", headers=AUTH, json=body(known=["videos", "desktop"]))

    assert client.get("/folder-access", headers=AUTH).json()["known"] == ["desktop", "videos"]


def test_una_carpeta_que_no_existe_se_rechaza_con_un_motivo(
    client: TestClient, tmp_path: Path
) -> None:
    response = client.put(
        "/folder-access", headers=AUTH, json=body(extra=[str(tmp_path / "no-esta")])
    )

    assert response.status_code == 422
    assert "No existe" in response.json()["detail"]


@pytest.mark.parametrize(
    "changes",
    [
        {"known": ["papelera"]},
        {"depth": 0},
        {"depth": MAX_DEPTH + 1},
        {"depth": 2.5},
        {"extra": r"D:\proyectos"},
    ],
)
def test_rechaza_lo_que_no_sirve(client: TestClient, changes: dict[str, Any]) -> None:
    assert client.put("/folder-access", headers=AUTH, json=body(**changes)).status_code == 422
