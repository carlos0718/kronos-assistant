"""Arma las piezas con las que arranca el motor."""

import os
import sys
from collections.abc import Callable
from dataclasses import dataclass

from kronos_engine.core.approval import ApprovalDesk
from kronos_engine.core.choosing import Chooser
from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.demo import (
    DemoEndPause,
    DemoFolderAccess,
    DemoFollowUp,
    DemoModel,
    DemoProfile,
    DemoRecognizer,
    DemoSecretKey,
    DemoVoices,
    DemoWakeWord,
    demo_pipeline,
)
from kronos_engine.core.end_pause import EndPauseControl
from kronos_engine.core.folder_access import FolderAccess, FolderAccessControl
from kronos_engine.core.follow_up import FollowUpControl
from kronos_engine.core.model_choice import ModelControl
from kronos_engine.core.profile import ProfileControl
from kronos_engine.core.recognizer import RecognizerControl
from kronos_engine.core.secret import SecretKeyControl
from kronos_engine.core.standby import Standby
from kronos_engine.core.tools import Tool
from kronos_engine.core.voices import VoiceControl
from kronos_engine.voice.assembly import (
    conversation_tts,
    starting_voice,
    tts_for,
    voice_catalog,
)

# KRONOS_PIPELINE=demo usa las piezas simuladas, sin micrófono ni modelos.
PIPELINE_ENV = "KRONOS_PIPELINE"
# Idioma en que se transcribe ("es", "en"). PROVISORIO: irá en la configuración.
LANGUAGE_ENV = "KRONOS_LANGUAGE"
# Modelo que transcribe, para probar uno sin pasar por la pestaña Voz (si el
# usuario eligió uno ahí, gana el suyo): "parakeet", "elevenlabs" o un tamaño de
# whisper ("base", "small", "medium"…). Parakeet es mucho más rápido; los tiempos
# están en docs/MEDICIONES.md. "elevenlabs" transcribe en la nube, de pago, con la
# clave de la pestaña Voz: lo que oye el micrófono sale de la computadora, incluso
# en reposo.
STT_MODEL_ENV = "KRONOS_STT_MODEL"

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
    folder_access: FolderAccessControl
    model: ModelControl
    recognizer: RecognizerControl
    secret_key: SecretKeyControl


