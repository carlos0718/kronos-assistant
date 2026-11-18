from kronos_engine.core.platform import App, Folder
from kronos_engine.platform.windows.apps import SHELL_FOLDERS, parse_apps


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


def test_sabe_abrir_todas_las_carpetas_del_usuario() -> None:
    assert set(SHELL_FOLDERS) == set(Folder)
    assert all(name.startswith("shell:") for name in SHELL_FOLDERS.values())
