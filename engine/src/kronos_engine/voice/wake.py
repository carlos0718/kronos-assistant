"""Palabra de activación sin modelo propio: transcribe lo que oye y busca "Kronos".

Usa el detector de voz y el whisper que ya están cargados, así no hay que
entrenar ni descargar nada. A cambio, transcribe cada frase que se dice cerca
del micrófono: gasta más que un detector entrenado para una sola palabra.
"""

import logging
import re
import unicodedata

from kronos_engine.voice.endpointing import EndpointConfig
from kronos_engine.voice.listener import OpenMicrophone, Stt, Vad, capture

log = logging.getLogger(__name__)

# Cómo escribe whisper el nombre, sin acentos y en minúsculas.
_SPELLINGS = frozenset({"kronos", "cronos", "chronos", "khronos", "kronus", "cronus"})
# Lo que puede quedar pegado al nombre: "Kronos, …", "…, Kronos".
_SEPARATORS = " ,.;:!?-—…"
# Con menos palabras, lo que va antes del nombre es un saludo ("hola, Kronos").
_MIN_REQUEST_WORDS = 3

WAKE_ENDPOINTS = EndpointConfig(
    # Más exigente que en una conversación: un golpe o una tos no se transcriben.
    min_speech_ms=192,
    # La espera no vence: el micrófono queda abierto hasta que alguien habla.
    start_timeout_ms=3_600_000,
    # Una charla de fondo no se acumula: se transcribe de a tramos cortos.
    max_utterance_ms=15_000,
)


def _plain(word: str) -> str:
    decomposed = unicodedata.normalize("NFD", word.lower())
    return "".join(char for char in decomposed if not unicodedata.combining(char))


def after_wake_word(text: str) -> str | None:
    """Busca el nombre de Kronos en una frase.

    Devuelve None si no lo nombra. Si lo nombra, devuelve el pedido que lo
    acompaña, o un texto vacío si solo lo llamó.
    """
    for word in re.finditer(r"\w+", text):
        if _plain(word.group()) not in _SPELLINGS:
            continue
        after = text[word.end() :]
        if request := after.lstrip(_SEPARATORS).strip():
            return request
        before = text[: word.start()].rstrip(_SEPARATORS)
        if len(before.split()) >= _MIN_REQUEST_WORDS:
            # "¿Qué hora es, Kronos?": se conserva el cierre de la pregunta.
            return before + after.strip()
        return ""
    return None


class WhisperWakeWord:
    """Implementa `WakeWord` con el detector de voz y el reconocedor de siempre."""

    def __init__(
        self,
        open_microphone: OpenMicrophone,
        vad: Vad,
        stt: Stt,
        config: EndpointConfig = WAKE_ENDPOINTS,
    ) -> None:
        self._open_microphone = open_microphone
        self._vad = vad
        self._stt = stt
        self._config = config

    async def wait(self) -> str:
        async with self._open_microphone() as microphone:
            while True:
                audio = await capture(microphone, self._vad, self._config)
                if audio is None:
                    continue
                # Lo que no nombra a Kronos se descarta acá: ni se guarda ni se registra.
                request = after_wake_word(await self._stt.transcribe(audio))
                if request is not None:
                    return request
