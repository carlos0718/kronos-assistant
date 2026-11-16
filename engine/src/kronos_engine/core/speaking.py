"""Lo que Kronos va diciendo en un turno, frase por frase."""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable

# La forma de `Speaker.speak`: recibe las frases y a quién avisarle cuando empieza a sonar.
Speak = Callable[[AsyncIterator[str], Callable[[], None] | None], Awaitable[None]]


async def _drain(sentences: asyncio.Queue[str | None]) -> AsyncIterator[str]:
    """Entrega las frases de la cola hasta la marca de fin (`None`)."""
    while (sentence := await sentences.get()) is not None:
        yield sentence


class SpokenReply:
    """Manda las frases a la voz mientras el modelo sigue generando.

    La voz corre en paralelo. `finish` espera a que termine de sonar lo dicho
    hasta ese momento; después se puede seguir diciendo.
    """

    def __init__(self, speak: Speak, on_start: Callable[[], None] | None = None) -> None:
        self._speak = speak
        self._on_start = on_start
        self._sentences: asyncio.Queue[str | None] = asyncio.Queue()
        self._speaking: asyncio.Task[None] | None = None

    def say(self, sentence: str) -> None:
        if self._speaking is None:
            self._sentences = asyncio.Queue()
            self._speaking = asyncio.ensure_future(
                self._speak(_drain(self._sentences), self._on_start)
            )
        self._sentences.put_nowait(sentence)

    async def finish(self) -> None:
        """Espera a que termine de sonar todo lo dicho. Si la voz falló, el error sale acá."""
        speaking, self._speaking = self._speaking, None
        if speaking is None:
            return
        self._sentences.put_nowait(None)
        try:
            await speaking
        finally:
            await _stop(speaking)

    async def abort(self) -> None:
        """Corta lo que esté sonando."""
        speaking, self._speaking = self._speaking, None
        if speaking is not None:
            await _stop(speaking)


async def _stop(speaking: asyncio.Task[None]) -> None:
    if not speaking.done():
        speaking.cancel()
    with contextlib.suppress(asyncio.CancelledError, Exception):
        await speaking
