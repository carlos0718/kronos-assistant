"""Respaldo en la computadora para cuando la nube no responde.

ElevenLabs transcribe y habla por internet. Si no contesta a tiempo, o falla
(sin conexión, la clave rechazada, sin cuota), esa frase la resuelve lo que
corre en la computadora: Parakeet para transcribir y Piper para hablar. Así la
conversación sigue en lugar de cortarse a los 30 s.

Después de un fallo, `Outage` deja de probar la nube por un rato: sin internet,
cada frase esperaría el plazo entero. Transcribir y hablar comparten el mismo
`Outage`, porque si una falla lo más probable es que falle la otra.
"""

import asyncio
import logging
import time
from collections.abc import Awaitable, Callable
from typing import Protocol

import numpy as np

from kronos_engine.voice.speaker import Speech

log = logging.getLogger(__name__)

# Segundos que se espera a la nube antes de usar el respaldo. ElevenLabs tarda
# 1,2 s de mediana en transcribir una frase (docs/MEDICIONES.md).
TIMEOUT = 3.0
# Segundos sin probar la nube después de un fallo.
PAUSE = 60.0


class Outage:
    """Recuerda que la nube falló hace poco, para no esperarla en cada frase."""

    def __init__(
        self,
        name: str = "ElevenLabs",
        pause: float = PAUSE,
        clock: Callable[[], float] = time.monotonic,
    ) -> None:
        self._name = name
        self._pause = pause
        self._clock = clock
        self._failed_at: float | None = None

    def active(self) -> bool:
        return self._failed_at is not None and self._clock() - self._failed_at < self._pause

    def failed(self, reason: str) -> None:
        self._failed_at = self._clock()
        log.warning(
            "%s no respondió (%s): por %d s se usa lo de la computadora.",
            self._name,
            reason,
            self._pause,
        )

    def reset(self) -> None:
        """Vuelve a probar la nube en la próxima frase: por ejemplo, porque cambió la clave."""
        self._failed_at = None

    def answered(self) -> None:
        if self._failed_at is not None:
            self._failed_at = None
            log.info("%s volvió a responder.", self._name)


async def _first_that_answers[T](
    cloud: Callable[[], Awaitable[T]],
    local: Callable[[], Awaitable[T]],
    outage: Outage,
    seconds: float,
) -> T:
    if outage.active():
        return await local()
    try:
        result = await asyncio.wait_for(cloud(), seconds)
    except TimeoutError:
        outage.failed(f"tardó más de {seconds:g} s")
    except Exception as exc:  # noqa: BLE001 - sin conexión, clave rechazada o sin cuota: igual se sigue.
        outage.failed(str(exc) or type(exc).__name__)
    else:
        outage.answered()
        return result
    return await local()


class Stt(Protocol):
    def preload(self) -> None: ...

    async def transcribe(self, audio: np.ndarray) -> str: ...


class FallbackStt:
    """Transcribe con `cloud`; si no responde a tiempo, con `local`."""

    def __init__(self, cloud: Stt, local: Stt, outage: Outage, timeout: float = TIMEOUT) -> None:
        self._cloud = cloud
        self._local = local
        self._outage = outage
        self._timeout = timeout

    def preload(self) -> None:
        # El respaldo se carga desde el arranque: cuando haga falta no hay tiempo.
        self._cloud.preload()
        self._local.preload()

    async def transcribe(self, audio: np.ndarray) -> str:
        return await _first_that_answers(
            lambda: self._cloud.transcribe(audio),
            lambda: self._local.transcribe(audio),
            self._outage,
            self._timeout,
        )


class Tts(Protocol):
    @property
    def voice(self) -> str: ...

    def set_voice(self, voice: str) -> None: ...

    def preload(self) -> None: ...

    async def synthesize(self, text: str) -> Speech: ...


class FallbackTts:
    """Habla con la voz de `cloud`; si no responde a tiempo, esa frase la dice `local`.

    La voz elegida sigue siendo la de `cloud` aunque hable `local`.
    """

    def __init__(self, cloud: Tts, local: Tts, outage: Outage, timeout: float = TIMEOUT) -> None:
        self._cloud = cloud
        self._local = local
        self._outage = outage
        self._timeout = timeout

    @property
    def voice(self) -> str:
        return self._cloud.voice

    def set_voice(self, voice: str) -> None:
        self._cloud.set_voice(voice)

    def preload(self) -> None:
        self._cloud.preload()
        self._local.preload()

    async def synthesize(self, text: str) -> Speech:
        return await _first_that_answers(
            lambda: self._cloud.synthesize(text),
            lambda: self._local.synthesize(text),
            self._outage,
            self._timeout,
        )
