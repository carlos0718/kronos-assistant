from pathlib import Path

from kronos_engine.config.settings import Settings, SettingsStore


def test_sin_archivo_devuelve_los_ajustes_de_fabrica(tmp_path: Path) -> None:
    assert SettingsStore(tmp_path / "config.toml").load() == Settings(voice=None)


def test_lo_que_se_guarda_se_vuelve_a_leer(tmp_path: Path) -> None:
    path = tmp_path / "carpeta-nueva" / "config.toml"

    SettingsStore(path).save(Settings(voice="es_ES-davefx-medium"))

    assert SettingsStore(path).load() == Settings(voice="es_ES-davefx-medium")
    assert path.read_text(encoding="utf-8") == 'voice = "es_ES-davefx-medium"\n'


def test_un_archivo_roto_no_impide_arrancar(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("esto no es TOML [[[", encoding="utf-8")

    assert SettingsStore(path).load() == Settings()


def test_ignora_un_valor_del_tipo_equivocado(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text("voice = 3\n", encoding="utf-8")

    assert SettingsStore(path).load() == Settings()
