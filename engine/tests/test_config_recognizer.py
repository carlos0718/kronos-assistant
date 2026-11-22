from pathlib import Path

import pytest

from kronos_engine.config.recognizer import StoredRecognizer
from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.recognizer import DEFAULT_RECOGNIZER, ELEVENLABS, WHISPER


def stored(path: Path, **extra: object) -> StoredRecognizer:
    return StoredRecognizer(SettingsStore(path), lambda: False, **extra)  # type: ignore[arg-type]


def test_sin_elegir_nada_usa_el_de_fabrica(tmp_path: Path) -> None:
    assert stored(tmp_path / "config.toml").get() == DEFAULT_RECOGNIZER


def test_sin_elegir_nada_vale_la_variable_de_entorno(tmp_path: Path) -> None:
    assert stored(tmp_path / "config.toml", from_env="elevenlabs").get() == ELEVENLABS


def test_lo_elegido_gana_a_la_variable_de_entorno(tmp_path: Path) -> None:
    recognizer = stored(tmp_path / "config.toml", from_env="elevenlabs")

    recognizer.set(WHISPER)

    assert recognizer.get() == WHISPER


def test_la_eleccion_queda_guardada(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"

    stored(path).set(ELEVENLABS)

    # Otro objeto sobre el mismo archivo: es lo que pasa al reiniciar el motor.
    assert stored(path).get() == ELEVENLABS


def test_rechaza_un_reconocedor_desconocido_y_no_lo_guarda(tmp_path: Path) -> None:
    recognizer = stored(tmp_path / "config.toml")

    with pytest.raises(ValueError, match="desconocido"):
        recognizer.set("loro")

    assert recognizer.get() == DEFAULT_RECOGNIZER


def test_un_nombre_desconocido_en_el_archivo_se_ignora(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('stt_model = "de-una-version-futura"\n', encoding="utf-8")

    assert stored(path).get() == DEFAULT_RECOGNIZER


def test_avisa_cuando_cambia(tmp_path: Path) -> None:
    changes: list[str] = []
    recognizer = stored(tmp_path / "config.toml", on_change=lambda: changes.append("cambió"))

    recognizer.set(WHISPER)

    assert changes == ["cambió"]
