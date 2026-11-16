import asyncio

import pytest

from kronos_engine.core.approval import ApprovalDesk, ApprovalRequest, parse_answer

REQUEST = ApprovalRequest("close_app", "cerrar Spotify")


@pytest.mark.parametrize(
    "text",
    [
        *["Sí", "si.", "Sí, dale", "Dale", "Confirmo", "hacelo", "Adelante", "ok", "Yes"],
        "sí, cerrala",
        # Así transcribió el reconocedor un «sí» en las pruebas con micrófono.
        *["C", "c.", "See", "See, that's it"],
    ],
)
def test_un_si_claro_aprueba(text: str) -> None:
    assert parse_answer(text) is True


@pytest.mark.parametrize(
    "text",
    ["No", "no.", "No, dejá", "Cancelá", "cancelar", "mejor no", "No sé", "Pará", "sí... no, no"],
)
def test_un_no_rechaza_aunque_venga_con_un_si(text: str) -> None:
    assert parse_answer(text) is False


@pytest.mark.parametrize("text", ["", "Yeah", "North", "¿Qué?", "mmm", "casi"])
def test_lo_que_no_es_claro_no_es_una_respuesta(text: str) -> None:
    # El reconocedor a veces transcribe «No» como «Yeah» o «North»: por eso
    # «yeah» no vale como sí.
    assert parse_answer(text) is None


class FakeApprover:
    def __init__(self, answer: bool) -> None:
        self._answer = answer
        self.asked: list[ApprovalRequest] = []

    async def confirm(self, request: ApprovalRequest) -> bool:
        self.asked.append(request)
        return self._answer


def test_sin_nadie_a_quien_preguntarle_no_se_aprueba() -> None:
    assert asyncio.run(ApprovalDesk().confirm(REQUEST)) is False


@pytest.mark.parametrize("answer", [True, False])
def test_le_pregunta_a_quien_esta_conectado(answer: bool) -> None:
    desk, approver = ApprovalDesk(), FakeApprover(answer)
    desk.connect(approver)

    assert asyncio.run(desk.confirm(REQUEST)) is answer
    assert approver.asked == [REQUEST]
