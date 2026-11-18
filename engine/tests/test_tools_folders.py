import asyncio

import pytest

from kronos_engine.core.platform import Folder
from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.folders import OpenFolderTool, find_folder


class FakeFolders:
    def __init__(self) -> None:
        self.opened: list[Folder] = []

    def open_folder(self, folder: Folder) -> None:
        self.opened.append(folder)


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


def test_abre_la_carpeta_pedida_sin_pedir_permiso() -> None:
    folders = FakeFolders()
    tool = OpenFolderTool(folders)

    result = asyncio.run(tool.run({"name": "documentos"}))

    assert tool.level == PermissionLevel.NORMAL
    assert folders.opened == [Folder.DOCUMENTS]
    assert result == "Se abrió la carpeta Documentos."


def test_la_carpeta_personal_se_nombra_como_tal() -> None:
    result = asyncio.run(OpenFolderTool(FakeFolders()).run({"name": "mi usuario"}))

    assert result == "Se abrió tu carpeta personal."


def test_si_no_la_conoce_dice_cuales_puede_abrir_y_no_abre_nada() -> None:
    folders = FakeFolders()

    with pytest.raises(ToolError) as error:
        asyncio.run(OpenFolderTool(folders).run({"name": "Proyectos"}))

    assert folders.opened == []
    assert "«Proyectos»" in str(error.value)
    assert "Documentos, Descargas" in str(error.value)


def test_sin_nombre_no_abre_nada() -> None:
    folders = FakeFolders()

    with pytest.raises(ToolError):
        asyncio.run(OpenFolderTool(folders).run({}))

    assert folders.opened == []


def test_el_modelo_sabe_cuales_puede_abrir() -> None:
    description = OpenFolderTool.spec.description

    for name in ("Escritorio", "Documentos", "Descargas", "Imágenes", "Música", "Videos"):
        assert name in description
    assert "carpeta personal" in description


def test_describe_lo_que_va_a_abrir() -> None:
    describe = OpenFolderTool(FakeFolders()).describe({"name": "descargas"})

    assert asyncio.run(describe) == "abrir la carpeta Descargas"
