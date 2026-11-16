"""Modelos locales a través de Ollama (https://ollama.com)."""

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator, Sequence
from typing import Any

import httpx

from kronos_engine.core.llm import LLMError, Message
from kronos_engine.core.tools import ToolCall, ToolSpec

DEFAULT_URL = "http://127.0.0.1:11434"

# La primera respuesta puede tardar: Ollama carga el modelo en memoria.
_TIMEOUT = httpx.Timeout(120, connect=5)
# Cuánto queda el modelo en memoria sin uso. Ollama lo descarga a los 5 minutos
# y volver a cargarlo tarda varios segundos: demasiado para una conversación.
_KEEP_ALIVE = "30m"


def _wire_message(message: Message) -> dict[str, Any]:
    """Un mensaje, en el formato de Ollama."""
    wire: dict[str, Any] = {"role": message.role, "content": message.content}
    if message.tool_calls:
        wire["tool_calls"] = [
            {
                "type": "function",
                "function": {"index": index, "name": call.name, "arguments": dict(call.arguments)},
            }
            for index, call in enumerate(message.tool_calls)
        ]
    if message.tool_name:
        wire["tool_name"] = message.tool_name
    return wire


def _wire_tool(tool: ToolSpec) -> dict[str, Any]:
    """Una acción que se le ofrece al modelo, en el formato de Ollama."""
    return {
        "type": "function",
        "function": {
            "name": tool.name,
            "description": tool.description,
            "parameters": dict(tool.parameters),
        },
    }


class OllamaProvider:
    def __init__(
        self,
        model: str,
        base_url: str = DEFAULT_URL,
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        self._model = model
        self._base_url = base_url
        self._transport = transport

    def _client(self) -> httpx.AsyncClient:
        return httpx.AsyncClient(
            base_url=self._base_url, timeout=_TIMEOUT, transport=self._transport
        )

    def preload(self) -> None:
        """Carga el modelo en segundo plano, mientras el usuario todavía no habló."""
        threading.Thread(target=lambda: asyncio.run(self.load()), daemon=True).start()

    async def load(self) -> None:
        """Le pide a Ollama que cargue el modelo en memoria."""
        request = {"model": self._model, "messages": [], "keep_alive": _KEEP_ALIVE}
        # Si Ollama no responde, se avisa cuando el usuario habla, no al arrancar.
        with contextlib.suppress(httpx.HTTPError):
            async with self._client() as client:
                await client.post("/api/chat", json=request)

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall]:
        request: dict[str, Any] = {
            "model": self._model,
            "messages": [_wire_message(message) for message in messages],
            "stream": True,
            # Sin razonamiento previo: en una conversación hablada importa responder rápido.
            "think": False,
            "keep_alive": _KEEP_ALIVE,
        }
        if tools:
            request["tools"] = [_wire_tool(tool) for tool in tools]
        try:
            async with (
                self._client() as client,
                client.stream("POST", "/api/chat", json=request) as response,
            ):
                if response.is_error:
                    raise self._failure(response.status_code, await response.aread())
                async for line in response.aiter_lines():
                    if not line:
                        continue
                    event = json.loads(line)
                    if error := event.get("error"):
                        raise LLMError(f"Ollama informó un error: {error}")
                    message = event.get("message") or {}
                    if content := message.get("content"):
                        yield content
                    # Ollama manda cada acción entera, no de a pedazos.
                    for call in message.get("tool_calls") or []:
                        function = call.get("function") or {}
                        yield ToolCall(function.get("name", ""), function.get("arguments") or {})
        except httpx.ConnectError as exc:
            raise LLMError("No se pudo conectar con Ollama. ¿Está abierto?") from exc
        except httpx.TimeoutException as exc:
            raise LLMError("Ollama tardó demasiado en responder.") from exc

    def _failure(self, status: int, body: bytes) -> LLMError:
        if status == httpx.codes.NOT_FOUND:
            return LLMError(
                f"Ollama no tiene el modelo {self._model}. "
                f"Descargalo con: ollama pull {self._model}"
            )
        try:
            detail = json.loads(body).get("error")
        except (ValueError, AttributeError):
            detail = None
        return LLMError(f"Ollama informó un error: {detail or f'código {status}'}")
