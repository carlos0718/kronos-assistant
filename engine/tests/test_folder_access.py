from pathlib import Path

import pytest

from kronos_engine.core.folder_access import (
    MAX_DEPTH,
    MIN_DEPTH,
    FolderAccess,
    FolderAccessError,
    checked,
)


def test_sin_cambios_lo_que_ya_sirve(tmp_path: Path) -> None:
    access = FolderAccess(extra=(tmp_path,), depth=2)

    assert checked(access) == access


def test_no_repite_la_misma_carpeta(tmp_path: Path) -> None:
    access = FolderAccess(extra=(tmp_path, tmp_path / ".", Path(str(tmp_path) + "/")))

    assert checked(access).extra == (tmp_path,)


def test_rechaza_una_ruta_relativa() -> None:
    with pytest.raises(FolderAccessError, match="ruta completa"):
        checked(FolderAccess(extra=(Path("proyectos"),)))


def test_rechaza_un_archivo(tmp_path: Path) -> None:
    notes = tmp_path / "notas.txt"
    notes.write_text("no es una carpeta")

    with pytest.raises(FolderAccessError, match="No existe"):
        checked(FolderAccess(extra=(notes,)))


@pytest.mark.parametrize("depth", [MIN_DEPTH - 1, MAX_DEPTH + 1])
def test_rechaza_niveles_fuera_de_rango(depth: int) -> None:
    with pytest.raises(FolderAccessError):
        checked(FolderAccess(depth=depth))
