import pytest

from kronos_engine.pipeline import stt_for
from kronos_engine.voice.parakeet import ParakeetStt
from kronos_engine.voice.stt import WhisperStt


def test_parakeet_se_elige_por_su_nombre() -> None:
    assert isinstance(stt_for("parakeet", "es"), ParakeetStt)


@pytest.mark.parametrize("name", ["small", "base", "large-v3-turbo"])
def test_cualquier_otro_nombre_es_un_modelo_de_whisper(name: str) -> None:
    assert isinstance(stt_for(name, "es"), WhisperStt)
