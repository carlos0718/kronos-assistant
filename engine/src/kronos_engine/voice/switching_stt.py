"""El reconocedor que el usuario eligió en la pestaña Voz.

La elección y la clave se leen en cada frase: cambiar de reconocedor se nota en la
próxima, sin reiniciar el motor. Cada reconocedor se arma la primera vez que se usa y
se conserva; Parakeet se comparte con el respaldo de ElevenLabs, así no se carga dos veces.
"""

import threading
from collections.abc import Callable
from typing import Protocol

import numpy as np

from kronos_engine.core.recognizer import ELEVENLABS, PARAKEET
from kronos_engine.voice.assembly import stt_for
from kronos_engine.voice.fallback import FallbackStt, Outage


class Stt(Protocol):
    def preload(self) -> None: ...

    async def transcribe(self, audio: np.ndarray) -> str: ...


class SwitchingStt:
    """Implementa el reconocedor pasándole cada frase al elegido.

    Sin clave de ElevenLabs, reconoce Parakeet aunque esté elegido ElevenLabs: así no se
    espera a que falle ni se cuenta como una caída de la nube.
    """

    def __init__(
        self,
        choice: Callable[[], str],
        language: str,
        outage: Outage,
        key: Callable[[], str],
    ) -> None:
        self._choice = choice
        self._language = language
        self._outage = outage
        self._key = key
        self._made: dict[str, Stt] = {}
        # Rentrante: armar la nube pide Parakeet, con el candado ya tomado.
        self._lock = threading.RLock()

    def preload(self) -> None:
        """Carga el elegido, sin esperar a la próxima frase."""
        self._current().preload()

    async def transcribe(self, audio: np.ndarray) -> str:
        return await self._current().transcribe(audio)

    def _current(self) -> Stt:
        name = self._choice()
        if name == ELEVENLABS and not self._key():
            name = PARAKEET
        return self._get(name)

    def _get(self, name: str) -> Stt:
        with self._lock:
            if name not in self._made:
                self._made[name] = self._make(name)
            return self._made[name]

    def _make(self, name: str) -> Stt:
        if name != ELEVENLABS:
            return stt_for(name, self._language, self._key)
        # La nube, con Parakeet de respaldo; el mismo Parakeet que usa quien lo elige solo.
        return FallbackStt(
            stt_for(ELEVENLABS, self._language, self._key),
            self._get(PARAKEET),
            self._outage,
        )
