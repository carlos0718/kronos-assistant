import asyncio
import logging
from typing import Any

import pytest

from kronos_engine.core.approval import ApprovalRequest
from kronos_engine.core.protocol import AssistantState, ServerMessage
from kronos_engine.core.secret_prompt import SecretPrompts

REQUEST = ApprovalRequest("edit_registry", "modificar el registro")


class Harness:
    def __init__(self, wait_seconds: float = 5.0) -> None:
        self.sent: list[tuple[ServerMessage, dict[str, Any]]] = []
        self.said: list[str] = []
        self.states: list[AssistantState] = []
        self.requested = asyncio.Event()
        self.prompts = SecretPrompts(self._say, self._state, self._emit, wait_seconds)

    async def _say(self, text: str) -> None:
        self.said.append(text)

    async def _state(self, state: AssistantState) -> None:
        self.states.append(state)

    async def _emit(self, type_: ServerMessage, payload: dict[str, Any]) -> None:
        self.sent.append((type_, payload))
        self.requested.set()

    async def ask(self) -> asyncio.Task[str | None]:
        """Empieza el pedido y espera a que la interfaz lo reciba."""
        task = asyncio.ensure_future(self.prompts.ask_secret(REQUEST))
        await self.requested.wait()
        return task

    @property
    def request_id(self) -> str:
        return str(self.sent[0][1]["id"])


def test_el_usuario_escribe_la_clave_y_llega_a_quien_pregunto() -> None:
    async def scenario() -> str | None:
        harness = Harness()
        task = await harness.ask()
        harness.prompts.answer(harness.request_id, "mi-clave")
        return await task

    assert asyncio.run(scenario()) == "mi-clave"


def test_la_interfaz_recibe_que_se_pide_y_despues_que_se_cerro() -> None:
    async def scenario() -> Harness:
        harness = Harness()
        task = await harness.ask()
        harness.prompts.answer(harness.request_id, "mi-clave")
        await task
        return harness

    harness = asyncio.run(scenario())

    assert [type_ for type_, _ in harness.sent] == [
        ServerMessage.SECRET_REQUEST,
        ServerMessage.SECRET_RESOLVED,
    ]
    assert harness.sent[0][1]["summary"] == "modificar el registro"
    assert harness.sent[0][1]["id"] == harness.sent[1][1]["id"]
    assert harness.states[-1] is AssistantState.THINKING


def test_kronos_avisa_en_voz_alta_que_la_clave_se_escribe() -> None:
    async def scenario() -> Harness:
        harness = Harness()
        task = await harness.ask()
        harness.prompts.answer(harness.request_id, "x")
        await task
        return harness

    said = asyncio.run(scenario()).said

    assert len(said) == 1
    assert "escrib" in said[0].lower()


def test_cancelar_devuelve_none() -> None:
    async def scenario() -> str | None:
        harness = Harness()
        task = await harness.ask()
        harness.prompts.answer(harness.request_id, None)
        return await task

    assert asyncio.run(scenario()) is None


def test_si_nadie_escribe_es_un_no() -> None:
    async def scenario() -> str | None:
        return await Harness(wait_seconds=0.01).prompts.ask_secret(REQUEST)

    assert asyncio.run(scenario()) is None


def test_la_respuesta_a_otro_pedido_se_ignora() -> None:
    async def scenario() -> str | None:
        harness = Harness(wait_seconds=0.05)
        task = await harness.ask()
        harness.prompts.answer("otro", "mi-clave")
        return await task

    assert asyncio.run(scenario()) is None


def test_si_se_corta_la_conversacion_la_interfaz_saca_el_pedido() -> None:
    async def scenario() -> Harness:
        harness = Harness()
        task = await harness.ask()
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task
        return harness

    assert asyncio.run(scenario()).sent[-1][0] is ServerMessage.SECRET_RESOLVED


def test_la_clave_no_se_registra_ni_se_reenvia(caplog: pytest.LogCaptureFixture) -> None:
    async def scenario() -> Harness:
        harness = Harness()
        task = await harness.ask()
        harness.prompts.answer(harness.request_id, "clave-privada")
        await task
        return harness

    with caplog.at_level(logging.DEBUG):
        harness = asyncio.run(scenario())

    assert "clave-privada" not in caplog.text
    assert "clave-privada" not in str(harness.sent)
