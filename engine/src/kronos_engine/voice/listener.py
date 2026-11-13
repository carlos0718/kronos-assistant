"""La pieza que escucha: micrófono → fin de frase → transcripción."""

from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import AbstractAsyncContextManager
from typing import Protocol

import numpy as np

from kronos_engine.voice.endpointing import EndpointConfig, Endpointer, Verdict

OpenMicrophone = Callable[[], AbstractAsyncContextManager[AsyncIterator[np.ndarray]]]


class Vad(Protocol):
    def reset(self) -> None: ...

    def probability(self, frame: np.ndarray) -> float: ...


class Stt(Protocol):
    async def transcribe(self, audio: np.ndarray) -> str: ...


async def capture(
    microphone: AsyncIterator[np.ndarray], vad: Vad, config: EndpointConfig
) -> np.ndarray | None:
    """Lee cuadros de un micrófono ya abierto hasta el fin de la frase.

    Devuelve None si venció el plazo sin que nadie hablara.
    """
    vad.reset()
    endpointer = Endpointer(config)
    # Mientras nadie habla solo se guarda lo que puede llegar a ser el comienzo
    # de la frase: así la espera puede durar lo que haga falta.
    keep = config.frames(config.pre_roll_ms) + config.frames(config.min_speech_ms)
    frames: list[np.ndarray] = []
    dropped = 0
    async for frame in microphone:
        frames.append(frame)
        verdict = endpointer.feed(vad.probability(frame))
        if verdict is Verdict.DONE:
            return np.concatenate(frames[endpointer.first_frame - dropped :])
        if verdict is Verdict.NO_SPEECH:
            return None
        if verdict is Verdict.WAITING and len(frames) > keep:
            del frames[0]
            dropped += 1
    return None


class VoiceListener:
    def __init__(
        self,
        open_microphone: OpenMicrophone,
        vad: Vad,
        stt: Stt,
        config: EndpointConfig | None = None,
    ) -> None:
        self._open_microphone = open_microphone
        self._vad = vad
        self._stt = stt
        self._config = config or EndpointConfig()

    async def listen(
        self, on_speech_end: Callable[[], Awaitable[None]] | None = None
    ) -> str | None:
        async with self._open_microphone() as microphone:
            audio = await capture(microphone, self._vad, self._config)
        if audio is None:
            return None
        # El micrófono ya está cerrado: transcribir puede tardar un momento.
        if on_speech_end:
            await on_speech_end()
        return await self._stt.transcribe(audio)
