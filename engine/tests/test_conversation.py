import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

from kronos_engine.core.conversation import Conversation, Pipeline


class FakeListener:
    def __init__(
        self,
        *texts: str,
        wait: asyncio.Event | None = None,
        announces_speech_end: bool = False,
    ) -> None:
        # Una frase por escucha; cuando se acaban, nadie habla.
        self._texts = list(texts or ["¿Qué hora es?"])
        self._wait = wait
        self._announces_speech_end = announces_speech_end

    async def listen(
        self, on_speech_end: Callable[[], Awaitable[None]] | None = None
    ) -> str | None:
        if self._wait:
            await self._wait.wait()
        if not self._texts:
            return None
        if self._announces_speech_end and on_speech_end:
            await on_speech_end()
        return self._texts.pop(0)


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
        # Vuelve a escuchar por si el usuario sigue; como nadie habla, termina.
        ("state_changed", "listening"),
        ("state_changed", "idle"),
    ]


def test_si_el_usuario_sigue_hablando_la_conversacion_continua() -> None:
    async def scenario() -> tuple[list[tuple[str, str]], list[str]]:
        responder = FakeResponder(["Hola."])
        listener = FakeListener("Hola", "¿Cómo estás?")
        conversation, recorder = build(listener=listener, responder=responder)
        await conversation.activate()
        await conversation.wait()
        return recorder.events, responder.asked

    events, asked = asyncio.run(scenario())
    assert asked == ["Hola", "¿Cómo estás?"]
    assert events == [
        ("state_changed", "listening"),
        ("transcript_final", "Hola"),
        ("state_changed", "thinking"),
        ("state_changed", "speaking"),
        ("assistant_delta", "Hola."),
        ("state_changed", "listening"),
        ("transcript_final", "¿Cómo estás?"),
        ("state_changed", "thinking"),
        ("state_changed", "speaking"),
        ("assistant_delta", "Hola."),
        ("state_changed", "listening"),
        ("state_changed", "idle"),
    ]


def test_pasa_a_pensando_apenas_se_deja_de_escuchar() -> None:
    # Mientras se transcribe el micrófono ya está cerrado: no debe decir "escuchando".
    async def scenario() -> list[tuple[str, str]]:
        conversation, recorder = build(listener=FakeListener(announces_speech_end=True))
        await conversation.activate()
        await conversation.wait()
        return recorder.events

    assert asyncio.run(scenario())[:4] == [
        ("state_changed", "listening"),
        ("state_changed", "thinking"),
        ("transcript_final", "¿Qué hora es?"),
        ("state_changed", "speaking"),
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


def test_si_no_se_entiende_lo_que_se_oyo_sigue_escuchando() -> None:
    # Un ruido o una frase que no se pudo transcribir no corta la conversación.
    async def scenario() -> tuple[list[tuple[str, str]], list[str]]:
        responder = FakeResponder(["Hola."])
        listener = FakeListener("", "Hola", announces_speech_end=True)
        conversation, recorder = build(listener=listener, responder=responder)
        await conversation.activate()
        await conversation.wait()
        return recorder.events, responder.asked

    events, asked = asyncio.run(scenario())
    assert asked == ["Hola"]
    assert events[:4] == [
        ("state_changed", "listening"),
        ("state_changed", "thinking"),
        ("state_changed", "listening"),
        ("state_changed", "thinking"),
    ]


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
