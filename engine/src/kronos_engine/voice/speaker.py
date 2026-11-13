"""La pieza que habla: texto → audio → altavoz."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Protocol

import numpy as np

from kronos_engine.voice.speakable import speakable


@dataclass(frozen=True)
class Speech:
    samples: np.ndarray  # Un canal, valores entre -1 y 1.
    sample_rate: int


class Tts(Protocol):
    async def synthesize(self, text: str) -> Speech: ...


Play = Callable[[np.ndarray, int], Awaitable[None]]


class VoiceSpeaker:
    def __init__(self, tts: Tts, play: Play) -> None:
        self._tts = tts
        self._play = play

    async def speak(self, sentences: AsyncIterator[str]) -> None:
        # Mientras suena una frase se va preparando la siguiente: así no queda
        # un silencio entre frase y frase.
        ready: asyncio.Queue[Speech | None] = asyncio.Queue()
        preparing = asyncio.create_task(self._prepare(sentences, ready))
        try:
            while (speech := await ready.get()) is not None:
                await self._play(speech.samples, speech.sample_rate)
            await preparing  # Si la preparación falló, el error sale acá.
        finally:
            preparing.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await preparing

    async def _prepare(
        self, sentences: AsyncIterator[str], ready: asyncio.Queue[Speech | None]
    ) -> None:
        try:
            async for sentence in sentences:
                if text := speakable(sentence):
                    ready.put_nowait(await self._tts.synthesize(text))
        finally:
            ready.put_nowait(None)  # Avisa que no hay más, también si falló.
