from pathlib import Path

import pytest

from kronos_engine.config.folder_access import StoredFolderAccess
from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.folder_access import FolderAccess, FolderAccessError
from kronos_engine.core.platform import Folder


def test_sin_elegir_nada_puede_mirar_las_carpetas_conocidas(tmp_path: Path) -> None:
    assert StoredFolderAccess(SettingsStore(tmp_path / "config.toml")).get() == FolderAccess()


def test_lo_elegido_queda_guardado(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    projects = tmp_path / "proyectos"
    projects.mkdir()
    chosen = FolderAccess(frozenset({Folder.DESKTOP, Folder.DOCUMENTS}), (projects,), 2)

    StoredFolderAccess(SettingsStore(path)).set(chosen)

    # Otro objeto sobre el mismo archivo: es lo que pasa al reiniciar el motor.
    assert StoredFolderAccess(SettingsStore(path)).get() == chosen


def test_no_guarda_una_carpeta_que_no_existe(tmp_path: Path) -> None:
    access = StoredFolderAccess(SettingsStore(tmp_path / "config.toml"))

    with pytest.raises(FolderAccessError, match="No existe"):
        access.set(FolderAccess(extra=(tmp_path / "no-esta",)))

    assert access.get() == FolderAccess()


def test_una_carpeta_que_desaparecio_se_conserva(tmp_path: Path) -> None:
    # Un disco desconectado no le borra la carpeta elegida al usuario.
    path = tmp_path / "config.toml"
    path.write_text('folders_extra = ["Z:\\\\proyectos"]\n', encoding="utf-8")

    assert StoredFolderAccess(SettingsStore(path)).get().extra == (Path(r"Z:\proyectos"),)
