import sys
import uuid
from collections.abc import Iterator

import pytest

from kronos_engine.platform.windows.credentials import WindowsCredentials

pytestmark = pytest.mark.skipif(
    sys.platform != "win32", reason="Usa el Administrador de credenciales"
)


@pytest.fixture
def name() -> Iterator[str]:
    # Un nombre que no choca con nada del usuario, y que se borra al terminar.
    name = f"Kronos-prueba/{uuid.uuid4()}"
    yield name
    WindowsCredentials().delete(name)


def test_lo_que_se_guarda_se_vuelve_a_leer(name: str) -> None:
    credentials = WindowsCredentials()

    credentials.write(name, "sk-ant-api03-ñandú-" + "x" * 100)

    assert credentials.read(name) == "sk-ant-api03-ñandú-" + "x" * 100


def test_guardar_otra_vez_reemplaza_la_clave(name: str) -> None:
    credentials = WindowsCredentials()
    credentials.write(name, "vieja")

    credentials.write(name, "nueva")

    assert credentials.read(name) == "nueva"


def test_una_clave_que_no_existe_se_lee_como_nada(name: str) -> None:
    assert WindowsCredentials().read(name) is None


def test_borrar_quita_la_clave_y_borrar_dos_veces_no_falla(name: str) -> None:
    credentials = WindowsCredentials()
    credentials.write(name, "secreta")

    credentials.delete(name)
    credentials.delete(name)

    assert credentials.read(name) is None
