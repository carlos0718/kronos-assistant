import asyncio
from collections.abc import AsyncIterator, Callable, Sequence

import pytest

from kronos_engine.core.llm import LLMError, Message
from kronos_engine.core.model_choice import ANTHROPIC, ModelChoice
from kronos_engine.core.tools import ToolCall, ToolSpec
from kronos_engine.llm.switching import SwitchingProvider


class FakeControl:
    def __init__(self, choice: ModelChoice | None = None, key: str | None = None) -> None:
        self.choice = choice or ModelChoice()
        self.saved_key = key

    def get(self) -> ModelChoice:
        return self.choice

    def set(self, choice: ModelChoice) -> None:
        self.choice = choice or ModelChoice()

    def key(self, provider: str) -> str | None:
        return self.saved_key

    def set_key(self, provider: str, key: str) -> None:
        self.saved_key = key or None


class Named:
    def __init__(self, name: str) -> None:
        self.name = name
        self.preloaded = False

    def preload(self) -> None:
        self.preloaded = True

    async def stream(
        self, messages: Sequence[Message], tools: Sequence[ToolSpec] = ()
    ) -> AsyncIterator[str | ToolCall]:
        yield self.name


def make_cloud(made: list[tuple[str, str]]) -> Callable[[str, str], Named]:
    def make(key: str, model: str) -> Named:
        made.append((key, model))
        return Named(f"claude {model}")

    return make


async def reply(provider: SwitchingProvider) -> str:
    return "".join([str(piece) async for piece in provider.stream([Message("user", "Hola")])])


def test_de_fabrica_responde_el_modelo_local() -> None:
    provider = SwitchingProvider(FakeControl(), Named("ollama"), make_cloud([]))

    assert asyncio.run(reply(provider)) == "ollama"


def test_con_claude_elegido_y_la_clave_responde_claude() -> None:
    made: list[tuple[str, str]] = []
    control = FakeControl(ModelChoice(ANTHROPIC, "claude-sonnet-5-5"), key="sk-ant")
    provider = SwitchingProvider(control, Named("ollama"), make_cloud(made))

    assert asyncio.run(reply(provider)) == "claude claude-sonnet-5-5"
    assert made == [("sk-ant", "claude-sonnet-5-5")]


def test_sin_modelo_elegido_usa_el_claude_de_fabrica() -> None:
    made: list[tuple[str, str]] = []
    provider = SwitchingProvider(
        FakeControl(ModelChoice(ANTHROPIC), key="sk-ant"), Named("ollama"), make_cloud(made)
    )

    asyncio.run(reply(provider))

    assert made == [("sk-ant", "claude-opus-5-5")]


def test_cambia_de_modelo_sin_reiniciar() -> None:
    control = FakeControl(key="sk-ant")
    provider = SwitchingProvider(control, Named("ollama"), make_cloud([]))
    assert asyncio.run(reply(provider)) == "ollama"

    control.choice = ModelChoice(ANTHROPIC, "claude-haiku-5-5")

    assert asyncio.run(reply(provider)) == "claude claude-haiku-5-5"


def test_no_crea_otro_cliente_en_cada_respuesta() -> None:
    made: list[tuple[str, str]] = []
    provider = SwitchingProvider(
        FakeControl(ModelChoice(ANTHROPIC), key="sk-ant"), Named("ollama"), make_cloud(made)
    )

    asyncio.run(reply(provider))
    asyncio.run(reply(provider))

    assert len(made) == 1


def test_una_clave_nueva_crea_otro_cliente() -> None:
    made: list[tuple[str, str]] = []
    control = FakeControl(ModelChoice(ANTHROPIC), key="vieja")
    provider = SwitchingProvider(control, Named("ollama"), make_cloud(made))
    asyncio.run(reply(provider))

    control.saved_key = "nueva"
    asyncio.run(reply(provider))

    assert [key for key, _ in made] == ["vieja", "nueva"]


def test_claude_sin_clave_avisa_donde_cargarla() -> None:
    provider = SwitchingProvider(
        FakeControl(ModelChoice(ANTHROPIC)), Named("ollama"), make_cloud([])
    )

    with pytest.raises(LLMError, match="pestaña Modelo"):
        asyncio.run(reply(provider))


def test_precarga_el_modelo_local_solo_si_es_el_elegido() -> None:
    local = Named("ollama")
    SwitchingProvider(FakeControl(), local, make_cloud([])).preload()
    assert local.preloaded

    other = Named("ollama")
    SwitchingProvider(FakeControl(ModelChoice(ANTHROPIC)), other, make_cloud([])).preload()
    assert not other.preloaded
