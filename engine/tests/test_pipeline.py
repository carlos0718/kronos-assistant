import pytest

from kronos_engine.pipeline import (
    DEFAULT_STT_MODEL,
    starting_voice,
    stt_for,
    tts_for,
    voice_catalog,
)
from kronos_engine.voice.catalog import VOICES
from kronos_engine.voice.elevenlabs import ElevenLabsError, ElevenLabsStt, ElevenLabsTts
from kronos_engine.voice.parakeet import ParakeetStt
from kronos_engine.voice.stt import WhisperStt
from kronos_engine.voice.tts import PiperTts


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


DANIELA = "es_AR-daniela-high"
DAVE = "es_ES-davefx-medium"


def test_arranca_con_la_voz_que_eligio_el_usuario() -> None:
    assert starting_voice(DAVE, DANIELA, has_key=False) == DAVE
    assert starting_voice("elevenlabs:abc", DANIELA, has_key=True) == "elevenlabs:abc"


def test_sin_eleccion_arranca_con_la_de_fabrica() -> None:
    assert starting_voice(None, DANIELA, has_key=True) == DANIELA


def test_una_voz_de_elevenlabs_sin_clave_vuelve_a_la_de_fabrica() -> None:
    assert starting_voice("elevenlabs:abc", DANIELA, has_key=False) == DANIELA


def test_las_voces_de_elevenlabs_tienen_su_motor(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("ELEVENLABS_API_KEY", "clave-de-prueba")

    assert isinstance(tts_for("elevenlabs:abc"), ElevenLabsTts)
    assert isinstance(tts_for(DANIELA), PiperTts)


def test_sin_clave_solo_se_ofrecen_las_voces_de_piper(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("ELEVENLABS_API_KEY", raising=False)

    assert voice_catalog()() == VOICES
