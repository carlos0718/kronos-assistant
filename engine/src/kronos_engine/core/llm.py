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


class LLMError(RuntimeError):
    """El modelo no pudo responder. El mensaje se le muestra al usuario."""


class LLMProvider(Protocol):
    def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall]:
        """Genera la respuesta a la conversación, de a pedazos.

        Cada pedazo es texto, o una acción de `tools` que el modelo pide ejecutar.
        """
        ...
