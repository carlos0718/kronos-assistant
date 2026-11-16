"""La conversación le pregunta al usuario si aprueba una acción delicada."""

import asyncio
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Any

import pytest

from kronos_engine.core.approval import ApprovalDesk, ApprovalRequest
from kronos_engine.core.conversation import Conversation, Pipeline

REQUEST = ApprovalRequest("close_app", "cerrar Spotify")
QUESTION = "¿Confirmás cerrar Spotify?"


class FakeSpeaker:
    def __init__(self) -> None:
        self.spoken: list[str] = []

    async def speak(
        self, sentences: AsyncIterator[str], on_start: Callable[[], None] | None = None
    ) -> None:
        async for sentence in sentences:
            await asyncio.sleep(0)  # Decir una frase lleva un momento.
            self.spoken.append(sentence)


class FakeListener:
    """Devuelve una frase por escucha; `...` es quedarse esperando y `None`, que nadie habló."""

    def __init__(self, speaker: FakeSpeaker, *answers: Any) -> None:
        self._speaker = speaker
        self._answers = ["Cerrá Spotify", *answers]
        # Qué se había dicho al abrir el micrófono en cada escucha.
        self.heard_before: list[list[str]] = []
        self.cancelled = False
        # Se prende cuando empieza a escuchar la respuesta a la confirmación.
        self.asked_to_confirm = asyncio.Event()

    async def listen(
        self,
        on_speech_end: Callable[[], Awaitable[None]] | None = None,
        wait_seconds: float | None = None,
    ) -> str | None:
        self.heard_before.append(list(self._speaker.spoken))
        if len(self.heard_before) == 2:
            self.asked_to_confirm.set()
        answer = self._answers.pop(0) if self._answers else None
        if answer is ...:
            try:
                await asyncio.Event().wait()
            except asyncio.CancelledError:
                self.cancelled = True
                raise
        return answer


class AskingResponder:
    """Como el agente: dice algo, pide la aprobación y cuenta cómo terminó."""

    def __init__(self, desk: ApprovalDesk) -> None:
        self._desk = desk
        self.answers: list[bool] = []

    async def respond(self, text: str) -> AsyncIterator[str]:
        yield "Dale.\n"
        approved = await self._desk.confirm(REQUEST)
        self.answers.append(approved)
        yield "Listo." if approved else "No lo hago."


class Recorder:
    def __init__(self) -> None:
        self.events: list[tuple[str, Any]] = []

    async def set_state(self, state: str) -> None:
        self.events.append(("state_changed", str(state)))

    async def emit(self, type_: str, payload: dict[str, Any]) -> None:
        self.events.append((str(type_), payload))

    def of(self, type_: str) -> list[Any]:
        return [payload for kind, payload in self.events if kind == type_]


class Scene:
    def __init__(self, *answers: Any) -> None:
        self.speaker = FakeSpeaker()
        self.listener = FakeListener(self.speaker, *answers)
        self.recorder = Recorder()
        desk = ApprovalDesk()
        self.responder = AskingResponder(desk)
        pipeline = Pipeline(self.listener, self.responder, self.speaker, approvals=desk)
        self.conversation = Conversation(pipeline, self.recorder.set_state, self.recorder.emit)

    async def run(self) -> None:
        await self.conversation.activate()
        await self.conversation.wait()

    async def until_listening_for_the_answer(self) -> None:
        await self.listener.asked_to_confirm.wait()


def test_un_si_dicho_en_voz_alta_aprueba_la_accion() -> None:
    scene = Scene("Sí, dale")

    asyncio.run(scene.run())

    assert scene.responder.answers == [True]
    assert scene.speaker.spoken == ["Dale.", QUESTION, "Listo."]


def test_un_no_dicho_en_voz_alta_la_rechaza() -> None:
    scene = Scene("No")

    asyncio.run(scene.run())

    assert scene.responder.answers == [False]
    assert scene.speaker.spoken == ["Dale.", QUESTION, "No lo hago."]


