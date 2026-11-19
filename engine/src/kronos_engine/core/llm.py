"""Interfaz de los modelos de lenguaje.

Cada proveedor (Ollama, Anthropic, OpenAI…) la implementa en `llm/`. El resto
del motor solo conoce esta interfaz.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

from kronos_engine.core.tools import ToolCall, ToolSpec

Role = Literal["system", "user", "assistant", "tool"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str
    # Acciones que pidió el modelo en este mensaje (solo con el rol "assistant").
    tool_calls: tuple[ToolCall, ...] = ()
    # De qué acción es el resultado (solo con el rol "tool").
    tool_name: str = ""
    # El id de esa acción, si el proveedor le dio uno.
    tool_call_id: str = ""
    # Lo que hizo el modelo por su cuenta antes de responder, como buscar en
    # internet (solo con el rol "assistant"). No se dijo en voz alta.
    aside: str = ""


@dataclass(frozen=True)
class Aside:
    """Una nota del proveedor sobre la respuesta, para recordar y no para decir.

    Claude busca en internet en los servidores de Anthropic: sin esta nota, en
    el turno siguiente no sabe de dónde salió lo que contestó y lo pone en duda.
    """

    text: str


class LLMError(RuntimeError):
    """El modelo no pudo responder. El mensaje se le muestra al usuario."""


class LLMProvider(Protocol):
    def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall | Aside]:
        """Genera la respuesta a la conversación, de a pedazos.

        Cada pedazo es texto, una acción de `tools` que el modelo pide ejecutar,
        o una nota sobre la respuesta que no se dice en voz alta.
        """
        ...
