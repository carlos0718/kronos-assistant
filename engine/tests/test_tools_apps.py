import asyncio
from collections.abc import Sequence

import pytest

from kronos_engine.core.platform import App, Window
from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.apps import CloseAppTool, OpenAppTool, app_of, find_app, find_windows

NOTEPAD = App("Bloc de notas", "Microsoft.WindowsNotepad!App")
STICKY = App("Notas rápidas", "Microsoft.StickyNotes!App")
CHROME = App("Google Chrome", "Chrome")
REMOTE = App("Chrome Remote Desktop", "ChromeRemote")
SPOTIFY = App("Spotify", "Spotify!App")
UNINSTALL = App("Desinstalar Spotify", "Spotify!Uninstall")
CODE = App("Visual Studio Code", "Microsoft.VisualStudioCode")
APPS = [NOTEPAD, STICKY, CHROME, REMOTE, SPOTIFY, UNINSTALL, CODE]


CHROME_DOCS = Window("Notas de la reunión - Google Docs - Google Chrome", 1)
CHROME_MAIL = Window("Recibidos (3) - Gmail - Google Chrome", 2)
NOTEPAD_WINDOW = Window("Sin título - Bloc de notas", 3)
CALCULATOR = Window("Calculadora", 4)
SPOTIFY_WINDOW = Window("Spotify Premium", 5)
OVERLAY = Window("Kronos", 6)
WINDOWS = [CHROME_DOCS, CHROME_MAIL, NOTEPAD_WINDOW, CALCULATOR, SPOTIFY_WINDOW, OVERLAY]


class FakePlatform:
    def __init__(self, apps: Sequence[App] = APPS, windows: Sequence[Window] = WINDOWS) -> None:
        self._apps = apps
        self._windows = windows
        self.opened: list[App] = []
        self.closed: list[Window] = []

    def windows(self) -> Sequence[Window]:
        return self._windows

    def close_window(self, window: Window) -> None:
        self.closed.append(window)

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


def test_el_nombre_de_la_aplicacion_es_el_final_del_titulo_de_la_ventana() -> None:
    assert app_of("Notas de la reunión - Google Docs - Google Chrome") == "Google Chrome"
    assert app_of("#general | Servidor - Discord") == "Discord"
    assert app_of("Calculadora") == "Calculadora"


def test_encuentra_todas_las_ventanas_de_la_aplicacion() -> None:
    assert find_windows("chrome", WINDOWS) == [CHROME_DOCS, CHROME_MAIL]
    assert find_windows("la calculadora", WINDOWS) == [CALCULATOR]
    assert find_windows("spotify", WINDOWS) == [SPOTIFY_WINDOW]


def test_no_confunde_el_nombre_de_un_documento_con_la_aplicacion() -> None:
    # «Notas de la reunión» es una pestaña de Chrome, no el Bloc de notas.
    assert find_windows("bloc de notas", WINDOWS) == [NOTEPAD_WINDOW]
    assert find_windows("reunión", WINDOWS) == []


def test_si_la_aplicacion_no_esta_abierta_no_encuentra_ventanas() -> None:
    assert find_windows("Photoshop", WINDOWS) == []


def test_las_ventanas_de_kronos_no_se_cierran() -> None:
    assert find_windows("kronos", WINDOWS) == []


def test_cerrar_una_aplicacion_pide_aprobacion() -> None:
    assert CloseAppTool(FakePlatform()).level == PermissionLevel.SENSITIVE


def test_la_pregunta_dice_que_se_va_a_cerrar_de_verdad() -> None:
    tool = CloseAppTool(FakePlatform())

    assert asyncio.run(tool.describe({"name": "chrome"})) == "cerrar Google Chrome (2 ventanas)"
    assert asyncio.run(tool.describe({"name": "la calculadora"})) == "cerrar Calculadora"


def test_no_se_pregunta_por_cerrar_algo_que_no_esta_abierto() -> None:
    with pytest.raises(ToolError, match="Photoshop"):
        asyncio.run(CloseAppTool(FakePlatform()).describe({"name": "Photoshop"}))


def test_cierra_todas_las_ventanas_de_la_aplicacion() -> None:
    platform = FakePlatform()

    result = asyncio.run(CloseAppTool(platform).run({"name": "chrome"}))

    assert platform.closed == [CHROME_DOCS, CHROME_MAIL]
    assert "Google Chrome" in result


def test_si_no_esta_abierta_no_cierra_nada_y_lo_dice() -> None:
    platform = FakePlatform()

    with pytest.raises(ToolError, match="Photoshop"):
        asyncio.run(CloseAppTool(platform).run({"name": "Photoshop"}))

    assert platform.closed == []


def test_sin_nombre_no_hay_nada_que_cerrar() -> None:
    with pytest.raises(ToolError, match="nombre"):
        asyncio.run(CloseAppTool(FakePlatform()).run({"name": " "}))


def test_abrir_una_aplicacion_se_describe_con_su_nombre() -> None:
    assert asyncio.run(OpenAppTool(FakePlatform()).describe({"name": "Spotify"})) == "abrir Spotify"
