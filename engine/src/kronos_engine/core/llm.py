"""Interfaz de los modelos de lenguaje.

Cada proveedor (Ollama, Anthropic, OpenAI…) la implementa en `llm/`. El resto
del motor solo conoce esta interfaz.
"""

from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass
from typing import Literal, Protocol

Role = Literal["system", "user", "assistant"]


@dataclass(frozen=True)
class Message:
    role: Role
    content: str


class LLMError(RuntimeError):
    """El modelo no pudo responder. El mensaje se le muestra al usuario."""


class LLMProvider(Protocol):
    def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        """Genera la respuesta a la conversación, de a pedazos."""
        ...
