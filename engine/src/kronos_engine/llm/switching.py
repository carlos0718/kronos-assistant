"""El modelo que responde, el que el usuario eligió en la pestaña Modelo."""

import logging
from collections.abc import AsyncIterator, Callable, Sequence
from typing import Protocol

from kronos_engine.core.llm import LLMError, LLMProvider, Message
from kronos_engine.core.model_choice import ANTHROPIC, ANTHROPIC_MODELS, ModelControl
from kronos_engine.core.tools import ToolCall, ToolSpec

log = logging.getLogger(__name__)


class LocalProvider(LLMProvider, Protocol):
    def preload(self) -> None:
        """Carga el modelo mientras el usuario todavía no habló."""
        ...


class SwitchingProvider:
    """Implementa `LLMProvider` pasándole cada pedido al modelo elegido.

    La elección y la clave se leen en cada pedido: cambiar de modelo en la
    configuración se nota en la próxima respuesta, sin reiniciar el motor.
    """

    def __init__(
        self,
        control: ModelControl,
        local: LocalProvider,
        cloud: Callable[[str, str], LLMProvider],
    ) -> None:
        self._control = control
        self._local = local
        # Crea el proveedor de Claude con una clave y un modelo.
        self._make_cloud = cloud
        self._cloud: LLMProvider | None = None
        self._cloud_for: tuple[str, str] | None = None

    def preload(self) -> None:
        if self._control.get().provider != ANTHROPIC:
            self._local.preload()

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall]:
        async for piece in self._current().stream(messages, tools):
            yield piece

    def _current(self) -> LLMProvider:
        choice = self._control.get()
        if choice.provider != ANTHROPIC:
            return self._local
        key = self._control.key(ANTHROPIC)
        if not key:
            raise LLMError("Elegiste Claude, pero falta la clave: cargala en la pestaña Modelo.")
        model = choice.model or ANTHROPIC_MODELS[0]
        if self._cloud is None or self._cloud_for != (key, model):
            log.info("Responde Claude (%s), en la nube.", model)
            self._cloud = self._make_cloud(key, model)
            self._cloud_for = (key, model)
        return self._cloud
