"""Arma las piezas de la conversación con las que arranca el motor."""

import os

from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import SilentSpeaker, demo_pipeline

# KRONOS_PIPELINE=demo usa las piezas simuladas, sin micrófono ni modelos.
PIPELINE_ENV = "KRONOS_PIPELINE"
# Idioma en que se transcribe ("es", "en"). PROVISORIO: irá en la configuración.
LANGUAGE_ENV = "KRONOS_LANGUAGE"

# Modelo de Ollama que responde. PROVISORIO: irá en la configuración.
MODEL_ENV = "KRONOS_LLM_MODEL"
DEFAULT_MODEL = "qwen3:8b"
# Dónde escucha Ollama, si no es la dirección por defecto.
OLLAMA_URL_ENV = "KRONOS_OLLAMA_URL"

# Espera máxima a que el usuario hable. PROVISORIO: sin voz, Kronos vuelve a
# escuchar mientras el usuario todavía lee la respuesta, así que hace falta
# más margen que los 8 segundos normales. Con la voz vuelve al valor normal.
START_TIMEOUT_MS = 20_000


def build_pipeline() -> Pipeline:
    if os.environ.get(PIPELINE_ENV) == "demo":
        return demo_pipeline()

    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.agent.instructions import INSTRUCTIONS
    from kronos_engine.agent.responder import AgentResponder
    from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider
    from kronos_engine.voice.endpointing import EndpointConfig
    from kronos_engine.voice.listener import VoiceListener
    from kronos_engine.voice.microphone import open_microphone
    from kronos_engine.voice.stt import WhisperStt
    from kronos_engine.voice.vad import SileroVad

    stt = WhisperStt(language=os.environ.get(LANGUAGE_ENV, "es"))
    stt.preload()  # Carga el modelo mientras el usuario todavía no habló.
    model = OllamaProvider(
        os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        base_url=os.environ.get(OLLAMA_URL_ENV, DEFAULT_URL),
    )
    model.preload()
    return Pipeline(
        listener=VoiceListener(
            open_microphone, SileroVad(), stt, EndpointConfig(start_timeout_ms=START_TIMEOUT_MS)
        ),
        responder=AgentResponder(model, INSTRUCTIONS),
        speaker=SilentSpeaker(),
    )
