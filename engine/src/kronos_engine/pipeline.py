"""Arma las piezas de la conversación con las que arranca el motor."""

import os

from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import DemoResponder, DemoSpeaker, demo_pipeline

# KRONOS_PIPELINE=demo usa las piezas simuladas, sin micrófono ni modelos.
PIPELINE_ENV = "KRONOS_PIPELINE"
# Idioma en que se transcribe ("es", "en"). PROVISORIO: irá en la configuración.
LANGUAGE_ENV = "KRONOS_LANGUAGE"

# PROVISORIO: hasta que se conecte el modelo, el asistente responde esto.
PLACEHOLDER_REPLY = (
    "Te escuché. Todavía no sé responder ni hablar: eso llega en los próximos pasos."
)


def build_pipeline() -> Pipeline:
    if os.environ.get(PIPELINE_ENV) == "demo":
        return demo_pipeline()

    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.voice.listener import VoiceListener
    from kronos_engine.voice.microphone import open_microphone
    from kronos_engine.voice.stt import WhisperStt
    from kronos_engine.voice.vad import SileroVad

    stt = WhisperStt(language=os.environ.get(LANGUAGE_ENV, "es"))
    stt.preload()  # Carga el modelo mientras el usuario todavía no habló.
    return Pipeline(
        listener=VoiceListener(open_microphone, SileroVad(), stt),
        responder=DemoResponder(0.3, reply=PLACEHOLDER_REPLY),
        speaker=DemoSpeaker(1.5),
    )
