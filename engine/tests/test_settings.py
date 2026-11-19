from pathlib import Path

import pytest

from kronos_engine.config.settings import Settings, SettingsStore


def test_sin_archivo_devuelve_los_ajustes_de_fabrica(tmp_path: Path) -> None:
    assert SettingsStore(tmp_path / "config.toml").load() == Settings(voice=None, wake_word=False)


def test_lo_que_se_guarda_se_vuelve_a_leer(tmp_path: Path) -> None:
    path = tmp_path / "carpeta-nueva" / "config.toml"

    SettingsStore(path).save(Settings(voice="es_ES-davefx-medium"))

    assert SettingsStore(path).load() == Settings(voice="es_ES-davefx-medium")
    assert path.read_text(encoding="utf-8").startswith(
        'voice = "es_ES-davefx-medium"\nwake_word = false\nfollow_up_seconds = 8\n'
        "end_pause_ms = 1500\n"
    )


def test_el_perfil_se_guarda_y_se_vuelve_a_leer(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.toml")

    about = "Programo. Me gusta correr."
    store.update(user_name="Carlos", user_about=about)

    assert store.load() == Settings(user_name="Carlos", user_about=about)


def test_un_archivo_roto_no_impide_arrancar(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("esto no es TOML [[[", encoding="utf-8")

    assert SettingsStore(path).load() == Settings()


def test_ignora_un_valor_del_tipo_equivocado(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('voice = 3\nwake_word = "sí"\n', encoding="utf-8")

    assert SettingsStore(path).load() == Settings()


def test_cambiar_un_ajuste_conserva_los_demas(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.toml")
    store.save(Settings(voice="es_ES-davefx-medium"))

    store.update(wake_word=True)

    assert store.load() == Settings(voice="es_ES-davefx-medium", wake_word=True)


def test_la_espera_despues_de_responder_se_guarda_y_se_vuelve_a_leer(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.toml")

    store.update(follow_up_seconds=20)

    assert store.load() == Settings(follow_up_seconds=20)


@pytest.mark.parametrize("value", ["-1", "61", "2.5", "true", '"ocho"'])
def test_una_espera_invalida_vuelve_a_la_de_fabrica(tmp_path: Path, value: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(f"follow_up_seconds = {value}\n", encoding="utf-8")

    assert SettingsStore(path).load() == Settings()


def test_la_pausa_de_fin_de_frase_se_guarda_y_se_vuelve_a_leer(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.toml")

    store.update(end_pause_ms=2500)

    assert store.load() == Settings(end_pause_ms=2500)


@pytest.mark.parametrize("value", ["0", "499", "5001", "1500.5", "true", '"larga"'])
def test_una_pausa_invalida_vuelve_a_la_de_fabrica(tmp_path: Path, value: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(f"end_pause_ms = {value}\n", encoding="utf-8")

    assert SettingsStore(path).load() == Settings()


def test_las_carpetas_permitidas_se_guardan_y_se_vuelven_a_leer(tmp_path: Path) -> None:
    store = SettingsStore(tmp_path / "config.toml")

    store.update(folders_known=("desktop",), folders_extra=("D:/proyectos",), folder_depth=2)

    assert store.load() == Settings(
        folders_known=("desktop",), folders_extra=("D:/proyectos",), folder_depth=2
    )


def test_sin_ninguna_carpeta_conocida_no_vuelve_a_las_de_fabrica(tmp_path: Path) -> None:
    # Apagarlas todas es una elección del usuario, no un archivo roto.
    store = SettingsStore(tmp_path / "config.toml")

    store.update(folders_known=())

    assert store.load().folders_known == ()


@pytest.mark.parametrize(
    "line",
    [
        'folders_known = "desktop"',
        "folder_depth = 0",
        "folder_depth = 6",
        "folder_depth = true",
        "folders_extra = 3",
    ],
)
def test_carpetas_invalidas_vuelven_a_las_de_fabrica(tmp_path: Path, line: str) -> None:
    path = tmp_path / "config.toml"
    path.write_text(line + "\n", encoding="utf-8")

    assert SettingsStore(path).load() == Settings()


def test_ignora_una_carpeta_conocida_que_no_existe(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('folders_known = ["desktop", "papelera", 3]\n', encoding="utf-8")

    assert SettingsStore(path).load().folders_known == ("desktop",)
