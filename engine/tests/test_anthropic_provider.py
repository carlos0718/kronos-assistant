import asyncio
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import anthropic
import httpx2
import pytest

from kronos_engine.core.llm import LLMError, Message
from kronos_engine.core.tools import ToolCall, ToolSpec
from kronos_engine.llm.anthropic import AnthropicProvider

CLOCK = ToolSpec("current_time", "Dice la hora.")


def text(value: str) -> SimpleNamespace:
    return SimpleNamespace(type="text", text=value)


def tool_use(id_: str, name: str, arguments: dict[str, Any]) -> SimpleNamespace:
    return SimpleNamespace(type="tool_use", id=id_, name=name, input=arguments)


class FakeStream:
    def __init__(self, deltas: list[str], content: list[Any], stop_reason: str) -> None:
        self._deltas = deltas
        self._final = SimpleNamespace(content=content, stop_reason=stop_reason)

    async def __aenter__(self) -> "FakeStream":
        return self

    async def __aexit__(self, *_: object) -> None:
        return None

    async def __aiter__(self) -> AsyncIterator[Any]:
        for delta in self._deltas:
            yield SimpleNamespace(type="text", text=delta)

    async def get_final_message(self) -> Any:
        return self._final


class FakeClient:
    """Imita `client.beta.messages.stream(...)` del SDK."""

    def __init__(self, *replies: FakeStream | Exception) -> None:
        self._replies = list(replies)
        self.requests: list[dict[str, Any]] = []
        self.beta = SimpleNamespace(messages=SimpleNamespace(stream=self._stream))

    def _stream(self, **request: Any) -> FakeStream:
        self.requests.append(request)
        reply = self._replies.pop(0)
        if isinstance(reply, Exception):
            raise reply
        return reply


def answer(reply: str) -> FakeStream:
    return FakeStream([reply], [text(reply)], "end_turn")


async def collect(
    provider: AnthropicProvider, messages: list[Message], tools: Any = ()
) -> list[Any]:
    return [piece async for piece in provider.stream(messages, tools)]


def test_dice_el_texto_a_medida_que_llega() -> None:
    client = FakeClient(FakeStream(["Pa", "rís."], [text("París.")], "end_turn"))
    provider = AnthropicProvider("sk", client=client)

    pieces = asyncio.run(
        collect(provider, [Message("system", "Sos Kronos."), Message("user", "?")])
    )

    assert pieces == ["Pa", "rís."]


def test_pide_responder_rapido_y_tolerar_cambios_en_la_charla() -> None:
    client = FakeClient(answer("Hola."))

    asyncio.run(
        collect(
            AnthropicProvider("sk", client=client),
            [Message("system", "Sos Kronos."), Message("user", "Hola")],
        )
    )

    request = client.requests[0]
    assert request["model"] == "claude-opus-5-5"
    assert request["system"] == "Sos Kronos."
    assert request["messages"] == [{"role": "user", "content": "Hola"}]
    # En una conversación hablada importa contestar rápido.
    assert request["output_config"] == {"effort": "low"}
    # Si cambia el perfil a mitad de la charla, se descarta el razonamiento viejo en vez de fallar.
    assert request["thinking"]["block_binding"] == {"prefix_mismatch_behavior": "drop_block"}
    assert "thinking-binding-controls-2026-08-01" in request["betas"]
    assert request["cache_control"] == {"type": "ephemeral"}
    assert "tools" not in request


def test_si_se_niega_otro_modelo_de_claude_sigue_la_respuesta() -> None:
    client = FakeClient(answer("Hola."))

    asyncio.run(collect(AnthropicProvider("sk", client=client), [Message("user", "Hola")]))

    assert client.requests[0]["fallbacks"] == "default"
    assert "server-side-fallback-2026-07-01" in client.requests[0]["betas"]


def test_haiku_no_tiene_modelo_de_respaldo() -> None:
    client = FakeClient(answer("Hola."))

    asyncio.run(
        collect(
            AnthropicProvider("sk", "claude-haiku-5-5", client=client), [Message("user", "Hola")]
        )
    )

    assert "fallbacks" not in client.requests[0]


