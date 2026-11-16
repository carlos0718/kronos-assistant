import pytest

from kronos_engine.pipeline import (
    DEFAULT_END_SILENCE_MS,
    DEFAULT_STT_MODEL,
    end_silence_ms,
    stt_for,
)
from kronos_engine.voice.parakeet import ParakeetStt
from kronos_engine.voice.stt import WhisperStt


def test_el_reconocedor_de_fabrica_es_parakeet() -> None:
    assert isinstance(stt_for(DEFAULT_STT_MODEL, "es"), ParakeetStt)


def test_parakeet_se_elige_por_su_nombre() -> None:
    assert isinstance(stt_for("parakeet", "es"), ParakeetStt)


@pytest.mark.parametrize("name", ["small", "base", "large-v3-turbo"])
def test_cualquier_otro_nombre_es_un_modelo_de_whisper(name: str) -> None:
    assert isinstance(stt_for(name, "es"), WhisperStt)


def test_la_pausa_que_termina_la_frase_es_la_de_fabrica() -> None:
    assert end_silence_ms(None) == DEFAULT_END_SILENCE_MS


def test_la_pausa_que_termina_la_frase_se_puede_elegir() -> None:
    assert end_silence_ms("1800") == 1800


@pytest.mark.parametrize("value", ["", "mucho", "50", "60000", "-1"])
def test_una_pausa_invalida_vuelve_a_la_de_fabrica(value: str) -> None:
    assert end_silence_ms(value) == DEFAULT_END_SILENCE_MS
