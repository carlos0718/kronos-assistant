import asyncio
from collections.abc import AsyncIterator, Sequence

import pytest

from kronos_engine.agent.responder import AgentResponder
from kronos_engine.core.llm import LLMError, Message

INSTRUCTIONS = "Sos Kronos."


class FakeProvider:
    def __init__(self, replies: list[list[str]], fail_with: Exception | None = None) -> None:
        self._replies = replies
        self._fail_with = fail_with
        self.received: list[list[Message]] = []

    async def stream(self, messages: Sequence[Message]) -> AsyncIterator[str]:
        self.received.append(list(messages))
        for delta in self._replies[len(self.received) - 1]:
            yield delta
        if self._fail_with:
            raise self._fail_with


async def ask(responder: AgentResponder, text: str) -> str:
    return "".join([delta async for delta in responder.respond(text)])


def test_le_pasa_al_modelo_las_instrucciones_y_lo_que_dijo_el_usuario() -> None:
    provider = FakeProvider([["Son las ", "tres."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS)

    assert asyncio.run(ask(responder, "¿Qué hora es?")) == "Son las tres."
    assert provider.received == [
        [Message("system", INSTRUCTIONS), Message("user", "¿Qué hora es?")],
    ]


def test_recuerda_los_turnos_anteriores_de_la_conversacion() -> None:
    provider = FakeProvider([["Son las tres."], ["De la tarde."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS)

    async def scenario() -> None:
        await ask(responder, "¿Qué hora es?")
        await ask(responder, "¿De la tarde?")

    asyncio.run(scenario())
    assert provider.received[1] == [
        Message("system", INSTRUCTIONS),
        Message("user", "¿Qué hora es?"),
        Message("assistant", "Son las tres."),
        Message("user", "¿De la tarde?"),
    ]


def test_un_turno_que_falla_no_queda_en_la_memoria() -> None:
    provider = FakeProvider([["Son las"], ["Hola."]], fail_with=LLMError("sin conexión"))
    responder = AgentResponder(provider, lambda: INSTRUCTIONS)

    async def scenario() -> None:
        with pytest.raises(LLMError):
            await ask(responder, "¿Qué hora es?")
        provider._fail_with = None
        await ask(responder, "Hola")

    asyncio.run(scenario())
    assert provider.received[1] == [Message("system", INSTRUCTIONS), Message("user", "Hola")]


def test_un_turno_cortado_por_el_usuario_no_queda_en_la_memoria() -> None:
    provider = FakeProvider([["Son las ", "tres."], ["Hola."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS)

    async def scenario() -> None:
        stream = responder.respond("¿Qué hora es?")
        await anext(stream)
        await stream.aclose()  # El usuario cortó a Kronos a mitad de la respuesta.
        await ask(responder, "Hola")

    asyncio.run(scenario())
    assert provider.received[1] == [Message("system", INSTRUCTIONS), Message("user", "Hola")]


def test_olvida_los_turnos_mas_viejos_al_pasar_el_limite() -> None:
    provider = FakeProvider([["uno"], ["dos"], ["tres"]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS, max_turns=1)

    async def scenario() -> None:
        await ask(responder, "a")
        await ask(responder, "b")
        await ask(responder, "c")

    asyncio.run(scenario())
    assert provider.received[2] == [
        Message("system", INSTRUCTIONS),
        Message("user", "b"),
        Message("assistant", "dos"),
        Message("user", "c"),
    ]


def test_lee_las_instrucciones_en_cada_turno() -> None:
    # El usuario puede cambiar su perfil con la conversación en marcha.
    provider = FakeProvider([["uno"], ["dos"]])
    current = ["Sos Kronos."]
    responder = AgentResponder(provider, lambda: current[0])

    async def scenario() -> None:
        await ask(responder, "a")
        current[0] = "Sos Kronos. El usuario se llama Carlos."
        await ask(responder, "b")

    asyncio.run(scenario())
    assert provider.received[0][0] == Message("system", "Sos Kronos.")
    assert provider.received[1][0] == Message("system", "Sos Kronos. El usuario se llama Carlos.")
