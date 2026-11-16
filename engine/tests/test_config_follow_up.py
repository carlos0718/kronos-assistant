from pathlib import Path

from kronos_engine.config.follow_up import StoredFollowUp
from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.follow_up import DEFAULT_SECONDS


def test_sin_elegir_nada_usa_la_espera_de_fabrica(tmp_path: Path) -> None:
    assert StoredFollowUp(SettingsStore(tmp_path / "config.toml")).get() == DEFAULT_SECONDS


def test_la_espera_elegida_queda_guardada(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"

    StoredFollowUp(SettingsStore(path)).set(25)

    # Otro objeto sobre el mismo archivo: es lo que pasa al reiniciar el motor.
    assert StoredFollowUp(SettingsStore(path)).get() == 25
