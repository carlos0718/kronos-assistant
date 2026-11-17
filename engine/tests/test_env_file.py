import os
from pathlib import Path

import pytest

from kronos_engine.config.env_file import load_env_file


@pytest.fixture(autouse=True)
def clean_env(monkeypatch: pytest.MonkeyPatch) -> None:
    for name in ("PRUEBA_A", "PRUEBA_B", "PRUEBA_C"):
        monkeypatch.delenv(name, raising=False)


def write(tmp_path: Path, text: str, encoding: str = "utf-8") -> Path:
    path = tmp_path / ".env"
    path.write_text(text, encoding=encoding)
    return path


def test_suma_las_variables_del_archivo(tmp_path: Path) -> None:
    load_env_file(write(tmp_path, "PRUEBA_A=uno\nPRUEBA_B = dos\n"))

    assert os.environ["PRUEBA_A"] == "uno"
    assert os.environ["PRUEBA_B"] == "dos"


def test_saca_las_comillas_del_valor(tmp_path: Path) -> None:
    load_env_file(write(tmp_path, "PRUEBA_A=\"uno\"\nPRUEBA_B='dos'\n"))

    assert os.environ["PRUEBA_A"] == "uno"
    assert os.environ["PRUEBA_B"] == "dos"


def test_las_variables_ya_puestas_ganan(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PRUEBA_A", "de la terminal")

    load_env_file(write(tmp_path, "PRUEBA_A=del archivo\n"))

    assert os.environ["PRUEBA_A"] == "de la terminal"


def test_ignora_comentarios_y_lineas_sin_igual(tmp_path: Path) -> None:
    load_env_file(write(tmp_path, "# PRUEBA_A=no\n\nPRUEBA_B\nPRUEBA_C=si\n"))

    assert "PRUEBA_A" not in os.environ
    assert "PRUEBA_B" not in os.environ
    assert os.environ["PRUEBA_C"] == "si"


def test_lee_la_primera_variable_aunque_el_archivo_tenga_marca_de_utf8(tmp_path: Path) -> None:
    load_env_file(write(tmp_path, "PRUEBA_A=uno\n", encoding="utf-8-sig"))

    assert os.environ["PRUEBA_A"] == "uno"


def test_sin_archivo_no_hace_nada(tmp_path: Path) -> None:
    load_env_file(tmp_path / "no-existe.env")

    assert "PRUEBA_A" not in os.environ
