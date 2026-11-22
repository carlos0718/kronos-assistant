import asyncio

import numpy as np
import pytest

from kronos_engine.core.recognizer import DEFAULT_RECOGNIZER
from kronos_engine.voice.assembly import (
    conversation_tts,
    starting_voice,
    stt_for,
    tts_for,
    voice_catalog,
)
from kronos_engine.voice.catalog import VOICES
from kronos_engine.voice.elevenlabs import ElevenLabsError, ElevenLabsStt, ElevenLabsTts
from kronos_engine.voice.fallback import FallbackTts, Outage
from kronos_engine.voice.parakeet import ParakeetStt
from kronos_engine.voice.stt import WhisperStt
from kronos_engine.voice.tts import PiperTts


def key() -> str:
    return "clave-de-prueba"


def no_key() -> str:
    return ""


def test_el_reconocedor_de_fabrica_es_parakeet() -> None:
    assert isinstance(stt_for(DEFAULT_RECOGNIZER, "es", key), ParakeetStt)


def test_parakeet_se_elige_por_su_nombre() -> None:
    assert isinstance(stt_for("parakeet", "es", key), ParakeetStt)


@pytest.mark.parametrize("name", ["small", "base", "large-v3-turbo"])
def test_cualquier_otro_nombre_es_un_modelo_de_whisper(name: str) -> None:
    assert isinstance(stt_for(name, "es", key), WhisperStt)


def test_elevenlabs_se_elige_por_su_nombre() -> None:
    assert isinstance(stt_for("elevenlabs", "es", key), ElevenLabsStt)


def test_elevenlabs_sin_clave_avisa_donde_cargarla_al_transcribir() -> None:
    recognizer = stt_for("elevenlabs", "es", no_key)

    with pytest.raises(ElevenLabsError, match="pestaña Voz"):
        asyncio.run(recognizer.transcribe(np.zeros(160, dtype=np.float32)))


DANIELA = "es_AR-daniela-high"
DAVE = "es_ES-davefx-medium"


def test_arranca_con_la_voz_que_eligio_el_usuario() -> None:
    assert starting_voice(DAVE, DANIELA, has_key=False) == DAVE
    assert starting_voice("elevenlabs:abc", DANIELA, has_key=True) == "elevenlabs:abc"


def test_sin_eleccion_arranca_con_la_de_fabrica() -> None:
    assert starting_voice(None, DANIELA, has_key=True) == DANIELA


def test_una_voz_de_elevenlabs_sin_clave_vuelve_a_la_de_fabrica() -> None:
    assert starting_voice("elevenlabs:abc", DANIELA, has_key=False) == DANIELA


def test_las_voces_de_elevenlabs_tienen_su_motor() -> None:
    assert isinstance(tts_for("elevenlabs:abc", key), ElevenLabsTts)
    assert isinstance(tts_for(DANIELA, key), PiperTts)


def test_sin_clave_solo_se_ofrecen_las_voces_de_piper() -> None:
    assert voice_catalog(no_key)() == VOICES


def test_en_la_conversacion_una_voz_de_elevenlabs_tiene_respaldo_de_piper() -> None:
    make = conversation_tts(DANIELA, Outage(), key)

    tts = make("elevenlabs:abc")

    assert isinstance(tts, FallbackTts)
    assert tts.voice == "elevenlabs:abc"


def test_en_la_conversacion_una_voz_de_piper_no_lleva_respaldo() -> None:
    assert isinstance(conversation_tts(DANIELA, Outage(), key)(DAVE), PiperTts)
