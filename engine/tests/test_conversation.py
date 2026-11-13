import asyncio
from collections.abc import AsyncIterator
from typing import Any

from kronos_engine.core.conversation import Conversation, Pipeline


class FakeListener:
    def __init__(self, text: str = "¿Qué hora es?", wait: asyncio.Event | None = None) -> None:
        self._text = text
        self._wait = wait

    async def listen(self) -> str:
        if self._wait:
            await self._wait.wait()
        return self._text


class FakeResponder:
    def __init__(self, deltas: list[str], fail_with: Exception | None = None) -> None:
        self._deltas = deltas
        self._fail_with = fail_with
        self.asked: list[str] = []

    async def respond(self, text: str) -> AsyncIterator[str]:
        self.asked.append(text)
        for delta in self._deltas:
            yield delta
        if self._fail_with:
            raise self._fail_with


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def speak(self, text: str) -> None:
        self.spoken.append(text)


class Recorder:
    """Guarda lo que la conversación le manda a la interfaz, en orden."""

    def __init__(self) -> None:
        self.events: list[tuple[str, str]] = []

    async def set_state(self, state: str) -> None:
        self.events.append(("state_changed", state))

    async def emit(self, type_: str, payload: dict[str, Any]) -> None:
        self.events.append((type_, payload.get("text") or payload.get("message") or ""))


def build(
    listener: FakeListener | None = None,
    responder: FakeResponder | None = None,
    speaker: FakeSpeaker | None = None,
) -> tuple[Conversation, Recorder]:
    recorder = Recorder()
    pipeline = Pipeline(
        listener=listener or FakeListener(),
        responder=responder or FakeResponder(["Son las ", "tres. ", "¿Algo más?"]),
        speaker=speaker or FakeSpeaker(),
    )
    return Conversation(pipeline, recorder.set_state, recorder.emit), recorder


def test_un_turno_completo_recorre_los_estados_en_orden() -> None:
    async def scenario() -> list[tuple[str, str]]:
        conversation, recorder = build()
        await conversation.activate()
        await conversation.wait()
        return recorder.events

    assert asyncio.run(scenario()) == [
        ("state_changed", "listening"),
        ("transcript_final", "¿Qué hora es?"),
        ("state_changed", "thinking"),
        ("state_changed", "speaking"),
        ("assistant_delta", "Son las "),
        ("assistant_delta", "tres. "),
        ("assistant_delta", "¿Algo más?"),
        ("state_changed", "idle"),
    ]


def test_el_modelo_recibe_la_transcripcion_y_se_habla_frase_por_frase() -> None:
    async def scenario() -> tuple[list[str], list[str]]:
        responder = FakeResponder(["Son las ", "tres. ", "¿Algo más?"])
        speaker = FakeSpeaker()
        conversation, _ = build(responder=responder, speaker=speaker)
        await conversation.activate()
        await conversation.wait()
        return responder.asked, speaker.spoken

    asked, spoken = asyncio.run(scenario())
    assert asked == ["¿Qué hora es?"]
    assert spoken == ["Son las tres.", "¿Algo más?"]


def test_si_no_se_entendio_nada_vuelve_a_inactivo_sin_llamar_al_modelo() -> None:
    async def scenario() -> tuple[list[tuple[str, str]], list[str]]:
        responder = FakeResponder(["no debería usarse"])
        conversation, recorder = build(listener=FakeListener("   "), responder=responder)
        await conversation.activate()
        await conversation.wait()
        return recorder.events, responder.asked

    events, asked = asyncio.run(scenario())
    assert events == [("state_changed", "listening"), ("state_changed", "idle")]
    assert asked == []


def test_un_fallo_vuelve_a_inactivo_y_despues_informa_el_error() -> None:
    # El error va después del estado: la interfaz borra el error al cambiar de estado.
    async def scenario() -> list[tuple[str, str]]:
        responder = FakeResponder(["Hola. "], fail_with=RuntimeError("sin conexión"))
        conversation, recorder = build(responder=responder)
        await conversation.activate()
        await conversation.wait()
        return recorder.events

    assert asyncio.run(scenario())[-2:] == [
        ("state_changed", "idle"),
        ("error", "sin conexión"),
    ]


def test_cancel_corta_el_turno_y_vuelve_a_inactivo() -> None:
    async def scenario() -> tuple[list[tuple[str, str]], list[str]]:
        speaker = FakeSpeaker()
        never = asyncio.Event()
        conversation, recorder = build(listener=FakeListener(wait=never), speaker=speaker)
        await conversation.activate()
        await asyncio.sleep(0)  # Deja que el turno empiece a escuchar.
        await conversation.cancel()
        return recorder.events, speaker.spoken

    events, spoken = asyncio.run(scenario())
    assert events == [("state_changed", "listening"), ("state_changed", "idle")]
    assert spoken == []


def test_cancel_sin_turno_en_curso_no_hace_nada() -> None:
    async def scenario() -> list[tuple[str, str]]:
        conversation, recorder = build()
        await conversation.cancel()
        return recorder.events

    assert asyncio.run(scenario()) == []


def test_activate_durante_un_turno_lo_reemplaza_por_uno_nuevo() -> None:
    async def scenario() -> list[tuple[str, str]]:
        gate = asyncio.Event()
        conversation, recorder = build(listener=FakeListener(wait=gate))
        await conversation.activate()
        await asyncio.sleep(0)
        await conversation.activate()
        gate.set()
        await conversation.wait()
        return recorder.events

    events = asyncio.run(scenario())
    assert events[:3] == [
        ("state_changed", "listening"),
        ("state_changed", "idle"),
        ("state_changed", "listening"),
    ]
    assert [e for e in events if e[0] == "transcript_final"] == [
        ("transcript_final", "¿Qué hora es?")
    ]
