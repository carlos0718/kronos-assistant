import asyncio
import sys
from collections.abc import Mapping, Sequence
from pathlib import Path
from typing import Any

import pytest

from kronos_engine.core.folder_access import FolderAccess
from kronos_engine.core.platform import Folder
from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.folder_search import find_folder
from kronos_engine.tools.folders import OpenFolderTool


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


class FakeChooser:
    """Elige la opción que empieza con `pick`, como lo haría el modelo; sin `pick`, ninguna."""

    def __init__(self, pick: str | None = None) -> None:
        self._pick = pick
        self.wanted = ""
        self.options: list[str] = []

    async def choose(self, wanted: str, options: Sequence[str]) -> int | None:
        self.wanted, self.options = wanted, list(options)
        if self._pick is None:
            return None
        return next(i for i, option in enumerate(options) if option.startswith(self._pick))


def tool(
    folders: FakeFolders, access: FolderAccess | None = None, chooser: FakeChooser | None = None
) -> OpenFolderTool:
    return OpenFolderTool(folders, lambda: access or FolderAccess(), chooser)


def run(
    folders: FakeFolders,
    access: FolderAccess | None = None,
    chooser: FakeChooser | None = None,
    **arguments: Any,
) -> str:
    return asyncio.run(tool(folders, access, chooser).run(arguments))


def make(folders: FakeFolders, folder: Folder, *names: str) -> Path:
    path = folders.folder_path(folder).joinpath(*names)
    path.mkdir(parents=True)
    return path


def fails(
    folders: FakeFolders,
    arguments: Mapping[str, Any],
    access: FolderAccess | None = None,
    chooser: FakeChooser | None = None,
) -> str:
    with pytest.raises(ToolError) as error:
        asyncio.run(tool(folders, access, chooser).run(arguments))
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


def test_si_la_subcarpeta_no_existe_pide_preguntar_sin_dar_la_lista(
    folders: FakeFolders,
) -> None:
    make(folders, Folder.DESKTOP, "Workspace")
    make(folders, Folder.DESKTOP, "Juegos")

    message = fails(folders, {"folder": "Escritorio", "subfolders": ["Proyectos"]})

    assert "«Proyectos»" in message
    assert "Preguntale al usuario" in message
    # El modelo lee en voz alta las listas que recibe.
    assert "Juegos" not in message


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


def test_el_modelo_sabe_cuales_puede_abrir(folders: FakeFolders) -> None:
    description = tool(folders).spec.description

    for name in ("Escritorio", "Documentos", "Descargas", "Imágenes", "Música", "Videos"):
        assert name in description
    assert "carpeta personal" in description


