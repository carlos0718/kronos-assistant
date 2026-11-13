"""Arma las piezas con las que arranca el motor."""

import os
from dataclasses import dataclass

from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import DemoVoices, DemoWakeWord, demo_pipeline
from kronos_engine.core.standby import Standby
from kronos_engine.core.voices import VoiceControl

# KRONOS_PIPELINE=demo usa las piezas simuladas, sin micrófono ni modelos.
PIPELINE_ENV = "KRONOS_PIPELINE"
# Idioma en que se transcribe ("es", "en"). PROVISORIO: irá en la configuración.
LANGUAGE_ENV = "KRONOS_LANGUAGE"

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


def build() -> Parts:
    if os.environ.get(PIPELINE_ENV) == "demo":
        return Parts(demo_pipeline(), DemoVoices(), Standby(DemoWakeWord()))

    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.agent.instructions import INSTRUCTIONS
    from kronos_engine.agent.responder import AgentResponder
    from kronos_engine.config.settings import SettingsStore
    from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider
    from kronos_engine.voice.catalog import DEFAULT_VOICES
    from kronos_engine.voice.listener import VoiceListener
    from kronos_engine.voice.microphone import open_microphone
    from kronos_engine.voice.playback import play
    from kronos_engine.voice.speaker import VoiceSpeaker
    from kronos_engine.voice.stt import WhisperStt
    from kronos_engine.voice.tts import PiperTts
    from kronos_engine.voice.vad import SileroVad
    from kronos_engine.voice.voices import PiperVoices
    from kronos_engine.voice.wake import WhisperWakeWord

    language = os.environ.get(LANGUAGE_ENV, "es")
    store = SettingsStore()
    settings = store.load()
    default_voice = DEFAULT_VOICES.get(language, DEFAULT_VOICES["es"])

    # Los tres modelos se cargan mientras el usuario todavía no habló.
    stt = WhisperStt(language=language)
    stt.preload()
    tts = PiperTts(settings.voice or os.environ.get(VOICE_ENV) or default_voice)
    tts.preload()
    model = OllamaProvider(
        os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        base_url=os.environ.get(OLLAMA_URL_ENV, DEFAULT_URL),
    )
    model.preload()

    pipeline = Pipeline(
        listener=VoiceListener(open_microphone, SileroVad(), stt),
        responder=AgentResponder(model, INSTRUCTIONS),
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
    return Parts(pipeline, voices, standby)
