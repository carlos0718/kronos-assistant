"""Elige las piezas de voz: qué reconocedor y qué motor de voz corresponde.

`key` es de dónde leer la clave de ElevenLabs que el usuario cargó en la pestaña
Voz; se lee en cada pedido, así que guardarla o borrarla no obliga a reiniciar.
"""

import os
import threading
from collections.abc import Callable
from typing import TYPE_CHECKING

from kronos_engine.core.recognizer import ELEVENLABS, PARAKEET

if TYPE_CHECKING:
    from kronos_engine.core.voices import VoiceInfo
    from kronos_engine.voice.elevenlabs import ElevenLabsStt, ElevenLabsTts
    from kronos_engine.voice.fallback import FallbackTts, Outage
    from kronos_engine.voice.parakeet import ParakeetStt
    from kronos_engine.voice.stt import WhisperStt
    from kronos_engine.voice.tts import PiperTts

Key = Callable[[], str]


def stt_for(name: str, language: str, key: Key) -> "ParakeetStt | WhisperStt | ElevenLabsStt":
    """Elige el reconocedor de voz por el nombre de su modelo."""
    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.voice.elevenlabs import ElevenLabsStt
    from kronos_engine.voice.parakeet import ParakeetStt
    from kronos_engine.voice.stt import WhisperStt

    if name == ELEVENLABS:
        return ElevenLabsStt(key, language=language)
    if name == PARAKEET:
        # Parakeet reconoce solo el idioma: no recibe el elegido.
        return ParakeetStt()
    return WhisperStt(name, language=language)


def tts_for(voice: str, key: Key) -> "PiperTts | ElevenLabsTts":
    """El motor de voz que corresponde a una voz: ElevenLabs si su id lo dice, si no Piper."""
    from kronos_engine.voice.elevenlabs import (
        TTS_MODEL,
        TTS_MODEL_ENV,
        ElevenLabsTts,
        is_elevenlabs_voice,
    )
    from kronos_engine.voice.tts import PiperTts

    if is_elevenlabs_voice(voice):
        model = os.environ.get(TTS_MODEL_ENV, TTS_MODEL)
        return ElevenLabsTts(key, voice, model=model)
    return PiperTts(voice)


def conversation_tts(
    backup_voice: str, outage: "Outage", key: Key
) -> "Callable[[str], PiperTts | FallbackTts]":
    """Crea el motor de voz de la conversación: las de ElevenLabs, con Piper de respaldo.

    Probar una voz en la pestaña Voz no usa respaldo: si ElevenLabs falla, se ve el error.
    """
    from kronos_engine.voice.fallback import FallbackTts
    from kronos_engine.voice.tts import PiperTts

    def make(voice: str) -> "PiperTts | FallbackTts":
        tts = tts_for(voice, key)
        if isinstance(tts, PiperTts):
            return tts
        return FallbackTts(tts, PiperTts(backup_voice), outage)

    return make


def starting_voice(saved: str | None, default: str, has_key: bool) -> str:
    """La voz con la que arranca: la elegida, salvo que sea de ElevenLabs y falte la clave."""
    from kronos_engine.voice.elevenlabs import is_elevenlabs_voice

    if not saved or (is_elevenlabs_voice(saved) and not has_key):
        return default
    return saved


def voice_catalog(key: Key) -> "Callable[[], list[VoiceInfo]]":
    """Las voces para elegir: las de Piper, y las de ElevenLabs mientras haya clave."""
    from kronos_engine.voice.catalog import VOICES
    from kronos_engine.voice.elevenlabs import ElevenLabsCatalog

    cloud = ElevenLabsCatalog(key)
    if key():
        # Se piden al arrancar, para que elegir una no espere a ElevenLabs.
        threading.Thread(target=cloud.voices, daemon=True).start()
    return lambda: [*VOICES, *cloud.voices()]
