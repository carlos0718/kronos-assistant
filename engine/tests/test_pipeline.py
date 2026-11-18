import pytest

from kronos_engine.pipeline import DEFAULT_STT_MODEL, stt_for
from kronos_engine.voice.elevenlabs import ElevenLabsError, ElevenLabsStt
from kronos_engine.voice.parakeet import ParakeetStt
from kronos_engine.voice.stt import WhisperStt


def test_el_reconocedor_de_fabrica_es_parakeet() -> None:
    assert isinstance(stt_for(DEFAULT_STT_MODEL, "es"), ParakeetStt)


def test_parakeet_se_elige_por_su_nombre() -> None:
    assert isinstance(stt_for("parakeet", "es"), ParakeetStt)


@pytest.mark.parametrize("name", ["small", "base", "large-v3-turbo"])
def test_cualquier_otro_nombre_es_un_modelo_de_whisper(name: str) -> None:
    assert isinstance(stt_for(name, "es"), WhisperStt)


def test_elevenlabs_se_elige_por_su_nombre_con_la_clave_del_entorno(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")

    assert isinstance(stt_for("elevenlabs", "es"), ElevenLabsStt)


def test_elevenlabs_sin_clave_avisa_que_falta(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
        stt_for("elevenlabs", "es")
