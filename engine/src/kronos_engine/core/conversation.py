"""Orquestador de la conversación: escuchar → modelo → hablar, y de nuevo.

No sabe de audio ni de modelos: recibe tres piezas intercambiables y avisa a
la interfaz qué va pasando.
"""

import asyncio
import contextlib
import logging
import time
from collections.abc import AsyncIterator, Awaitable, Callable
from dataclasses import dataclass
from typing import Any, Protocol

from kronos_engine.core.protocol import AssistantState, ServerMessage
from kronos_engine.core.sentences import SentenceSplitter
from kronos_engine.core.timing import Clock, Step, TurnTimer

log = logging.getLogger(__name__)


class Listener(Protocol):
    async def listen(
        self,
        on_speech_end: Callable[[], Awaitable[None]] | None = None,
        wait_seconds: float | None = None,
    ) -> str | None:
        """Escucha hasta el fin de la frase y devuelve lo que entendió.

        Llama a `on_speech_end` cuando deja de escuchar y pasa a transcribir.
        `wait_seconds` es cuánto espera a que alguien empiece a hablar; sin
        ese dato usa su propia espera. Devuelve `None` si nadie habló, y un
        texto vacío si oyó algo pero no lo entendió.
        """
        ...


class Responder(Protocol):
    def respond(self, text: str) -> AsyncIterator[str]:
        """Genera la respuesta de a pedazos, a medida que el modelo la produce."""
        ...


class Speaker(Protocol):
    async def speak(
        self, sentences: AsyncIterator[str], on_start: Callable[[], None] | None = None
    ) -> None:
        """Dice las frases a medida que llegan.

        Llama a `on_start` cuando empieza a sonar la primera. Vuelve cuando
        terminó de sonar la última.
        """
        ...


@dataclass(frozen=True)
class Pipeline:
    listener: Listener
    responder: Responder
    speaker: Speaker


SetState = Callable[[AssistantState], Awaitable[None]]
Emit = Callable[[ServerMessage, dict[str, Any]], Awaitable[None]]
# Segundos que se espera otra frase después de responder; cero es no esperar.
FollowUp = Callable[[], float]


async def _drain(sentences: asyncio.Queue[str | None]) -> AsyncIterator[str]:
    """Entrega las frases de la cola hasta la marca de fin (`None`)."""
    while (sentence := await sentences.get()) is not None:
        yield sentence


class Conversation:
    def __init__(
        self,
        pipeline: Pipeline,
        set_state: SetState,
        emit: Emit,
        follow_up: FollowUp | None = None,
        clock: Clock = time.perf_counter,
    ) -> None:
        """`follow_up` se consulta después de cada respuesta: el usuario puede cambiarla.

        Sin ella, la espera es siempre la del oyente. `clock` mide cuánto
        tarda cada turno.
        """
        self._pipeline = pipeline
        self._follow_up = follow_up
        self._clock = clock
        self._timer = TurnTimer(clock)
        self._notify_state = set_state
        self._state = AssistantState.IDLE
        self._emit = emit
        self._turn: asyncio.Task[None] | None = None

    async def activate(self, heard: str = "") -> None:
        """Empieza una conversación. Si había una en curso, la reemplaza.

        `heard` es lo que el usuario ya dijo al llamar a Kronos por su nombre:
        se responde a eso sin volver a escuchar.
        """
        await self.cancel()
        self._turn = asyncio.create_task(self._run(heard.strip()))

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
        self._timer.mark(Step.SPEECH_END)
        await self._set_state(AssistantState.THINKING)

    async def _run(self, heard: str) -> None:
        error: str | None = None
        # Si el pedido ya se oyó junto con el nombre, el turno empieza con el texto.
        self._timer = TurnTimer(self._clock)
        try:
            text: str | None = heard or await self._listen()
            # Hasta la primera respuesta la espera es la del oyente; después,
            # la que eligió el usuario.
            wait_seconds: float | None = None
            # Después de responder vuelve a escuchar, por si el usuario sigue.
            # La conversación termina cuando nadie habla.
            while text is not None:
                if text:
                    self._timer.mark(Step.TRANSCRIBED)
                    # No se registra lo que se dijo, solo cuánto: puede ser privado.
                    log.info("Frase entendida (%d caracteres); responde el modelo.", len(text))
                    await self._emit(ServerMessage.TRANSCRIPT_FINAL, {"text": text})
                    await self._set_state(AssistantState.THINKING)
                    await self._reply(text)
                    if summary := self._timer.summary():
                        log.info("Tiempos del turno: %s.", summary)
                    if self._follow_up:
                        wait_seconds = self._follow_up()
                else:
                    # Un ruido o algo que no se pudo transcribir: sigue escuchando.
                    log.info("Se oyó algo que no se entendió; sigue escuchando.")
                text = await self._listen(wait_seconds)
        except Exception as exc:  # noqa: BLE001 - cualquier fallo se le informa al usuario.
            error = str(exc) or type(exc).__name__
            log.warning("La conversación terminó por un fallo: %s", error)
        finally:
            await self._set_state(AssistantState.IDLE)
        # Va después del estado: la interfaz borra el error al cambiar de estado.
        if error:
            await self._emit(ServerMessage.ERROR, {"message": error})

    async def _listen(self, wait_seconds: float | None = None) -> str | None:
        if wait_seconds is not None and wait_seconds <= 0:
            log.info("Seguir escuchando está apagado; termina la conversación.")
            return None
        await self._set_state(AssistantState.LISTENING)
        self._timer = TurnTimer(self._clock)
        text = await self._pipeline.listener.listen(self._stop_listening, wait_seconds)
        if text is None:
            # Con la espera a la vista se distingue un plazo corto de un micrófono que no oye.
            waited = "" if wait_seconds is None else f" en {wait_seconds:g} s"
            log.info("Nadie habló%s; termina la conversación.", waited)
            return None
        return text.strip()

    async def _reply(self, text: str) -> None:
        # La voz corre en paralelo: dice cada frase mientras el modelo sigue generando.
        sentences: asyncio.Queue[str | None] = asyncio.Queue()
        timer = self._timer
        speaking = asyncio.create_task(
            self._pipeline.speaker.speak(_drain(sentences), lambda: timer.mark(Step.FIRST_SOUND))
        )
        splitter = SentenceSplitter()
        started = False
        try:
            async for delta in self._pipeline.responder.respond(text):
                if not started:
                    started = True
                    await self._set_state(AssistantState.SPEAKING)
                await self._emit(ServerMessage.ASSISTANT_DELTA, {"text": delta})
                for sentence in splitter.feed(delta):
                    timer.mark(Step.FIRST_SENTENCE)
                    sentences.put_nowait(sentence)
            if rest := splitter.flush():
                timer.mark(Step.FIRST_SENTENCE)
                sentences.put_nowait(rest)
            sentences.put_nowait(None)
            await speaking
        finally:
            if not speaking.done():
                speaking.cancel()
            with contextlib.suppress(asyncio.CancelledError, Exception):
                await speaking
