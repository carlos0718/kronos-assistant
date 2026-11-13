"""Orquestador de la conversación: escuchar → modelo → hablar, y de nuevo.

No sabe de audio ni de modelos: recibe tres piezas intercambiables y avisa a
la interfaz qué va pasando.
"""

import asyncio
import contextlib
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from kronos_engine.core.protocol import AssistantState, ServerMessage
from kronos_engine.core.sentences import SentenceSplitter


class Listener(Protocol):
    async def listen(self, on_speech_end: Callable[[], Awaitable[None]] | None = None) -> str:
        """Escucha hasta el fin de la frase y devuelve lo que entendió.

        Llama a `on_speech_end` cuando deja de escuchar y pasa a transcribir.
        Devuelve un texto vacío si nadie habló.
        """
        ...


class Responder(Protocol):
    def respond(self, text: str) -> AsyncIterator[str]:
        """Genera la respuesta de a pedazos, a medida que el modelo la produce."""
        ...


class Speaker(Protocol):
    async def speak(self, text: str) -> None:
        """Dice una frase y vuelve cuando terminó de sonar."""
        ...


@dataclass(frozen=True)
class Pipeline:
    listener: Listener
    responder: Responder
    speaker: Speaker


SetState = Callable[[AssistantState], Awaitable[None]]
Emit = Callable[[ServerMessage, dict[str, Any]], Awaitable[None]]


class Conversation:
    def __init__(self, pipeline: Pipeline, set_state: SetState, emit: Emit) -> None:
        self._pipeline = pipeline
        self._notify_state = set_state
        self._state = AssistantState.IDLE
        self._emit = emit
        self._turn: asyncio.Task[None] | None = None

    async def activate(self) -> None:
        """Empieza una conversación. Si había una en curso, la reemplaza."""
        await self.cancel()
        self._turn = asyncio.create_task(self._run())

    async def cancel(self) -> None:
        """Corta la conversación en curso, si la hay."""
        turn, self._turn = self._turn, None
        if turn and not turn.done():
            turn.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await turn

    async def wait(self) -> None:
        """Espera a que termine la conversación en curso."""
        if self._turn:
            await self._turn

    async def _set_state(self, state: AssistantState) -> None:
        if state != self._state:
            self._state = state
            await self._notify_state(state)

    async def _stop_listening(self) -> None:
        # El micrófono ya se cerró: la interfaz deja de mostrar "escuchando".
        await self._set_state(AssistantState.THINKING)

    async def _run(self) -> None:
        error: str | None = None
        try:
            # Después de responder vuelve a escuchar, por si el usuario sigue.
            # La conversación termina cuando nadie habla.
            while text := await self._listen():
                await self._emit(ServerMessage.TRANSCRIPT_FINAL, {"text": text})
                await self._set_state(AssistantState.THINKING)
                await self._reply(text)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo se le informa al usuario.
            error = str(exc) or type(exc).__name__
        finally:
            await self._set_state(AssistantState.IDLE)
        # Va después del estado: la interfaz borra el error al cambiar de estado.
        if error:
            await self._emit(ServerMessage.ERROR, {"message": error})

    async def _listen(self) -> str:
        await self._set_state(AssistantState.LISTENING)
        return (await self._pipeline.listener.listen(self._stop_listening)).strip()

    async def _reply(self, text: str) -> None:
        # La voz corre en paralelo: dice cada frase mientras el modelo sigue generando.
        sentences: asyncio.Queue[str | None] = asyncio.Queue()
        speaking = asyncio.create_task(self._speak_all(sentences))
        splitter = SentenceSplitter()
        started = False
        try:
            async for delta in self._pipeline.responder.respond(text):
                if not started:
                    started = True
                    await self._set_state(AssistantState.SPEAKING)
                await self._emit(ServerMessage.ASSISTANT_DELTA, {"text": delta})
                for sentence in splitter.feed(delta):
                    sentences.put_nowait(sentence)
            if rest := splitter.flush():
                sentences.put_nowait(rest)
            sentences.put_nowait(None)
            await speaking
        finally:
            if not speaking.done():
                speaking.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await speaking

    async def _speak_all(self, sentences: asyncio.Queue[str | None]) -> None:
        while (sentence := await sentences.get()) is not None:
            await self._pipeline.speaker.speak(sentence)
