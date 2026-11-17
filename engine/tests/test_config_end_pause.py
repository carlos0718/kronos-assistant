from pathlib import Path

from kronos_engine.config.end_pause import StoredEndPause
from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.end_pause import DEFAULT_MS


def test_sin_elegir_nada_usa_la_pausa_de_fabrica(tmp_path: Path) -> None:
    assert StoredEndPause(SettingsStore(tmp_path / "config.toml")).get() == DEFAULT_MS


def test_la_pausa_elegida_queda_guardada(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"

    StoredEndPause(SettingsStore(path)).set(2500)

    # Otro objeto sobre el mismo archivo: es lo que pasa al reiniciar el motor.
    assert StoredEndPause(SettingsStore(path)).get() == 2500
