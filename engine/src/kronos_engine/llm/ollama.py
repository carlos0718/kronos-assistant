"""Modelos locales a través de Ollama (https://ollama.com)."""

import asyncio
import contextlib
import json
import threading
from collections.abc import AsyncIterator, Sequence
from dataclasses import asdict

import httpx

from kronos_engine.core.llm import LLMError, Message

DEFAULT_URL = "http://127.0.0.1:11434"

# La primera respuesta puede tardar: Ollama carga el modelo en memoria.
_TIMEOUT = httpx.Timeout(120, connect=5)
# Cuánto queda el modelo en memoria sin uso. Ollama lo descarga a los 5 minutos
# y volver a cargarlo tarda varios segundos: demasiado para una conversación.
_KEEP_ALIVE = "30m"


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

    async def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        request = {
            "model": self._model,
            "messages": [asdict(message) for message in messages],
            "stream": True,
            # Sin razonamiento previo: en una conversación hablada importa responder rápido.
            "think": False,
            "keep_alive": _KEEP_ALIVE,
        }
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
                    if content := event.get("message", {}).get("content"):
                        yield content
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
