"""Claude, de Anthropic, en la nube: de pago y con la clave del usuario.

Lo que dice el usuario sale de la computadora. Se usa solo si el usuario lo
elige en la pestaña Modelo y carga su clave.
"""

from collections import OrderedDict
from collections.abc import AsyncIterator, Sequence
from typing import Any

import anthropic

from kronos_engine.core.llm import LLMError, Message
from kronos_engine.core.model_choice import ANTHROPIC_MODELS
from kronos_engine.core.tools import ToolCall, ToolSpec
from kronos_engine.llm.anthropic_wire import echoed, split_system, wire_messages, wire_tools

# Permite pedir `drop_block`: si la charla cambió (otro perfil, otras carpetas
# permitidas), la API descarta el razonamiento viejo en lugar de rechazar el pedido.
_BINDING_BETA = "thinking-binding-controls-2026-08-01"
# Si Claude se niega por una de sus reglas de seguridad, otro modelo de Claude sigue la respuesta.
_FALLBACK_BETA = "server-side-fallback-2026-07-01"
# Haiku no tiene modelo de respaldo.
_WITH_FALLBACK = {"claude-opus-5-5", "claude-sonnet-5-5"}
# Cuenta lo que razona y lo que dice: un tope bajo cortaría la respuesta.
_MAX_TOKENS = 16000
_TIMEOUT = anthropic.Timeout(60, connect=5)
# Cuántos pedidos de acciones se recuerdan para devolverlos tal cual. Solo se
# usan los del turno en curso; el tope es para que no crezca sin fin.
_REPLAY_LIMIT = 32


class AnthropicProvider:
    """Implementa `LLMProvider` con la API de Claude."""

    def __init__(self, key: str, model: str = ANTHROPIC_MODELS[0], client: Any = None) -> None:
        self._model = model
        # El cliente asíncrono del SDK; los tests pasan uno falso.
        self._client: Any = client or anthropic.AsyncAnthropic(api_key=key, timeout=_TIMEOUT)
        self._replay: OrderedDict[str, list[Any]] = OrderedDict()

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall]:
        try:
            async with self._client.beta.messages.stream(
                **self._request(messages, tools)
            ) as stream:
                async for event in stream:
                    if event.type == "text":
                        yield event.text
                final = await stream.get_final_message()
        except anthropic.APIError as exc:
            raise _failure(exc, self._model) from exc
        if final.stop_reason == "refusal":
            raise LLMError("Claude no quiso responder a eso.")
        content = echoed(final.content)
        calls = [part for part in content if part.type == "tool_use"]
        if calls and final.stop_reason == "max_tokens":
            raise LLMError("La respuesta de Claude quedó cortada; no se hizo ninguna acción.")
        if calls:
            self._remember(calls[0].id, content)
        for call in calls:
            yield ToolCall(call.name, dict(call.input), id=call.id)

    def _request(self, messages: Sequence[Message], tools: Sequence[ToolSpec]) -> dict[str, Any]:
        system, rest = split_system(messages)
        request: dict[str, Any] = {
            "model": self._model,
            "max_tokens": _MAX_TOKENS,
            "system": system,
            "messages": wire_messages(rest, self._replay),
            "thinking": {
                "type": "adaptive",
                "block_binding": {"prefix_mismatch_behavior": "drop_block"},
            },
            # En una conversación hablada importa contestar rápido: razona poco.
            "output_config": {"effort": "low"},
            # Las instrucciones y las acciones son las mismas en cada pedido: se cobran menos.
            "cache_control": {"type": "ephemeral"},
            "betas": [_BINDING_BETA],
        }
        if tools:
            request["tools"] = wire_tools(tools)
        if self._model in _WITH_FALLBACK:
            request["fallbacks"] = "default"
            request["betas"].append(_FALLBACK_BETA)
        return request

    def _remember(self, first_id: str, content: list[Any]) -> None:
        self._replay[first_id] = content
        while len(self._replay) > _REPLAY_LIMIT:
            self._replay.popitem(last=False)


def _failure(exc: anthropic.APIError, model: str) -> LLMError:
    """El error, explicado para el usuario. De lo más específico a lo más general."""
    if isinstance(exc, anthropic.AuthenticationError):
        return LLMError("Anthropic no aceptó la clave. Revisala en la pestaña Modelo.")
    if isinstance(exc, anthropic.PermissionDeniedError):
        return LLMError(f"La clave de Anthropic no tiene permiso para usar {model}.")
    if isinstance(exc, anthropic.RateLimitError):
        return LLMError("Anthropic está limitando los pedidos. Probá de nuevo en un rato.")
    if isinstance(exc, anthropic.OverloadedError):
        return LLMError("Claude está saturado. Probá de nuevo en un rato.")
    if isinstance(exc, anthropic.BadRequestError):
        return LLMError(f"Anthropic rechazó el pedido: {exc.message}")
    if isinstance(exc, anthropic.APIStatusError):
        return LLMError(f"Anthropic informó un error (código {exc.status_code}).")
    if isinstance(exc, anthropic.APITimeoutError):
        return LLMError("Anthropic tardó demasiado en responder.")
    if isinstance(exc, anthropic.APIConnectionError):
        return LLMError("No se pudo conectar con Anthropic. ¿Hay internet?")
    return LLMError(f"Anthropic informó un error: {exc}")
