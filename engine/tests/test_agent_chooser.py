import asyncio
from collections.abc import AsyncIterator, Sequence

import pytest

from kronos_engine.agent.chooser import ModelChooser
from kronos_engine.core.llm import LLMError, Message
from kronos_engine.core.tools import ToolCall, ToolSpec

OPTIONS = ["Facturas (en Documentos)", "Portfolio-master (en workspace)", "Juegos (en Escritorio)"]


class FakeProvider:
    def __init__(self, reply: str = "", error: Exception | None = None, delay: float = 0) -> None:
        self._reply = reply
        self._error = error
        self._delay = delay
        self.asked: list[Sequence[Message]] = []

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall]:
        self.asked.append(messages)
        assert tools == ()
        await asyncio.sleep(self._delay)
        if self._error:
            raise self._error
        yield self._reply


def choose(provider: FakeProvider, timeout: float = 15) -> int | None:
    return asyncio.run(ModelChooser(provider, timeout).choose("mi web personal", OPTIONS))


def test_devuelve_la_opcion_que_eligio_el_modelo() -> None:
    provider = FakeProvider("2")

    assert choose(provider) == 1
    question = provider.asked[0][-1].content
    assert "«mi web personal»" in question
    assert "2. Portfolio-master (en workspace)" in question


def test_tolera_texto_alrededor_del_numero() -> None:
    assert choose(FakeProvider("La opción 3.")) == 2


@pytest.mark.parametrize("reply", ["0", "Ninguna", "", "7"])
def test_sin_una_opcion_valida_no_elige(reply: str) -> None:
    assert choose(FakeProvider(reply)) is None


def test_si_el_modelo_falla_no_elige() -> None:
    assert choose(FakeProvider(error=LLMError("Ollama no responde"))) is None


def test_si_el_modelo_tarda_demasiado_no_elige() -> None:
    assert choose(FakeProvider("2", delay=0.5), timeout=0.05) is None


def test_sin_opciones_no_pregunta() -> None:
    provider = FakeProvider("1")

    assert asyncio.run(ModelChooser(provider).choose("algo", [])) is None
    assert provider.asked == []