def available_tools(
    folder_access: Callable[[], FolderAccess] = FolderAccess, chooser: Chooser | None = None
) -> list[Tool]:
    """Las acciones que Kronos puede ejecutar en este sistema.

    `folder_access` dice qué carpetas puede mirar; se lee en cada pedido. `chooser`
    elige por el significado lo que no se encuentra por las palabras.
    """
    from kronos_engine.tools.apps import CloseAppTool, OpenAppTool
    from kronos_engine.tools.clock import CurrentTimeTool
    from kronos_engine.tools.files import OpenFileTool
    from kronos_engine.tools.folders import OpenFolderTool
    from kronos_engine.tools.terminal import RunCommandTool
    from kronos_engine.tools.volume import VolumeTool
    from kronos_engine.tools.weather import WeatherTool

    # El clima consulta Open-Meteo por internet: anda con cualquier modelo.
    tools: list[Tool] = [CurrentTimeTool(), WeatherTool()]
    if sys.platform == "win32":
        from kronos_engine.platform.windows.apps import WindowsPlatform
        from kronos_engine.platform.windows.shell import PowerShell
        from kronos_engine.platform.windows.volume import WindowsVolume

        platform = WindowsPlatform()
        platform.preload()
        tools += [
            OpenAppTool(platform),
            CloseAppTool(platform),
            OpenFolderTool(platform, folder_access, chooser),
            OpenFileTool(platform, folder_access, chooser),
            VolumeTool(WindowsVolume()),
            RunCommandTool(PowerShell()),
        ]
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
            DemoFolderAccess(),
            DemoModel(),
            DemoRecognizer(),
            DemoSecretKey(),
        )

    # Se importan acá para que el modo demo no dependa de las librerías de voz.
    from kronos_engine.agent.chooser import ModelChooser
    from kronos_engine.agent.instructions import instructions_for
    from kronos_engine.agent.responder import AgentResponder
    from kronos_engine.config.elevenlabs_key import StoredElevenLabsKey, move_from_env
    from kronos_engine.config.end_pause import StoredEndPause
    from kronos_engine.config.folder_access import StoredFolderAccess
    from kronos_engine.config.follow_up import StoredFollowUp
    from kronos_engine.config.model_choice import StoredModelChoice
    from kronos_engine.config.profile import StoredProfile
    from kronos_engine.config.recognizer import StoredRecognizer
    from kronos_engine.config.settings import SettingsStore
    from kronos_engine.llm.anthropic import AnthropicProvider
    from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider
    from kronos_engine.llm.switching import SwitchingProvider
    from kronos_engine.permissions.gate import PermissionGate
    from kronos_engine.permissions.secret_key import SecretKey
    from kronos_engine.platform.windows.credentials import WindowsCredentials
    from kronos_engine.voice.catalog import DEFAULT_VOICES
    from kronos_engine.voice.elevenlabs import KEY_ENV
    from kronos_engine.voice.fallback import Outage
    from kronos_engine.voice.listener import VoiceListener
    from kronos_engine.voice.microphone import open_microphone
    from kronos_engine.voice.playback import play
    from kronos_engine.voice.speaker import VoiceSpeaker
    from kronos_engine.voice.switching_stt import SwitchingStt
    from kronos_engine.voice.vad import SileroVad
    from kronos_engine.voice.voices import RoutedTts, SelectableVoices
    from kronos_engine.voice.wake import WhisperWakeWord

    language = os.environ.get(LANGUAGE_ENV, "es")
    store = SettingsStore()
    settings = store.load()
    default_voice = DEFAULT_VOICES.get(language, DEFAULT_VOICES["es"])

    # Si ElevenLabs no responde, transcribir y hablar pasan juntos a la computadora.
    outage = Outage()
    # Con una clave nueva se vuelve a probar ElevenLabs enseguida, sin esperar la pausa.
    key = StoredElevenLabsKey(WindowsCredentials(), on_change=outage.reset)
    move_from_env(key, os.environ.get(KEY_ENV, ""))
    # Los tres modelos se cargan mientras el usuario todavía no habló. El reconocedor se
    # elige en cada frase; al cambiarlo se carga el nuevo sin esperar a que hable.
    stt_choice = StoredRecognizer(
        store,
        lambda: bool(key.get()),
        from_env=os.environ.get(STT_MODEL_ENV, ""),
        on_change=lambda: stt.preload(),
    )
    stt = SwitchingStt(stt_choice.get, language, outage, key.get)
    stt.preload()
    voice = starting_voice(
        settings.voice or os.environ.get(VOICE_ENV), default_voice, has_key=bool(key.get())
    )
    tts = RoutedTts(voice, conversation_tts(default_voice, outage, key.get))
    tts.preload()
    local = OllamaProvider(
        os.environ.get(MODEL_ENV, DEFAULT_MODEL),
        base_url=os.environ.get(OLLAMA_URL_ENV, DEFAULT_URL),
    )
    # Ollama de fábrica; Claude si el usuario lo elige (la clave, en Windows).
    choice = StoredModelChoice(store, WindowsCredentials())
    model = SwitchingProvider(choice, local, AnthropicProvider)
    model.preload()

    profile = StoredProfile(store)
    end_pause = StoredEndPause(store)
    folder_access = StoredFolderAccess(store)
    # El modelo propone las acciones; el control de permisos decide si se
    # ejecutan y, para las delicadas, le pregunta al usuario.
    approvals = ApprovalDesk()
    # Las acciones críticas piden la clave secreta, que se escribe en pantalla.
    secret_key = SecretKey(WindowsCredentials())
    tools = PermissionGate(
        available_tools(folder_access.get, ModelChooser(model)), approvals, secret_key, approvals
    )

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
        tts,
        lambda voice: tts_for(voice, key.get),
        play,
        lambda voice: store.update(voice=voice),
        catalog=voice_catalog(key.get),
        key=key,
        local_voice=default_voice,
    )
    return Parts(
        pipeline,
        voices,
        standby,
        profile,
        StoredFollowUp(store),
        end_pause,
        folder_access,
        choice,
        stt_choice,
        secret_key,
    )
