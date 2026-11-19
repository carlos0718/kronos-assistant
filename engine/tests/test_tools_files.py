import asyncio
from collections.abc import Sequence
from pathlib import Path
from typing import Any

import pytest

from kronos_engine.core.folder_access import FolderAccess
from kronos_engine.core.platform import Folder
from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.files import OpenFileTool


class FakeFiles:
    """Las carpetas del usuario, en una carpeta temporal del test."""

    def __init__(self, root: Path) -> None:
        self._root = root
        self.opened: list[Path] = []
        for folder in Folder:
            (root / folder.value).mkdir()

    def folder_path(self, folder: Folder) -> Path:
        return self._root / folder.value

    def open_path(self, path: Path) -> None:
        raise AssertionError("Se pidió abrir un archivo, no una carpeta.")

    def open_file(self, path: Path) -> None:
        self.opened.append(path)


class FakeChooser:
    def __init__(self, pick: str | None = None) -> None:
        self._pick = pick
        self.options: list[str] = []

    async def choose(self, wanted: str, options: Sequence[str]) -> int | None:
        self.options = list(options)
        if self._pick is None:
            return None
        return next(i for i, option in enumerate(options) if option.startswith(self._pick))


@pytest.fixture
def files(tmp_path: Path) -> FakeFiles:
    return FakeFiles(tmp_path)


def put(files: FakeFiles, folder: Folder, *names: str) -> Path:
    path = files.folder_path(folder).joinpath(*names)
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text("contenido", encoding="utf-8")
    return path


def run(
    files: FakeFiles,
    access: FolderAccess | None = None,
    chooser: FakeChooser | None = None,
    **arguments: Any,
) -> str:
    tool = OpenFileTool(files, lambda: access or FolderAccess(), chooser)
    return asyncio.run(tool.run(arguments))


def test_es_una_accion_normal(files: FakeFiles) -> None:
    assert OpenFileTool(files).level == PermissionLevel.NORMAL


def test_abre_un_archivo_por_su_nombre_sin_decir_donde_esta(files: FakeFiles) -> None:
    report = put(files, Folder.DOCUMENTS, "Informe de ventas.pdf")

    result = run(files, file="informe de ventas")

    assert files.opened == [report]
    assert "Informe de ventas.pdf" in result


def test_lo_encuentra_en_una_subcarpeta(files: FakeFiles) -> None:
    resume = put(files, Folder.DOCUMENTS, "Trabajo", "2026", "Curriculum.docx")

    run(files, file="curriculum")

    assert files.opened == [resume]


def test_tolera_un_error_de_transcripcion(files: FakeFiles) -> None:
    resume = put(files, Folder.DOCUMENTS, "Curriculum.pdf")

    run(files, file="curriculun")

    assert files.opened == [resume]


def test_con_la_carpeta_dicha_busca_ahi(files: FakeFiles) -> None:
    put(files, Folder.DOCUMENTS, "CV.pdf")
    downloaded = put(files, Folder.DOWNLOADS, "CV.pdf")

    run(files, file="CV", folder="Descargas")

    assert files.opened == [downloaded]


def test_el_nombre_con_la_extension_tambien_vale(files: FakeFiles) -> None:
    notes = put(files, Folder.DESKTOP, "notas.txt")

    run(files, file="notas.txt")

    assert files.opened == [notes]


def test_si_hay_dos_con_el_mismo_nombre_pregunta_cual(files: FakeFiles) -> None:
    put(files, Folder.DOCUMENTS, "CV.pdf")
    put(files, Folder.DOCUMENTS, "CV.docx")

    with pytest.raises(ToolError, match=r"CV\.pdf") as error:
        run(files, file="CV")

    assert "Preguntale" in str(error.value)
    assert files.opened == []


def test_si_esta_en_dos_carpetas_pregunta_cual(files: FakeFiles) -> None:
    put(files, Folder.DOCUMENTS, "CV.pdf")
    put(files, Folder.DOWNLOADS, "CV.pdf")

    with pytest.raises(ToolError, match="Preguntale"):
        run(files, file="CV")


@pytest.mark.parametrize("name", ["instalador.exe", "limpiar.bat", "script.ps1", "planilla.xlsm"])
def test_no_abre_programas_scripts_ni_documentos_con_macros(files: FakeFiles, name: str) -> None:
    put(files, Folder.DOWNLOADS, name)

    with pytest.raises(ToolError, match="no abre programas"):
        run(files, file=Path(name).stem)

    assert files.opened == []


def test_si_hay_un_documento_y_un_programa_con_el_mismo_nombre_abre_el_documento(
    files: FakeFiles,
) -> None:
    put(files, Folder.DOWNLOADS, "manual.exe")
    manual = put(files, Folder.DOWNLOADS, "manual.pdf")

    run(files, file="manual")

    assert files.opened == [manual]


def test_no_busca_en_las_carpetas_que_el_usuario_no_permitio(files: FakeFiles) -> None:
    put(files, Folder.DOWNLOADS, "secreto.pdf")
    access = FolderAccess(frozenset({Folder.DOCUMENTS}))

    with pytest.raises(ToolError):
        run(files, access, file="secreto")

    assert files.opened == []


def test_si_no_lo_encuentra_por_el_nombre_lo_elige_por_el_significado(files: FakeFiles) -> None:
    resume = put(files, Folder.DOCUMENTS, "CV-Ana-2026.pdf")
    put(files, Folder.DOCUMENTS, "factura-luz.pdf")
    chooser = FakeChooser("CV-Ana-2026.pdf")

    result = run(files, chooser=chooser, file="mi hoja de vida")

    assert files.opened == [resume]
    # El usuario tiene que saber qué se abrió de verdad.
    assert "CV-Ana-2026.pdf" in result
    # Al modelo no se le ofrecen programas.
    assert all(".exe" not in option for option in chooser.options)


def test_si_no_lo_encuentra_lo_dice(files: FakeFiles) -> None:
    put(files, Folder.DOCUMENTS, "factura.pdf")

    with pytest.raises(ToolError, match="tesis"):
        run(files, chooser=FakeChooser(), file="la tesis")


def test_sin_nombre_no_abre_nada(files: FakeFiles) -> None:
    with pytest.raises(ToolError, match="Falta"):
        run(files, file="  ")


def test_describe_que_archivo_abriria(files: FakeFiles) -> None:
    put(files, Folder.DOCUMENTS, "Presupuesto.xlsx")
    tool = OpenFileTool(files)

    assert asyncio.run(tool.describe({"file": "presupuesto"})) == "abrir «Presupuesto.xlsx»"
