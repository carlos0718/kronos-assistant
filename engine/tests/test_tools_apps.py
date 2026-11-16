import asyncio
from collections.abc import Sequence

import pytest

from kronos_engine.core.platform import App
from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.apps import OpenAppTool, find_app

NOTEPAD = App("Bloc de notas", "Microsoft.WindowsNotepad!App")
STICKY = App("Notas rápidas", "Microsoft.StickyNotes!App")
CHROME = App("Google Chrome", "Chrome")
REMOTE = App("Chrome Remote Desktop", "ChromeRemote")
SPOTIFY = App("Spotify", "Spotify!App")
UNINSTALL = App("Desinstalar Spotify", "Spotify!Uninstall")
CODE = App("Visual Studio Code", "Microsoft.VisualStudioCode")
APPS = [NOTEPAD, STICKY, CHROME, REMOTE, SPOTIFY, UNINSTALL, CODE]


class FakePlatform:
    def __init__(self, apps: Sequence[App] = APPS) -> None:
        self._apps = apps
        self.opened: list[App] = []

    def apps(self) -> Sequence[App]:
        return self._apps

    def open_app(self, app: App) -> None:
        self.opened.append(app)


def test_encuentra_la_aplicacion_por_su_nombre_exacto() -> None:
    assert find_app("Spotify", APPS) == SPOTIFY


def test_no_importan_las_mayusculas_ni_los_acentos() -> None:
    # La transcripción de voz no siempre acentúa ni usa mayúsculas.
    assert find_app("notas rapidas", APPS) == STICKY
    assert find_app("BLOC DE NOTAS.", APPS) == NOTEPAD


def test_alcanza_con_una_parte_del_nombre() -> None:
    assert find_app("code", APPS) == CODE
    assert find_app("visual studio", APPS) == CODE


def test_entre_varias_que_coinciden_gana_la_de_nombre_mas_corto() -> None:
    assert find_app("chrome", APPS) == CHROME


def test_tolera_un_error_chico_de_transcripcion() -> None:
    assert find_app("Spotifi", APPS) == SPOTIFY
    assert find_app("crome", APPS) == CHROME
    assert find_app("bloc de nota", APPS) == NOTEPAD


def test_una_palabra_parecida_no_alcanza_si_las_demas_no_estan() -> None:
    assert find_app("crome cast", APPS) is None


def test_si_no_se_puede_decidir_entre_dos_no_elige() -> None:
    # «Bloc de notas» y «Notas rápidas» miden lo mismo: mejor preguntar.
    assert find_app("notas", APPS) is None


def test_si_nada_se_parece_no_encuentra_nada() -> None:
    assert find_app("Photoshop", APPS) is None


def test_abre_la_aplicacion_que_encontro() -> None:
    platform = FakePlatform()

    result = asyncio.run(OpenAppTool(platform).run({"name": "bloc de notas"}))

    assert platform.opened == [NOTEPAD]
    assert "Bloc de notas" in result


def test_si_no_la_encuentra_no_abre_nada_y_dice_cuales_se_parecen() -> None:
    platform = FakePlatform()

    with pytest.raises(ToolError, match="Bloc de notas") as failure:
        asyncio.run(OpenAppTool(platform).run({"name": "notas"}))

    assert "Notas rápidas" in str(failure.value)
    assert platform.opened == []


def test_si_no_hay_nada_parecido_lo_dice() -> None:
    with pytest.raises(ToolError, match="Photoshop"):
        asyncio.run(OpenAppTool(FakePlatform()).run({"name": "Photoshop"}))


def test_sin_nombre_no_hay_nada_que_abrir() -> None:
    platform = FakePlatform()

    with pytest.raises(ToolError, match="nombre"):
        asyncio.run(OpenAppTool(platform).run({}))

    assert platform.opened == []


def test_es_una_accion_normal() -> None:
    assert OpenAppTool(FakePlatform()).level == PermissionLevel.NORMAL