def test_el_microfono_se_abre_cuando_kronos_termino_de_preguntar() -> None:
    # Si se abriera antes, Kronos oiría su propia pregunta.
    scene = Scene("Sí")

    asyncio.run(scene.run())

    assert scene.listener.heard_before[1] == ["Dale.", QUESTION]


def test_le_muestra_la_pregunta_a_la_interfaz_y_despues_como_termino() -> None:
    scene = Scene("Sí")

    asyncio.run(scene.run())

    assert scene.recorder.of("confirmation_request") == [
        {"id": "1", "summary": "cerrar Spotify", "detail": ""}
    ]
    assert scene.recorder.of("confirmation_resolved") == [{"id": "1", "approved": True}]


def test_mientras_espera_la_respuesta_esta_escuchando_y_despues_sigue_el_turno() -> None:
    scene = Scene("Sí")

    asyncio.run(scene.run())

    kinds = [
        payload if kind == "state_changed" else kind
        for kind, payload in scene.recorder.events
        if kind != "assistant_delta" and kind != "transcript_final"
    ]
    assert kinds[:8] == [
        "listening",
        "thinking",
        "speaking",
        "confirmation_request",
        "listening",
        "confirmation_resolved",
        "thinking",
        "speaking",
    ]


def test_la_respuesta_a_la_pregunta_no_se_muestra_como_un_pedido_nuevo() -> None:
    scene = Scene("Sí")

    asyncio.run(scene.run())

    assert scene.recorder.of("transcript_final") == [{"text": "Cerrá Spotify"}]


def test_si_nadie_contesta_es_un_no(caplog: pytest.LogCaptureFixture) -> None:
    scene = Scene(None)

    with caplog.at_level(logging.INFO):
        asyncio.run(scene.run())

    assert scene.responder.answers == [False]
    assert "Nadie contestó la confirmación" in caplog.text


def test_si_no_queda_claro_vuelve_a_escuchar() -> None:
    scene = Scene("mmm", "", "sí")

    asyncio.run(scene.run())

    assert scene.responder.answers == [True]


def test_si_nunca_queda_claro_es_un_no() -> None:
    scene = Scene("mmm", "Yeah", "¿Qué?")

    asyncio.run(scene.run())

    assert scene.responder.answers == [False]
    # El pedido, tres intentos de respuesta y la escucha de después de responder.
    assert len(scene.listener.heard_before) == 5


@pytest.mark.parametrize("approved", [True, False])
def test_un_clic_contesta_la_pregunta_y_deja_de_escuchar(approved: bool) -> None:
    scene = Scene(...)

    async def scenario() -> None:
        await scene.conversation.activate()
        await scene.until_listening_for_the_answer()
        scene.conversation.confirmations.answer("1", approved)
        await scene.conversation.wait()

    asyncio.run(scenario())

    assert scene.responder.answers == [approved]
    assert scene.listener.cancelled
    assert scene.recorder.of("confirmation_resolved") == [{"id": "1", "approved": approved}]


def test_un_clic_para_otra_pregunta_se_ignora() -> None:
    scene = Scene(...)

    async def scenario() -> None:
        await scene.conversation.activate()
        await scene.until_listening_for_the_answer()
        scene.conversation.confirmations.answer("99", True)
        await asyncio.sleep(0)
        assert scene.responder.answers == []
        scene.conversation.confirmations.answer("1", False)
        await scene.conversation.wait()

    asyncio.run(scenario())

    assert scene.responder.answers == [False]


def test_cortar_la_conversacion_cierra_la_pregunta_sin_aprobarla() -> None:
    scene = Scene(...)

    async def scenario() -> None:
        await scene.conversation.activate()
        await scene.until_listening_for_the_answer()
        await scene.conversation.cancel()
        # Un clic que llega tarde no hace nada.
        scene.conversation.confirmations.answer("1", True)

    asyncio.run(scenario())

    assert scene.responder.answers == []
    assert scene.recorder.of("confirmation_resolved") == [{"id": "1", "approved": False}]
    assert scene.recorder.events[-1] == ("state_changed", "idle")
