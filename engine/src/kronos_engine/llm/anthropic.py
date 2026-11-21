"""Claude, de Anthropic, en la nube: de pago y con la clave del usuario.

Lo que dice el usuario sale de la computadora. Se usa solo si el usuario lo
elige en la pestaña Modelo y carga su clave.
"""

import logging
from collections import OrderedDict
from collections.abc import AsyncIterator, Sequence
from dataclasses import dataclass, field
from typing import Any

import anthropic

from kronos_engine.core.llm import Aside, LLMError, Message
from kronos_engine.core.model_choice import ANTHROPIC_MODELS
from kronos_engine.core.tools import ToolCall, ToolSpec
from kronos_engine.llm.anthropic_web import log_web_use, web_note
from kronos_engine.llm.anthropic_wire import echoed, split_system, wire_messages, wire_tools

log = logging.getLogger(__name__)

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
# Buscar en internet y leer páginas: corren en los servidores de Anthropic. Cada
# búsqueda se cobra aparte (10 dólares cada 1000, en noviembre de 2026) y lo que
# se lee cuenta como tokens: pocas búsquedas por respuesta, y páginas recortadas.
_WEB_TOOLS = [
    {"type": "web_search_20260209", "name": "web_search", "max_uses": 3},
    {"type": "web_fetch_20260209", "name": "web_fetch", "max_uses": 2, "max_content_tokens": 8000},
]
# Haiku no tiene las versiones nuevas (que filtran los resultados): solo la búsqueda básica.
_BASIC_WEB_TOOLS = [{"type": "web_search_20250305", "name": "web_search", "max_uses": 3}]
_BASIC_WEB_MODELS = {"claude-haiku-5-5"}
# Si la búsqueda se alarga, la API corta la respuesta en pausa: cuántas veces se la sigue.
_MAX_RESUMES = 3


@dataclass
class _Reply:
    """Lo que mandó Claude en una respuesta, incluido lo de antes de cada pausa."""

    content: list[Any] = field(default_factory=list)
    stop_reason: str = ""


class AnthropicProvider:
    """Implementa `LLMProvider` con la API de Claude."""

    def __init__(self, key: str, model: str = ANTHROPIC_MODELS[0], client: Any = None) -> None:
        self._model = model
        # El cliente asíncrono del SDK; los tests pasan uno falso.
        self._client: Any = client or anthropic.AsyncAnthropic(api_key=key, timeout=_TIMEOUT)
        self._replay: OrderedDict[str, list[Any]] = OrderedDict()
        # Si Anthropic rechaza la búsqueda web (la organización puede tenerla apagada),
        # se deja de pedir mientras el motor siga abierto: Claude tiene que seguir andando.
        self._web = True

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall | Aside]:
        reply = _Reply()
        async for text in self._answer(messages, tools, reply):
            yield text
        log_web_use(reply.content)
        if reply.stop_reason == "refusal":
            raise LLMError("Claude no quiso responder a eso.")
        if note := web_note(reply.content):
            yield Aside(note)
        calls = [part for part in reply.content if part.type == "tool_use"]
        if calls and reply.stop_reason == "max_tokens":
            raise LLMError("La respuesta de Claude quedó cortada; no se hizo ninguna acción.")
        if calls:
            self._remember(calls[0].id, reply.content)
        for call in calls:
            yield ToolCall(call.name, dict(call.input), id=call.id)

    async def _answer(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec], reply: "_Reply"
    ) -> AsyncIterator[str]:
        """La respuesta entera: sigue después de cada pausa, y si Anthropic rechaza la
        búsqueda web, la pide de nuevo sin ella."""
        request = self._request(messages, tools)
        sent = request["messages"]
        resumes = 0
        while True:
            try:
                async for text in self._round(request, reply):
                    yield text
            except anthropic.BadRequestError as exc:
                if not (self._web and _asks_web(request)):
                    raise _failure(exc, self._model) from exc
                log.warning("Anthropic rechazó la búsqueda web (%s); se sigue sin ella.", exc)
                self._web = False
                # Se empieza de nuevo: lo de antes de una pausa era de otro pedido.
                reply.content.clear()
                request, resumes = self._request(messages, tools), 0
                sent = request["messages"]
                continue
            except anthropic.APIError as exc:
                raise _failure(exc, self._model) from exc
            if reply.stop_reason != "pause_turn" or resumes == _MAX_RESUMES:
                return
            resumes += 1
            # Se reenvía lo que mandó, sin otro mensaje del usuario: la API sigue sola.
            paused = {"role": "assistant", "content": [*reply.content]}
            request = {**request, "messages": [*sent, paused]}

    async def _round(self, request: dict[str, Any], reply: "_Reply") -> AsyncIterator[str]:
        """Un pedido a la API: dice el texto a medida que llega y anota cómo terminó."""
        async with self._client.beta.messages.stream(**request) as stream:
            async for event in stream:
                if event.type == "text":
                    yield event.text
            final = await stream.get_final_message()
        reply.content += echoed(final.content)
        reply.stop_reason = final.stop_reason

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
            # Solo cuando Kronos ofrece acciones: una pregunta aparte no busca en internet.
            web = _BASIC_WEB_TOOLS if self._model in _BASIC_WEB_MODELS else _WEB_TOOLS
            request["tools"] = [*wire_tools(tools), *(web if self._web else [])]
        if self._model in _WITH_FALLBACK:
            request["fallbacks"] = "default"
            request["betas"].append(_FALLBACK_BETA)
        return request

    def _remember(self, first_id: str, content: list[Any]) -> None:
        self._replay[first_id] = content
        while len(self._replay) > _REPLAY_LIMIT:
            self._replay.popitem(last=False)


def _asks_web(request: dict[str, Any]) -> bool:
    return any("type" in tool for tool in request.get("tools", []))


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
