import sys

import pytest

from kronos_engine.core.platform import App, Folder, Window
from kronos_engine.platform.windows.apps import new_window, parse_apps
from kronos_engine.platform.windows.known_folders import KNOWN_FOLDER_IDS, known_folder


def test_lee_la_lista_de_aplicaciones_del_menu_inicio() -> None:
    output = (
        '[{"Name":"Bloc de notas","AppID":"Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"},'
        '{"Name":"Google Chrome","AppID":"Chrome"}]'
    )

    assert parse_apps(output) == [
        App("Bloc de notas", "Microsoft.WindowsNotepad_8wekyb3d8bbwe!App"),
        App("Google Chrome", "Chrome"),
    ]


def test_con_una_sola_aplicacion_powershell_no_manda_una_lista() -> None:
    assert parse_apps('{"Name":"Spotify","AppID":"Spotify!App"}') == [App("Spotify", "Spotify!App")]


def test_saltea_las_entradas_sin_nombre_o_sin_identificador() -> None:
    output = '[{"Name":" ","AppID":"x"},{"Name":"Sin id","AppID":null},{"Name":"Ok","AppID":"ok"}]'

    assert parse_apps(output) == [App("Ok", "ok")]


def test_una_salida_vacia_o_rota_es_una_lista_vacia() -> None:
    assert parse_apps("") == []
    assert parse_apps("Get-StartApps: no se reconoce") == []


def test_sabe_donde_estan_todas_las_carpetas_del_usuario() -> None:
    assert set(KNOWN_FOLDER_IDS) == set(Folder)
    for folder in Folder:
        assert known_folder(folder).is_absolute()


@pytest.mark.skipif(sys.platform != "win32", reason="Pregunta a Windows")
def test_windows_dice_donde_estan_y_existen() -> None:
    for folder in Folder:
        assert known_folder(folder).is_dir()


def test_espera_la_ventana_nueva_de_la_carpeta() -> None:
    old = Window("Bloc de notas", 1)
    new = Window("Descargas - Explorador de archivos", 2)
    screens = iter([[old], [old], [old, new]])
    naps: list[float] = []

    found = new_window({old.id}, lambda: next(screens), timeout=1.0, sleep=naps.append)

    assert found == new
    assert len(naps) == 2


def test_si_la_ventana_no_aparece_se_rinde_sin_trabarse() -> None:
    naps: list[float] = []

    found = new_window({1}, lambda: [Window("Bloc de notas", 1)], timeout=0.5, sleep=naps.append)

    assert found is None
    assert sum(naps) >= 0.5
