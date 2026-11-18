import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from kronos_engine.core.platform import Folder
from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.folders import OpenFolderTool, find_folder


class FakeFolders:
    """Las carpetas del usuario, en una carpeta temporal del test."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self.opened: list[Path] = []
        for folder in Folder:
            (root / folder.value).mkdir()

    def folder_path(self, folder: Folder) -> Path:
        return self._root / folder.value

    def open_path(self, path: Path) -> None:
        self.opened.append(path)


@pytest.fixture
def folders(tmp_path: Path) -> FakeFolders:
    return FakeFolders(tmp_path)


def run(folders: FakeFolders, **arguments: Any) -> str:
    return asyncio.run(OpenFolderTool(folders).run(arguments))


def make(folders: FakeFolders, folder: Folder, *names: str) -> Path:
    path = folders.folder_path(folder).joinpath(*names)
    path.mkdir(parents=True)
    return path


def fails(folders: FakeFolders, arguments: Mapping[str, Any]) -> str:
    with pytest.raises(ToolError) as error:
        asyncio.run(OpenFolderTool(folders).run(arguments))
    assert folders.opened == []
    return str(error.value)


def test_encuentra_las_carpetas_del_usuario_por_su_nombre() -> None:
    assert find_folder("Documentos") == Folder.DOCUMENTS
    assert find_folder("Descargas") == Folder.DOWNLOADS
    assert find_folder("Escritorio") == Folder.DESKTOP
    assert find_folder("Imágenes") == Folder.PICTURES
    assert find_folder("Música") == Folder.MUSIC
    assert find_folder("Videos") == Folder.VIDEOS


def test_entiende_otros_nombres_de_la_misma_carpeta() -> None:
    assert find_folder("fotos") == Folder.PICTURES
    assert find_folder("vídeos") == Folder.VIDEOS
    assert find_folder("Downloads") == Folder.DOWNLOADS
    assert find_folder("carpeta personal") == Folder.HOME


def test_no_importan_las_palabras_de_relleno() -> None:
    # Así lo pidió el usuario en una prueba con micrófono.
    assert find_folder("la sección Documentos") == Folder.DOCUMENTS
    assert find_folder("mis documentos") == Folder.DOCUMENTS
    assert find_folder("la carpeta de descargas") == Folder.DOWNLOADS
    # El modelo a veces copia una aclaración entre paréntesis como parte del nombre.
    assert find_folder("Imágenes (las fotos)") == Folder.PICTURES


def test_tolera_un_error_chico_de_transcripcion() -> None:
    assert find_folder("descarga") == Folder.DOWNLOADS
    assert find_folder("imagenes") == Folder.PICTURES
    assert find_folder("documento") == Folder.DOCUMENTS
    # Se parece a «Videos» y a «Vídeos»: son dos nombres de la misma carpeta, no una duda.
    assert find_folder("video") == Folder.VIDEOS


def test_no_inventa_una_carpeta_que_no_conoce() -> None:
    assert find_folder("Proyectos") is None
    assert find_folder("carpeta") is None
    assert find_folder("") is None


def test_abre_la_carpeta_pedida_sin_pedir_permiso(folders: FakeFolders) -> None:
    result = run(folders, folder="documentos")

    assert OpenFolderTool.level == PermissionLevel.NORMAL
    assert folders.opened == [folders.folder_path(Folder.DOCUMENTS)]
    assert result.startswith("Se abrió la carpeta Documentos.")


def test_la_carpeta_personal_se_nombra_como_tal(folders: FakeFolders) -> None:
    assert run(folders, folder="mi usuario").startswith("Se abrió tu carpeta personal.")


def test_entra_a_una_subcarpeta(folders: FakeFolders) -> None:
    workspace = make(folders, Folder.DESKTOP, "Workspace")

    result = run(folders, folder="escritorio", subfolders=["workspace"])

    assert folders.opened == [workspace]
    assert result.startswith("Se abrió la carpeta Workspace, en Escritorio.")


def test_baja_varias_subcarpetas_aunque_el_nombre_tenga_guiones(folders: FakeFolders) -> None:
    project = make(folders, Folder.DESKTOP, "Workspace", "kronos-ai-assistant")

    run(folders, folder="Escritorio", subfolders=["Workspace", "kronos ai assistant"])

    assert folders.opened == [project]


def test_tolera_un_nombre_partido_o_con_un_error(folders: FakeFolders) -> None:
    workspace = make(folders, Folder.DESKTOP, "Workspace")

    run(folders, folder="Escritorio", subfolders=["Work Space"])
    run(folders, folder="Escritorio", subfolders=["workspase"])

    assert folders.opened == [workspace, workspace]


def test_sin_decir_donde_la_busca_en_las_carpetas_del_usuario(folders: FakeFolders) -> None:
    workspace = make(folders, Folder.DESKTOP, "Workspace")
    make(folders, Folder.DOCUMENTS, "Facturas")

    result = run(folders, subfolders=["Workspace"])

    assert folders.opened == [workspace]
    assert result.startswith("Se abrió la carpeta Workspace, en Escritorio.")


def test_si_esta_en_dos_carpetas_pregunta_cual(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "Fotos viejas")
    make(folders, Folder.DOCUMENTS, "Fotos viejas")

    message = fails(folders, {"subfolders": ["fotos viejas"]})

    assert "Escritorio" in message
    assert "Documentos" in message


def test_no_cuenta_lo_que_hay_adentro_si_no_hace_falta(folders: FakeFolders) -> None:
    # El modelo repite en voz alta lo que recibe: una lista de carpetas cansa.
    make(folders, Folder.DESKTOP, "Workspace", "kronos-ai-assistant")

    result = run(folders, folder="Escritorio", subfolders=["Workspace"])

    assert "kronos" not in result


def test_si_la_subcarpeta_no_existe_dice_cuales_hay(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "Workspace")
    make(folders, Folder.DESKTOP, "Juegos")

    message = fails(folders, {"folder": "Escritorio", "subfolders": ["Proyectos"]})

    assert "«Proyectos»" in message
    assert "Juegos, Workspace" in message


def test_no_abre_archivos_ni_carpetas_ocultas(folders: FakeFolders) -> None:
    desktop = folders.folder_path(Folder.DESKTOP)
    (desktop / "notas").write_text("no es una carpeta")
    (desktop / ".git").mkdir()

    fails(folders, {"folder": "Escritorio", "subfolders": ["notas"]})
    fails(folders, {"folder": "Escritorio", "subfolders": [".git"]})


def test_no_sale_de_las_carpetas_del_usuario(folders: FakeFolders, tmp_path: Path) -> None:
    desktop = folders.folder_path(Folder.DESKTOP)
    make(folders, Folder.DESKTOP, "Workspace")

    fails(folders, {"folder": "Escritorio", "subfolders": [".."]})
    fails(folders, {"folder": "Escritorio", "subfolders": [str(tmp_path)]})
    # Los signos no cuentan: a lo sumo queda «Workspace», que está adentro.
    run(folders, folder="Escritorio", subfolders=["Workspace/../.."])

    assert folders.opened == [desktop / "Workspace"]


def test_si_no_conoce_la_carpeta_dice_cuales_puede_abrir(folders: FakeFolders) -> None:
    message = fails(folders, {"folder": "Proyectos"})

    assert "«Proyectos»" in message
    assert "Documentos, Descargas" in message


def test_sin_nombre_no_abre_nada(folders: FakeFolders) -> None:
    fails(folders, {})
    fails(folders, {"subfolders": []})


def test_el_modelo_sabe_cuales_puede_abrir() -> None:
    description = OpenFolderTool.spec.description

    for name in ("Escritorio", "Documentos", "Descargas", "Imágenes", "Música", "Videos"):
        assert name in description
    assert "carpeta personal" in description


def test_describe_lo_que_va_a_abrir(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "Workspace")
    tool = OpenFolderTool(folders)

    assert asyncio.run(tool.describe({"folder": "descargas"})) == "abrir la carpeta Descargas"
    assert (
        asyncio.run(tool.describe({"subfolders": ["Workspace"]}))
        == "abrir la carpeta Workspace, en Escritorio"
    )


def test_si_no_esta_justo_ahi_la_busca_mas_adentro(folders: FakeFolders) -> None:
    # El modelo dijo «del escritorio» y la carpeta estaba en Escritorio\workspace.
    portfolio = make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")

    result = run(folders, folder="Escritorio", subfolders=["Portfolio master"])

    assert folders.opened == [portfolio]
    assert result.startswith("Se abrió la carpeta Portfolio-master, en workspace.")


def test_si_es_la_unica_con_esa_palabra_alcanza(folders: FakeFolders) -> None:
    # El usuario la recordaba como «Portfolio Web».
    portfolio = make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")
    make(folders, Folder.DESKTOP, "workspace", "react-basic-project")

    run(folders, folder="Escritorio", subfolders=["Portfolio Web"])
    run(folders, subfolders=["portfolio web"])

    assert folders.opened == [portfolio, portfolio]


def test_con_dos_que_comparten_la_palabra_no_adivina(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")
    make(folders, Folder.DESKTOP, "workspace", "Portfolio-viejo")

    fails(folders, {"folder": "Escritorio", "subfolders": ["Portfolio Web"]})


def test_una_coincidencia_exacta_le_gana_a_una_suelta(folders: FakeFolders) -> None:
    workspace = make(folders, Folder.DESKTOP, "Workspace")
    make(folders, Folder.DOCUMENTS, "cursos", "workspace viejo")

    run(folders, subfolders=["Workspace"])

    assert folders.opened == [workspace]


def test_no_busca_demasiado_adentro(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "a", "b", "c", "d", "Escondida")

    fails(folders, {"folder": "Escritorio", "subfolders": ["Escondida"]})


def test_si_el_modelo_adivina_mal_el_lugar_la_busca_en_las_demas(folders: FakeFolders) -> None:
    # Sin que el usuario dijera dónde, el modelo supuso «Documentos».
    portfolio = make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")

    run(folders, folder="Documentos", subfolders=["Portfolio master"])

    assert folders.opened == [portfolio]


def test_si_el_nombre_no_coincide_exacto_pide_decir_el_real(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")

    guessed = run(folders, folder="Escritorio", subfolders=["Portfolio Web"])
    exact = run(folders, folder="Escritorio", subfolders=["portfolio master"])

    assert "«Portfolio Web»" in guessed
    assert "«Portfolio-master»" in guessed
    assert "exactamente" not in exact
