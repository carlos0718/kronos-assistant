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
        audio = await self._capture()
        if audio is None:
            return None
        # El micrófono ya está cerrado: transcribir puede tardar un momento.
        if on_speech_end:
            await on_speech_end()
        return await self._stt.transcribe(audio)

    async def _capture(self) -> np.ndarray | None:
        """Graba hasta el fin de la frase. Devuelve None si nadie habló."""
        self._vad.reset()
        endpointer = Endpointer(self._config)
        frames: list[np.ndarray] = []
        verdict = Verdict.NO_SPEECH
        async with self._open_microphone() as microphone:
            async for frame in microphone:
                frames.append(frame)
                verdict = endpointer.feed(self._vad.probability(frame))
                if verdict in (Verdict.DONE, Verdict.NO_SPEECH):
                    break
        if verdict is not Verdict.DONE:
            return None
        return np.concatenate(frames[endpointer.first_frame :])
