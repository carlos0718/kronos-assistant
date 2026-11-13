"""Arma las piezas de la conversación con las que arranca el motor."""

import os

from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import demo_pipeline

# KRONOS_PIPELINE=demo usa las piezas simuladas, sin micrófono ni modelos.
PIPELINE_ENV = "KRONOS_PIPELINE"
# Idioma en que se transcribe ("es", "en"). PROVISORIO: irá en la configuración.
LANGUAGE_ENV = "KRONOS_LANGUAGE"

# Modelo de Ollama que responde. PROVISORIO: irá en la configuración.
MODEL_ENV = "KRONOS_LLM_MODEL"
DEFAULT_MODEL = "qwen3:8b"
# Dónde escucha Ollama, si no es la dirección por defecto.
OLLAMA_URL_ENV = "KRONOS_OLLAMA_URL"

# Voz de Piper con la que habla. PROVISORIO: irá en la configuración.
VOICE_ENV = "KRONOS_VOICE"
# Voz por defecto según el idioma.
DEFAULT_VOICES = {"es": "es_AR-daniela-high", "en": "en_US-lessac-medium"}


def build_pipeline() -> Pipeline:
    if os.environ.get(PIPELINE_ENV) == "demo":
        return demo_pipeline()

    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.agent.instructions import INSTRUCTIONS
    from kronos_engine.agent.responder import AgentResponder
    from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider
    from kronos_engine.voice.listener import VoiceListener
    from kronos_engine.voice.microphone import open_microphone
    from kronos_engine.voice.playback import play
    from kronos_engine.voice.speaker import VoiceSpeaker
    from kronos_engine.voice.stt import WhisperStt
    from kronos_engine.voice.tts import PiperTts
    from kronos_engine.voice.vad import SileroVad

    language = os.environ.get(LANGUAGE_ENV, "es")
    # Los tres modelos se cargan mientras el usuario todavía no habló.
    stt = WhisperStt(language=language)
    stt.preload()
    voice = os.environ.get(VOICE_ENV) or DEFAULT_VOICES.get(language, DEFAULT_VOICES["es"])
    tts = PiperTts(voice)
    tts.preload()
    model = OllamaProvider(
        os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        base_url=os.environ.get(OLLAMA_URL_ENV, DEFAULT_URL),
    )
    model.preload()
    return Pipeline(
        listener=VoiceListener(open_microphone, SileroVad(), stt),
        responder=AgentResponder(model, INSTRUCTIONS),
        speaker=VoiceSpeaker(tts, play),
    )
