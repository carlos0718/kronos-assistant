"""La pieza que responde: arma la conversación y se la pasa al modelo."""

from collections.abc import AsyncGenerator, Callable

from kronos_engine.core.llm import LLMProvider, Message


class AgentResponder:
    """Responde con un modelo, recordando los últimos turnos.

    `instructions` se pide en cada turno: así un cambio en el perfil del
    usuario se nota en la próxima respuesta, sin reiniciar el motor.

    La memoria vive solo mientras el motor está abierto. La memoria
    persistente llega en la Fase 3.
    """

    def __init__(
        self, provider: LLMProvider, instructions: Callable[[], str], max_turns: int = 10
    ) -> None:
        self._provider = provider
        self._instructions = instructions
        self._max_messages = max_turns * 2  # Cada turno: lo que dijo el usuario y la respuesta.
        self._history: list[Message] = []

    async def respond(self, text: str) -> AsyncGenerator[str]:
        system = Message("system", self._instructions())
        question = Message("user", text)
        reply = ""
        async for delta in self._provider.stream([system, *self._history, question]):
            reply += delta
            yield delta
        # Solo se recuerda el turno si terminó: uno cortado o fallido no dejó respuesta.
        self._history += [question, Message("assistant", reply)]
        del self._history[: -self._max_messages]
