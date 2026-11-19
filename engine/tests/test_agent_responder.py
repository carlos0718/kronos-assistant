import asyncio
from collections.abc import AsyncIterator, Sequence

import pytest

from kronos_engine.agent.responder import MAX_TOOL_ROUNDS, AgentResponder
from kronos_engine.core.llm import Aside, LLMError, Message
from kronos_engine.core.tools import ToolCall, ToolSpec

INSTRUCTIONS = "Sos Kronos."
CLOCK = ToolSpec("current_time", "Dice la hora.")
ASK_TIME = ToolCall("current_time")


class FakeProvider:
    def __init__(
        self,
        replies: Sequence[Sequence[str | ToolCall | Aside]],
        fail_with: Exception | None = None,
    ) -> None:
        self._replies = replies
        self._fail_with = fail_with
        self.received: list[list[Message]] = []
        self.offered: list[list[ToolSpec]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall | Aside]:
        self.received.append(list(messages))
        self.offered.append(list(tools))
        for piece in self._replies[len(self.received) - 1]:
            yield piece
        if self._fail_with:
            raise self._fail_with


class FakeToolbox:
    def __init__(self, result: str = "lunes 16 de noviembre de 2026, 15:00") -> None:
        self._result = result
        self.ran: list[ToolCall] = []

    def specs(self) -> Sequence[ToolSpec]:
        return [CLOCK]

    async def run(self, call: ToolCall) -> str:
        self.ran.append(call)
        return self._result


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


def test_le_ofrece_al_modelo_las_acciones_disponibles() -> None:
    provider = FakeProvider([["Hola."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS, tools=FakeToolbox())

    asyncio.run(ask(responder, "Hola"))

    assert provider.offered == [[CLOCK]]


def test_ejecuta_la_accion_que_pide_el_modelo_y_le_pasa_el_resultado() -> None:
    provider = FakeProvider([[ASK_TIME], ["Son las tres."]])
    tools = FakeToolbox("lunes 16 de noviembre de 2026, 15:00")
    responder = AgentResponder(provider, lambda: INSTRUCTIONS, tools=tools)

    assert asyncio.run(ask(responder, "¿Qué hora es?")) == "Son las tres."
    assert tools.ran == [ASK_TIME]
    assert provider.received[1] == [
        Message("system", INSTRUCTIONS),
        Message("user", "¿Qué hora es?"),
        Message("assistant", "", tool_calls=(ASK_TIME,)),
        Message("tool", "lunes 16 de noviembre de 2026, 15:00", tool_name="current_time"),
    ]


def test_lo_que_dice_antes_de_la_accion_queda_como_una_frase_aparte() -> None:
    # Sin el corte, la voz diría «Ya me fijoSon las tres» de corrido.
    provider = FakeProvider([["Ya me fijo", ASK_TIME], ["Son las tres."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS, tools=FakeToolbox())

    assert asyncio.run(ask(responder, "¿Qué hora es?")) == "Ya me fijo\nSon las tres."


def test_recuerda_las_acciones_de_los_turnos_anteriores() -> None:
    provider = FakeProvider([[ASK_TIME], ["Son las tres."], ["De nada."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS, tools=FakeToolbox("15:00"))

    async def scenario() -> None:
        await ask(responder, "¿Qué hora es?")
        await ask(responder, "Gracias")

    asyncio.run(scenario())
    assert provider.received[2] == [
        Message("system", INSTRUCTIONS),
        Message("user", "¿Qué hora es?"),
        Message("assistant", "", tool_calls=(ASK_TIME,)),
        Message("tool", "15:00", tool_name="current_time"),
        Message("assistant", "Son las tres."),
        Message("user", "Gracias"),
    ]


def test_un_turno_con_acciones_se_olvida_entero_al_pasar_el_limite() -> None:
    # Si quedara la mitad, el modelo vería un resultado sin la pregunta que lo pidió.
    provider = FakeProvider([[ASK_TIME], ["Son las tres."], ["De nada."], ["Chau."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS, max_turns=1, tools=FakeToolbox())

    async def scenario() -> None:
        await ask(responder, "¿Qué hora es?")
        await ask(responder, "Gracias")
        await ask(responder, "Chau")

    asyncio.run(scenario())
    assert provider.received[3] == [
        Message("system", INSTRUCTIONS),
        Message("user", "Gracias"),
        Message("assistant", "De nada."),
        Message("user", "Chau"),
    ]


def test_si_el_modelo_no_para_de_pedir_acciones_se_le_dejan_de_ofrecer() -> None:
    provider = FakeProvider([*([[ASK_TIME]] * MAX_TOOL_ROUNDS), ["No pude terminar."]])
    tools = FakeToolbox()
    responder = AgentResponder(provider, lambda: INSTRUCTIONS, tools=tools)

    assert asyncio.run(ask(responder, "¿Qué hora es?")) == "No pude terminar."
    assert len(tools.ran) == MAX_TOOL_ROUNDS
    assert provider.offered[-1] == []


def test_sin_acciones_disponibles_ignora_las_que_pida_el_modelo() -> None:
    provider = FakeProvider([["Hola.", ASK_TIME]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS)

    assert asyncio.run(ask(responder, "Hola")) == "Hola."
    assert len(provider.received) == 1


def test_el_resultado_lleva_el_id_con_que_el_modelo_pidio_la_accion() -> None:
    # Claude empareja cada acción con su resultado por el id.
    call = ToolCall("current_time", id="toolu_1")
    provider = FakeProvider([[call], ["Son las tres."]])

    asyncio.run(ask(AgentResponder(provider, lambda: INSTRUCTIONS, tools=FakeToolbox()), "Hora"))

    result = provider.received[1][-1]
    assert (result.role, result.tool_name, result.tool_call_id) == (
        "tool",
        "current_time",
        "toolu_1",
    )


def test_la_nota_del_modelo_no_se_dice_pero_queda_en_la_memoria() -> None:
    note = Aside("[Buscaste «Boca».]")
    provider = FakeProvider([["Ganó ", note, "Boca."], ["El domingo."]])
    responder = AgentResponder(provider, lambda: INSTRUCTIONS)

    async def scenario() -> str:
        said = await ask(responder, "¿Boca?")
        await ask(responder, "¿Cuándo?")
        return said

    assert asyncio.run(scenario()) == "Ganó Boca."
    assert provider.received[1][2] == Message("assistant", "Ganó Boca.", aside=note.text)


def test_la_nota_de_una_vuelta_con_acciones_queda_con_esa_vuelta() -> None:
    note = Aside("[Buscaste «clima».]")
    provider = FakeProvider([[note, ASK_TIME], ["Son las tres."]])

    asyncio.run(ask(AgentResponder(provider, lambda: INSTRUCTIONS, tools=FakeToolbox()), "Hora"))

    assert provider.received[1][2] == Message("assistant", "", (ASK_TIME,), aside=note.text)
