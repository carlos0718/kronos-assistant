"""Arma las piezas con las que arranca el motor."""

import os
import sys
import threading
from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING

from kronos_engine.core.approval import ApprovalDesk
from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import (
    DemoEndPause,
    DemoFollowUp,
    DemoProfile,
    DemoVoices,
    DemoWakeWord,
    demo_pipeline,
)
from kronos_engine.core.end_pause import EndPauseControl
from kronos_engine.core.follow_up import FollowUpControl
from kronos_engine.core.profile import ProfileControl
from kronos_engine.core.standby import Standby
from kronos_engine.core.tools import Tool
from kronos_engine.core.voices import VoiceControl

if TYPE_CHECKING:
    from kronos_engine.core.voices import VoiceInfo
    from kronos_engine.voice.elevenlabs import ElevenLabsStt, ElevenLabsTts
    from kronos_engine.voice.parakeet import ParakeetStt
    from kronos_engine.voice.stt import WhisperStt
    from kronos_engine.voice.tts import PiperTts

# KRONOS_PIPELINE=demo usa las piezas simuladas, sin micrófono ni modelos.
PIPELINE_ENV = "KRONOS_PIPELINE"
# Idioma en que se transcribe ("es", "en"). PROVISORIO: irá en la configuración.
LANGUAGE_ENV = "KRONOS_LANGUAGE"
# Modelo que transcribe: "parakeet", o un tamaño de whisper ("base", "small",
# "medium"…) para volver al reconocedor anterior. Parakeet es mucho más rápido;
# los tiempos están en docs/MEDICIONES.md. "elevenlabs" transcribe en la nube,
# de pago, con la clave de ELEVENLABS_API_KEY: lo que oye el micrófono sale de
# la computadora, incluso en reposo. PROVISORIO: irá en la configuración.
STT_MODEL_ENV = "KRONOS_STT_MODEL"
PARAKEET = "parakeet"
ELEVENLABS = "elevenlabs"
DEFAULT_STT_MODEL = PARAKEET

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
    end_pause: EndPauseControl


def stt_for(name: str, language: str) -> "ParakeetStt | WhisperStt | ElevenLabsStt":
    """Elige el reconocedor de voz por el nombre de su modelo."""
    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.voice.elevenlabs import KEY_ENV, ElevenLabsStt
    from kronos_engine.voice.parakeet import ParakeetStt
    from kronos_engine.voice.stt import WhisperStt

    if name == ELEVENLABS:
        return ElevenLabsStt(os.environ.get(KEY_ENV, ""), language=language)
    if name == PARAKEET:
        # Parakeet reconoce solo el idioma: no recibe el elegido.
        return ParakeetStt()
    return WhisperStt(name, language=language)


def tts_for(voice: str) -> "PiperTts | ElevenLabsTts":
    """El motor de voz que corresponde a una voz: ElevenLabs si su id lo dice, si no Piper."""
    from kronos_engine.voice.elevenlabs import (
        KEY_ENV,
        TTS_MODEL,
        TTS_MODEL_ENV,
        ElevenLabsTts,
        is_elevenlabs_voice,
    )
    from kronos_engine.voice.tts import PiperTts

    if is_elevenlabs_voice(voice):
        model = os.environ.get(TTS_MODEL_ENV, TTS_MODEL)
        return ElevenLabsTts(os.environ.get(KEY_ENV, ""), voice, model=model)
    return PiperTts(voice)


def starting_voice(saved: str | None, default: str, has_key: bool) -> str:
    """La voz con la que arranca: la elegida, salvo que sea de ElevenLabs y falte la clave."""
    from kronos_engine.voice.elevenlabs import is_elevenlabs_voice

    if not saved or (is_elevenlabs_voice(saved) and not has_key):
        return default
    return saved


def voice_catalog() -> "Callable[[], list[VoiceInfo]]":
    """Las voces para elegir: las de Piper, y las de ElevenLabs si está la clave."""
    from kronos_engine.voice.catalog import VOICES
    from kronos_engine.voice.elevenlabs import KEY_ENV, ElevenLabsCatalog

    key = os.environ.get(KEY_ENV, "")
    if not key:
        return lambda: list(VOICES)
    cloud = ElevenLabsCatalog(key)
    # Se piden al arrancar, para que elegir una no espere a ElevenLabs.
    threading.Thread(target=cloud.voices, daemon=True).start()
    return lambda: [*VOICES, *cloud.voices()]


