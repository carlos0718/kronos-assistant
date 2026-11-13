import asyncio
import json
from collections.abc import Callable
from typing import Any

import httpx
import pytest

from kronos_engine.core.llm import LLMError, Message
from kronos_engine.llm.ollama import OllamaProvider

MESSAGES = [Message("system", "Sos Kronos."), Message("user", "Hola")]


def ndjson(*events: dict[str, Any]) -> bytes:
    return "".join(json.dumps(event) + "\n" for event in events).encode()


def chunk(content: str, done: bool = False) -> dict[str, Any]:
    return {"message": {"role": "assistant", "content": content}, "done": done}


def provider(handler: Callable[[httpx.Request], httpx.Response]) -> OllamaProvider:
    return OllamaProvider("qwen3:8b", transport=httpx.MockTransport(handler))


def collect(ollama: OllamaProvider) -> list[str]:
    async def scenario() -> list[str]:
        return [delta async for delta in ollama.stream(MESSAGES)]

    return asyncio.run(scenario())


def test_entrega_la_respuesta_de_a_pedazos() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, content=ndjson(chunk("Hola, "), chunk("¿qué tal?"), chunk("", True))
        )

    assert collect(provider(handler)) == ["Hola, ", "¿qué tal?"]


def test_pide_el_modelo_elegido_en_streaming_y_sin_razonamiento() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, content=ndjson(chunk("", True)))

    collect(provider(handler))

    assert sent[0].url == "http://127.0.0.1:11434/api/chat"
    assert json.loads(sent[0].content) == {
        "model": "qwen3:8b",
        "messages": [
            {"role": "system", "content": "Sos Kronos."},
            {"role": "user", "content": "Hola"},
        ],
        "stream": True,
        "think": False,
        "keep_alive": "30m",
    }


def test_ignora_el_razonamiento_del_modelo() -> None:
    thinking = {
        "message": {"role": "assistant", "content": "", "thinking": "Veamos…"},
        "done": False,
    }

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ndjson(thinking, chunk("Hola."), chunk("", True)))

    assert collect(provider(handler)) == ["Hola."]


def test_avisa_si_ollama_no_esta_abierto() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada", request=request)

    with pytest.raises(LLMError, match="No se pudo conectar con Ollama"):
        collect(provider(handler))


def test_avisa_si_el_modelo_no_esta_descargado() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(404, json={"error": "model 'qwen3:8b' not found"})

    with pytest.raises(LLMError, match="ollama pull qwen3:8b"):
        collect(provider(handler))


def test_informa_otros_errores_de_ollama() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "out of memory"})

    with pytest.raises(LLMError, match="out of memory"):
        collect(provider(handler))


def test_informa_un_error_que_llega_a_mitad_de_la_respuesta() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=ndjson(chunk("Hola"), {"error": "se cortó"}))

    with pytest.raises(LLMError, match="se cortó"):
        collect(provider(handler))


def test_avisa_si_ollama_tarda_demasiado() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("sin respuesta", request=request)

    with pytest.raises(LLMError, match="tardó demasiado"):
        collect(provider(handler))


def test_load_le_pide_a_ollama_que_cargue_el_modelo_sin_preguntarle_nada() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"done": True})

    asyncio.run(provider(handler).load())

    assert sent[0].url == "http://127.0.0.1:11434/api/chat"
    assert json.loads(sent[0].content) == {
        "model": "qwen3:8b",
        "messages": [],
        "keep_alive": "30m",
    }


def test_load_no_falla_si_ollama_no_esta_abierto() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("conexión rechazada", request=request)

    asyncio.run(provider(handler).load())  # El aviso llega cuando el usuario habla.
