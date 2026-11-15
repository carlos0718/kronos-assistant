"""Arma las piezas con las que arranca el motor."""

import os
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import (
    DemoFollowUp,
    DemoProfile,
    DemoVoices,
    DemoWakeWord,
    demo_pipeline,
)
from kronos_engine.core.follow_up import FollowUpControl
from kronos_engine.core.profile import ProfileControl
from kronos_engine.core.standby import Standby
from kronos_engine.core.voices import VoiceControl

if TYPE_CHECKING:
    from kronos_engine.voice.parakeet import ParakeetStt
    from kronos_engine.voice.stt import WhisperStt

# KRONOS_PIPELINE=demo usa las piezas simuladas, sin micrófono ni modelos.
PIPELINE_ENV = "KRONOS_PIPELINE"
# Idioma en que se transcribe ("es", "en"). PROVISORIO: irá en la configuración.
LANGUAGE_ENV = "KRONOS_LANGUAGE"
# Modelo que transcribe: "parakeet", o un tamaño de whisper ("base", "small",
# "medium"…). Los whisper más grandes entienden mejor y tardan más; los tiempos
# están en docs/MEDICIONES.md. PROVISORIO: irá en la configuración.
STT_MODEL_ENV = "KRONOS_STT_MODEL"
DEFAULT_STT_MODEL = "small"
PARAKEET = "parakeet"

# Modelo de Ollama que responde. PROVISORIO: irá en la configuración.
MODEL_ENV = "KRONOS_LLM_MODEL"
DEFAULT_MODEL = "qwen3:8b"
# Dónde escucha Ollama, si no es la dirección por defecto.
OLLAMA_URL_ENV = "KRONOS_OLLAMA_URL"

# Voz de Piper para probar una sin pasar por la configuración. Si el usuario
# ya eligió una voz, gana la suya.
VOICE_ENV = "KRONOS_VOICE"


@dataclass(frozen=True)
class Parts:
    """Lo que el servidor necesita del resto del motor."""

    pipeline: Pipeline
    voices: VoiceControl
    standby: Standby
    profile: ProfileControl
    follow_up: FollowUpControl


def stt_for(name: str, language: str) -> "ParakeetStt | WhisperStt":
    """Elige el reconocedor de voz por el nombre de su modelo."""
    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.voice.parakeet import ParakeetStt
    from kronos_engine.voice.stt import WhisperStt

    if name == PARAKEET:
        # Parakeet reconoce solo el idioma: no recibe el elegido.
        return ParakeetStt()
    return WhisperStt(name, language=language)


def build() -> Parts:
    if os.environ.get(PIPELINE_ENV) == "demo":
        return Parts(
            demo_pipeline(), DemoVoices(), Standby(DemoWakeWord()), DemoProfile(), DemoFollowUp()
        )

    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.agent.instructions import instructions_for
    from kronos_engine.agent.responder import AgentResponder
    from kronos_engine.config.follow_up import StoredFollowUp
    from kronos_engine.config.profile import StoredProfile
    from kronos_engine.config.settings import SettingsStore
    from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider
    from kronos_engine.voice.catalog import DEFAULT_VOICES
    from kronos_engine.voice.listener import VoiceListener
    from kronos_engine.voice.microphone import open_microphone
    from kronos_engine.voice.playback import play
    from kronos_engine.voice.speaker import VoiceSpeaker
    from kronos_engine.voice.tts import PiperTts
    from kronos_engine.voice.vad import SileroVad
    from kronos_engine.voice.voices import PiperVoices
    from kronos_engine.voice.wake import WhisperWakeWord

    language = os.environ.get(LANGUAGE_ENV, "es")
    store = SettingsStore()
    settings = store.load()
    default_voice = DEFAULT_VOICES.get(language, DEFAULT_VOICES["es"])

    # Los tres modelos se cargan mientras el usuario todavía no habló.
    stt = stt_for(os.environ.get(STT_MODEL_ENV, DEFAULT_STT_MODEL), language)
    stt.preload()
    tts = PiperTts(settings.voice or os.environ.get(VOICE_ENV) or default_voice)
    tts.preload()
    model = OllamaProvider(
        os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        base_url=os.environ.get(OLLAMA_URL_ENV, DEFAULT_URL),
    )
    model.preload()

    profile = StoredProfile(store)

    def current_instructions() -> str:
        # Se lee en cada respuesta: el usuario puede cambiar su perfil sin reiniciar.
        saved = profile.get()
        return instructions_for(saved.name, saved.about)

    pipeline = Pipeline(
        listener=VoiceListener(open_microphone, SileroVad(), stt),
        responder=AgentResponder(model, current_instructions),
        speaker=VoiceSpeaker(tts, play),
    )

    # El reposo usa el mismo reconocedor que la conversación, con su propio
    # detector de voz: cada uno lleva la cuenta de lo que viene oyendo.
    standby = Standby(
        WhisperWakeWord(open_microphone, SileroVad(), stt),
        enabled=settings.wake_word,
        remember=lambda enabled: store.update(wake_word=enabled),
    )
    voices = PiperVoices(tts, PiperTts, play, lambda voice: store.update(voice=voice))
    return Parts(pipeline, voices, standby, profile, StoredFollowUp(store))