def test_una_accion_pedida_llega_con_su_id_y_sus_datos() -> None:
    call = tool_use("toolu_1", "open_app", {"name": "Spotify"})
    client = FakeClient(FakeStream([], [call], "tool_use"))

    pieces = asyncio.run(
        collect(AnthropicProvider("sk", client=client), [Message("user", "Spotify")], [CLOCK])
    )

    assert pieces == [ToolCall("open_app", {"name": "Spotify"}, id="toolu_1")]
    assert client.requests[0]["tools"][0]["name"] == "current_time"


def test_despues_de_la_accion_devuelve_la_respuesta_de_claude_tal_cual() -> None:
    thinking = SimpleNamespace(type="thinking", thinking="", signature="firma")
    call = tool_use("toolu_1", "current_time", {})
    client = FakeClient(FakeStream([], [thinking, call], "tool_use"), answer("Son las 15:42."))
    provider = AnthropicProvider("sk", client=client)
    turn = [Message("user", "Hora")]

    asyncio.run(collect(provider, turn, [CLOCK]))
    turn += [
        Message("assistant", "", (ToolCall("current_time", {}, id="toolu_1"),)),
        Message("tool", "15:42", tool_name="current_time", tool_call_id="toolu_1"),
    ]
    asyncio.run(collect(provider, turn, [CLOCK]))

    assert client.requests[1]["messages"][1] == {"role": "assistant", "content": [thinking, call]}


def test_una_pregunta_aparte_no_borra_lo_que_hay_que_devolver() -> None:
    # Al abrir una carpeta, Kronos le pregunta a Claude cuál es, en medio del turno.
    call = tool_use("toolu_1", "current_time", {})
    client = FakeClient(FakeStream([], [call], "tool_use"), answer("3"), answer("Listo."))
    provider = AnthropicProvider("sk", client=client)
    turn = [Message("user", "Abrí mi portafolio")]

    asyncio.run(collect(provider, turn, [CLOCK]))
    asyncio.run(collect(provider, [Message("user", "¿Qué número es?")]))
    turn += [
        Message("assistant", "", (ToolCall("current_time", {}, id="toolu_1"),)),
        Message("tool", "Se abrió.", tool_name="current_time", tool_call_id="toolu_1"),
    ]
    asyncio.run(collect(provider, turn, [CLOCK]))

    assert client.requests[2]["messages"][1]["content"] == [call]


def test_si_claude_se_niega_lo_dice() -> None:
    client = FakeClient(FakeStream([], [], "refusal"))

    with pytest.raises(LLMError, match="no quiso"):
        asyncio.run(collect(AnthropicProvider("sk", client=client), [Message("user", "?")]))


def test_una_accion_cortada_por_el_limite_no_se_ejecuta() -> None:
    client = FakeClient(FakeStream([], [tool_use("toolu_1", "open_app", {})], "max_tokens"))

    with pytest.raises(LLMError, match="cortada"):
        asyncio.run(
            collect(AnthropicProvider("sk", client=client), [Message("user", "?")], [CLOCK])
        )


def _response(status: int) -> httpx2.Response:
    return httpx2.Response(status, request=httpx2.Request("POST", "https://api.anthropic.com"))


@pytest.mark.parametrize(
    ("error", "said"),
    [
        (anthropic.AuthenticationError("no", response=_response(401), body=None), "clave"),
        (anthropic.RateLimitError("no", response=_response(429), body=None), "en un rato"),
        (anthropic.APIConnectionError(request=httpx2.Request("POST", "https://x")), "internet"),
    ],
)
def test_los_errores_de_anthropic_se_explican(error: Exception, said: str) -> None:
    client = FakeClient(error)

    with pytest.raises(LLMError, match=said):
        asyncio.run(collect(AnthropicProvider("sk", client=client), [Message("user", "?")]))


def _server_tools(request: dict[str, Any]) -> dict[str, dict[str, Any]]:
    return {tool["name"]: tool for tool in request.get("tools", []) if "type" in tool}