def test_describe_lo_que_va_a_abrir(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "Workspace")
    opener = tool(folders)

    assert asyncio.run(opener.describe({"folder": "descargas"})) == "abrir la carpeta Descargas"
    assert (
        asyncio.run(opener.describe({"subfolders": ["Workspace"]}))
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


# Las carpetas que el usuario permite mirar, desde la pestaña Permisos.
ONLY_DESKTOP = FolderAccess(frozenset({Folder.DESKTOP}))


def test_no_abre_una_carpeta_conocida_sin_permiso(folders: FakeFolders) -> None:
    message = fails(folders, {"folder": "descargas"}, ONLY_DESKTOP)

    assert "Descargas" in message
    assert "Permisos" in message


def test_no_busca_en_las_carpetas_sin_permiso(folders: FakeFolders) -> None:
    make(folders, Folder.DOCUMENTS, "Facturas")

    chooser = FakeChooser()

    fails(folders, {"subfolders": ["Facturas"]}, ONLY_DESKTOP, chooser)

    # Tampoco la ofrece como parecida.
    assert not any("Facturas" in option for option in chooser.options)


def test_sin_ninguna_carpeta_permitida_lo_dice(folders: FakeFolders) -> None:
    nothing = FolderAccess(frozenset())

    assert "Permisos" in fails(folders, {"subfolders": ["Facturas"]}, nothing)
    assert "ninguna por ahora" in tool(folders, nothing).spec.description


class NestedFolders(FakeFolders):
    """Como en Windows: la carpeta personal contiene a las demás."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self.opened = []
        for folder in Folder:
            self.folder_path(folder).mkdir(parents=True, exist_ok=True)

    def folder_path(self, folder: Folder) -> Path:
        home = self._root / Folder.HOME.value
        return home if folder == Folder.HOME else home / folder.value


def test_una_carpeta_sin_permiso_no_se_alcanza_desde_la_personal(tmp_path: Path) -> None:
    nested = NestedFolders(tmp_path)
    make(nested, Folder.DOWNLOADS, "Facturas")
    access = FolderAccess(frozenset({Folder.HOME}))

    fails(nested, {"folder": "personal", "subfolders": ["downloads"]}, access)
    fails(nested, {"folder": "personal", "subfolders": ["Facturas"]}, access)


def test_abre_una_carpeta_que_sumo_el_usuario(folders: FakeFolders, tmp_path: Path) -> None:
    projects = tmp_path / "D" / "proyectos"
    kronos = projects / "kronos"
    kronos.mkdir(parents=True)
    access = FolderAccess(extra=(projects,))

    assert run(folders, access, folder="proyectos").startswith("Se abrió la carpeta proyectos.")
    assert run(folders, access, folder="proyectos", subfolders=["kronos"]).startswith(
        "Se abrió la carpeta kronos, en proyectos."
    )
    run(folders, access, subfolders=["kronos"])

    assert folders.opened == [projects, kronos, kronos]


def test_el_modelo_sabe_de_las_carpetas_que_sumo_el_usuario(
    folders: FakeFolders, tmp_path: Path
) -> None:
    access = FolderAccess(frozenset({Folder.DESKTOP}), (tmp_path / "proyectos",))

    description = tool(folders, access).spec.description

    assert "Escritorio y proyectos" in description
    assert "Documentos" not in description


def test_la_misma_carpeta_vista_desde_dos_lugares_no_es_una_duda(folders: FakeFolders) -> None:
    workspace = make(folders, Folder.DESKTOP, "workspace")
    portfolio = make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")
    access = FolderAccess(extra=(workspace,))

    run(folders, access, subfolders=["Portfolio-master"])
    run(folders, access, subfolders=["Portfolio Web"])

    assert folders.opened == [portfolio, portfolio]


def test_busca_tantos_niveles_como_eligio_el_usuario(folders: FakeFolders) -> None:
    hidden = make(folders, Folder.DESKTOP, "a", "b", "c", "d", "Escondida")
    make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")
    shallow = FolderAccess(depth=1)

    fails(folders, {"folder": "Escritorio", "subfolders": ["Portfolio master"]}, shallow)
    run(folders, FolderAccess(depth=5), folder="Escritorio", subfolders=["Escondida"])

    assert folders.opened == [hidden]


def test_no_entra_a_las_carpetas_que_arman_los_programas(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "web", "node_modules", "react")

    fails(folders, {"folder": "Escritorio", "subfolders": ["react"]})


def test_gana_la_palabra_que_tiene_una_sola_carpeta(folders: FakeFolders) -> None:
    # «proyecto» está en muchas; «kronos», en una sola.
    kronos = make(folders, Folder.DESKTOP, "workspace", "kronos-ai-assistant")
    for name in ("proyecto", "proyectos-js", "react-basic-project"):
        make(folders, Folder.DESKTOP, "workspace", name)

    run(folders, subfolders=["mi proyecto de Kronos"])

    assert folders.opened == [kronos]


def test_si_no_la_encuentra_la_elige_por_el_significado(folders: FakeFolders) -> None:
    # El usuario dijo «mi web personal» y se llama «Portfolio-master»: no comparten
    # ni una palabra, así que elige el modelo, por el significado.
    portfolio = make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")
    make(folders, Folder.DOCUMENTS, "Facturas")
    chooser = FakeChooser("Portfolio-master")

    result = run(folders, chooser=chooser, subfolders=["mi web personal"])

    assert folders.opened == [portfolio]
    assert chooser.wanted == "mi web personal"
    assert {"Portfolio-master (en workspace)", "Facturas (en Documentos)"} <= set(chooser.options)
    assert result.startswith("Se abrió la carpeta Portfolio-master, en workspace.")
    # El usuario tiene que saber que no se llamaba así.
    assert "«mi web personal»" in result


def test_si_el_modelo_no_elige_ninguna_pide_preguntar(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "workspace", "Portfolio-master")

    message = fails(folders, {"subfolders": ["la tesis"]}, chooser=FakeChooser())

    assert "Preguntale al usuario" in message
    assert "Portfolio" not in message


def test_solo_elige_por_el_significado_la_ultima_del_camino(folders: FakeFolders) -> None:
    make(folders, Folder.DESKTOP, "workspace", "Portfolio-master", "src")
    chooser = FakeChooser("Portfolio-master")

    fails(folders, {"subfolders": ["mi web personal", "src"]}, chooser=chooser)

    assert chooser.options == []


def test_las_parecidas_en_las_letras_se_ofrecen_primero(folders: FakeFolders) -> None:
    for number in range(40):
        make(folders, Folder.DOCUMENTS, f"proyecto-{number:02}")
    make(folders, Folder.PICTURES, "viajes", "Fotografías")
    chooser = FakeChooser()

    fails(folders, {"subfolders": ["fotos"]}, chooser=chooser)

    names = [option.split(" (")[0] for option in chooser.options]
    assert names.index("Fotografías") < names.index("proyecto-00")


def test_una_palabra_parecida_tiene_que_empezar_igual(folders: FakeFolders) -> None:
    # «ingles» y «finales» comparten casi todas las letras, pero no son la misma palabra.
    make(folders, Folder.DOWNLOADS, "docs", "proyectos-finales")

    fails(folders, {"subfolders": ["apuntes de inglés"]})


@pytest.mark.skipif(sys.platform != "win32", reason="los enlaces de carpeta son de Windows")
def test_un_enlace_a_una_carpeta_apagada_no_la_abre(folders: FakeFolders) -> None:
    # Windows deja en Documentos «Mis vídeos», un enlace oculto a Videos: con Videos
    # apagada, Kronos abría el enlace y el explorador decía «acceso denegado».
    import _winapi

    videos = folders.folder_path(Folder.VIDEOS)
    link = folders.folder_path(Folder.DOCUMENTS) / "Mis vídeos"
    _winapi.CreateJunction(str(videos), str(link))
    only_documents = FolderAccess(frozenset({Folder.DOCUMENTS}))

    fails(folders, {"folder": "Documentos", "subfolders": ["Mis vídeos"]}, only_documents)
    fails(folders, {"subfolders": ["vídeos"]}, only_documents)


@pytest.mark.skipif(sys.platform != "win32", reason="los enlaces de carpeta son de Windows")
def test_un_enlace_a_una_carpeta_permitida_se_puede_abrir(folders: FakeFolders) -> None:
    import _winapi

    target = make(folders, Folder.DESKTOP, "proyectos")
    link = folders.folder_path(Folder.DOCUMENTS) / "atajo a proyectos"
    _winapi.CreateJunction(str(target), str(link))

    assert "atajo a proyectos" in run(
        folders, folder="Documentos", subfolders=["atajo a proyectos"]
    )


def test_desde_la_carpeta_personal_no_entra_a_una_carpeta_apagada(tmp_path: Path) -> None:
    # Con Videos apagada, «la carpeta Videos de mi usuario» abría otra que se le parecía.
    folders = NestedFolders(tmp_path)
    make(folders, Folder.DOWNLOADS, "imagenes para videos")
    access = FolderAccess(frozenset({Folder.HOME, Folder.DOWNLOADS}))

    said = fails(folders, {"folder": "carpeta personal", "subfolders": ["Videos"]}, access)

    assert "permiso" in said


def test_una_carpeta_apagada_pedida_sin_decir_donde_avisa_y_nombra_las_otras(
    folders: FakeFolders,
) -> None:
    make(folders, Folder.DOCUMENTS, "Videos")
    access = FolderAccess(frozenset({Folder.DOCUMENTS, Folder.DOWNLOADS}))

    said = fails(folders, {"subfolders": ["Videos"]}, access)

    assert "permiso" in said
    assert "Documentos" in said
