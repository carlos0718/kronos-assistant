"""La pieza que responde: arma la conversación, se la pasa al modelo y ejecuta lo que pide."""

from collections.abc import AsyncGenerator, Callable

from kronos_engine.core.llm import LLMProvider, Message
from kronos_engine.core.tools import Toolbox, ToolCall

# Cuántas veces seguidas puede pedir acciones el modelo antes de tener que contestar.
MAX_TOOL_ROUNDS = 5


class AgentResponder:
    """Responde con un modelo, recordando los últimos turnos.

    `instructions` se pide en cada turno: así un cambio en el perfil del
    usuario se nota en la próxima respuesta, sin reiniciar el motor.

    Si el modelo pide una acción de `tools`, se ejecuta y el modelo recibe el
    resultado para seguir respondiendo. Qué se ejecuta y qué no lo decide
    `tools`, no esta clase ni el modelo.

    La memoria vive solo mientras el motor está abierto. La memoria
    persistente llega en la Fase 3.
    """

    def __init__(
        self,
        provider: LLMProvider,
        instructions: Callable[[], str],
        max_turns: int = 10,
        tools: Toolbox | None = None,
    ) -> None:
        self._provider = provider
        self._instructions = instructions
        self._max_turns = max_turns
        self._tools = tools
        # Un turno es lo que dijo el usuario y todo lo que siguió hasta la respuesta.
        self._history: list[list[Message]] = []

    async def respond(self, text: str) -> AsyncGenerator[str]:
        system = Message("system", self._instructions())
        past = [message for turn in self._history for message in turn]
        turn = [Message("user", text)]
        tools = self._tools
        specs = tools.specs() if tools else ()
        for round_number in range(MAX_TOOL_ROUNDS + 1):
            # En la última vuelta no se ofrecen acciones: el modelo tiene que contestar.
            offered = specs if round_number < MAX_TOOL_ROUNDS else ()
            reply = ""
            calls: list[ToolCall] = []
            async for piece in self._provider.stream([system, *past, *turn], offered):
                if isinstance(piece, ToolCall):
                    calls.append(piece)
                else:
                    reply += piece
                    yield piece
            if tools is None or not offered or not calls:
                # Una acción pedida sin que se la ofrecieran no se ejecuta.
                turn.append(Message("assistant", reply))
                break
            turn.append(Message("assistant", reply, tuple(calls)))
            if reply:
                # Lo dicho antes de la acción es una frase aparte: se empieza a
                # decir mientras la acción corre y no se pega con lo que sigue.
                yield "\n"
            for call in calls:
                result = await tools.run(call)
                turn.append(Message("tool", result, tool_name=call.name, tool_call_id=call.id))
        # Solo se recuerda el turno si terminó: uno cortado o fallido no dejó respuesta.
        self._history.append(turn)
        del self._history[: -self._max_turns]