def test_con_acciones_puede_buscar_en_internet_y_leer_paginas_con_un_tope() -> None:
    client = FakeClient(answer("Hola."))

    asyncio.run(collect(AnthropicProvider("sk", client=client), [Message("user", "?")], [CLOCK]))

    web = _server_tools(client.requests[0])
    assert web["web_search"]["type"] == "web_search_20260209"
    assert web["web_fetch"]["type"] == "web_fetch_20260209"
    # Cada búsqueda se cobra: pocas por respuesta, y páginas recortadas.
    assert web["web_search"]["max_uses"] <= 3
    assert web["web_fetch"]["max_content_tokens"] <= 10000


def test_haiku_busca_con_la_version_basica_y_no_lee_paginas() -> None:
    client = FakeClient(answer("Hola."))
    provider = AnthropicProvider("sk", "claude-haiku-5-5", client=client)

    asyncio.run(collect(provider, [Message("user", "?")], [CLOCK]))

    web = _server_tools(client.requests[0])
    assert web["web_search"]["type"] == "web_search_20250305"
    assert "web_fetch" not in web


def test_una_pregunta_aparte_sin_acciones_no_busca_en_internet() -> None:
    client = FakeClient(answer("3"))

    asyncio.run(collect(AnthropicProvider("sk", client=client), [Message("user", "¿Cuál?")]))

    assert "tools" not in client.requests[0]


def test_si_la_busqueda_queda_en_pausa_la_sigue() -> None:
    searching = SimpleNamespace(type="server_tool_use", id="srvtoolu_1", name="web_search")
    paused = FakeStream(["Busco. "], [text("Busco. "), searching], "pause_turn")
    client = FakeClient(paused, answer("Hace veinte grados."))

    pieces = asyncio.run(
        collect(AnthropicProvider("sk", client=client), [Message("user", "¿Clima?")], [CLOCK])
    )

    assert pieces == ["Busco. ", "Hace veinte grados."]
    # Se reenvía lo que mandó Claude, sin un mensaje del usuario de por medio.
    assert client.requests[1]["messages"][-1] == {
        "role": "assistant",
        "content": [text("Busco. "), searching],
    }


def test_si_despues_de_la_pausa_pide_una_accion_se_devuelve_todo_junto() -> None:
    before = text("Busco. ")
    call = tool_use("toolu_1", "current_time", {})
    client = FakeClient(
        FakeStream([], [before], "pause_turn"),
        FakeStream([], [call], "tool_use"),
        answer("Listo."),
    )
    provider = AnthropicProvider("sk", client=client)
    turn = [Message("user", "Hora")]

    asyncio.run(collect(provider, turn, [CLOCK]))
    turn += [
        Message("assistant", "", (ToolCall("current_time", {}, id="toolu_1"),)),
        Message("tool", "15:42", tool_name="current_time", tool_call_id="toolu_1"),
    ]
    asyncio.run(collect(provider, turn, [CLOCK]))

    assert client.requests[2]["messages"][1]["content"] == [before, call]


def test_si_anthropic_rechaza_la_busqueda_responde_sin_ella_y_no_la_vuelve_a_pedir() -> None:
    # Por ejemplo, si la organización la tiene apagada: Claude tiene que seguir andando.
    rejected = anthropic.BadRequestError(
        "web_search is not enabled for this organization", response=_response(400), body=None
    )
    client = FakeClient(rejected, answer("Son las tres."), answer("Hola."))
    provider = AnthropicProvider("sk", client=client)

    pieces = asyncio.run(collect(provider, [Message("user", "Hora")], [CLOCK]))
    asyncio.run(collect(provider, [Message("user", "Hola")], [CLOCK]))

    assert pieces == ["Son las tres."]
    assert _server_tools(client.requests[1]) == {}
    assert _server_tools(client.requests[2]) == {}


def test_un_rechazo_sin_herramientas_web_no_se_repite() -> None:
    rejected = anthropic.BadRequestError("mal", response=_response(400), body=None)
    client = FakeClient(rejected)

    with pytest.raises(LLMError, match="rechazó"):
        asyncio.run(collect(AnthropicProvider("sk", client=client), [Message("user", "?")]))

    assert len(client.requests) == 1