def available_tools() -> list[Tool]:
    """Las acciones que Kronos puede ejecutar en este sistema."""
    from kronos_engine.tools.apps import CloseAppTool, OpenAppTool
    from kronos_engine.tools.clock import CurrentTimeTool

    tools: list[Tool] = [CurrentTimeTool()]
    if sys.platform == "win32":
        from kronos_engine.platform.windows.apps import WindowsPlatform

        platform = WindowsPlatform()
        platform.preload()
        tools += [OpenAppTool(platform), CloseAppTool(platform)]
    return tools


def build() -> Parts:
    if os.environ.get(PIPELINE_ENV) == "demo":
        return Parts(
            demo_pipeline(),
            DemoVoices(),
            Standby(DemoWakeWord()),
            DemoProfile(),
            DemoFollowUp(),
            DemoEndPause(),
        )

    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.agent.instructions import instructions_for
    from kronos_engine.agent.responder import AgentResponder
    from kronos_engine.config.end_pause import StoredEndPause
    from kronos_engine.config.follow_up import StoredFollowUp
    from kronos_engine.config.profile import StoredProfile
    from kronos_engine.config.settings import SettingsStore
    from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider
    from kronos_engine.permissions.gate import PermissionGate
    from kronos_engine.voice.catalog import DEFAULT_VOICES
    from kronos_engine.voice.elevenlabs import KEY_ENV
    from kronos_engine.voice.listener import VoiceListener
    from kronos_engine.voice.microphone import open_microphone
    from kronos_engine.voice.playback import play
    from kronos_engine.voice.speaker import VoiceSpeaker
    from kronos_engine.voice.vad import SileroVad
    from kronos_engine.voice.voices import RoutedTts, SelectableVoices
    from kronos_engine.voice.wake import WhisperWakeWord

    language = os.environ.get(LANGUAGE_ENV, "es")
    store = SettingsStore()
    settings = store.load()
    default_voice = DEFAULT_VOICES.get(language, DEFAULT_VOICES["es"])

    # Los tres modelos se cargan mientras el usuario todavía no habló.
    stt = stt_for(os.environ.get(STT_MODEL_ENV, DEFAULT_STT_MODEL), language)
    stt.preload()
    voice = starting_voice(
        settings.voice or os.environ.get(VOICE_ENV),
        default_voice,
        has_key=bool(os.environ.get(KEY_ENV)),
    )
    tts = RoutedTts(voice, tts_for)
    tts.preload()
    model = OllamaProvider(
        os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        base_url=os.environ.get(OLLAMA_URL_ENV, DEFAULT_URL),
    )
    model.preload()

    profile = StoredProfile(store)
    end_pause = StoredEndPause(store)
    # El modelo propone las acciones; el control de permisos decide si se
    # ejecutan y, para las delicadas, le pregunta al usuario.
    approvals = ApprovalDesk()
    tools = PermissionGate(available_tools(), approvals)

    def current_instructions() -> str:
        # Se lee en cada respuesta: el usuario puede cambiar su perfil sin reiniciar.
        saved = profile.get()
        return instructions_for(saved.name, saved.about)

    pipeline = Pipeline(
        listener=VoiceListener(
            open_microphone,
            SileroVad(),
            stt,
            # Se lee cada vez que escucha: el usuario la cambia desde el panel sin reiniciar.
            end_silence_ms=end_pause.get,
        ),
        responder=AgentResponder(model, current_instructions, tools=tools),
        speaker=VoiceSpeaker(tts, play),
        approvals=approvals,
    )

    # El reposo usa el mismo reconocedor que la conversación, con su propio
    # detector de voz: cada uno lleva la cuenta de lo que viene oyendo.
    standby = Standby(
        WhisperWakeWord(open_microphone, SileroVad(), stt),
        enabled=settings.wake_word,
        remember=lambda enabled: store.update(wake_word=enabled),
    )
    voices = SelectableVoices(
        tts, tts_for, play, lambda voice: store.update(voice=voice), catalog=voice_catalog()
    )
    return Parts(pipeline, voices, standby, profile, StoredFollowUp(store), end_pause)
