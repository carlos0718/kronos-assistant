import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import pytest

from kronos_engine.core.approval import ApprovalRequest
from kronos_engine.core.tools import PermissionLevel, ToolCall, ToolError, ToolSpec
from kronos_engine.permissions.gate import PermissionGate


class FakeTool:
    def __init__(
        self,
        name: str,
        level: PermissionLevel = PermissionLevel.NORMAL,
        fail_with: Exception | None = None,
        cannot: str = "",
    ) -> None:
        self._cannot = cannot
        self.spec = ToolSpec(name, f"Acción {name}.")
        self.level = level
        self._fail_with = fail_with
        self.ran: list[Mapping[str, Any]] = []

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        if self._cannot:
            raise ToolError(self._cannot)
        return f"hacer {self.spec.name} con {dict(arguments)}"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        self.ran.append(arguments)
        if self._fail_with:
            raise self._fail_with
        return f"{self.spec.name} hecho"


class FakeApprover:
    def __init__(self, answer: bool) -> None:
        self._answer = answer
        self.asked: list[ApprovalRequest] = []

    async def confirm(self, request: ApprovalRequest) -> bool:
        self.asked.append(request)
        return self._answer


def run(gate: PermissionGate, call: ToolCall) -> str:
    return asyncio.run(gate.run(call))


def test_una_accion_delicada_se_ejecuta_si_el_usuario_la_aprueba() -> None:
    tool = FakeTool("close_app", PermissionLevel.SENSITIVE)
    approver = FakeApprover(True)

    result = run(PermissionGate([tool], approver), ToolCall("close_app", {"name": "Spotify"}))

    assert result == "close_app hecho"
    assert approver.asked == [
        ApprovalRequest("close_app", "hacer close_app con {'name': 'Spotify'}")
    ]


def test_una_accion_delicada_no_se_ejecuta_si_el_usuario_no_la_aprueba() -> None:
    tool = FakeTool("close_app", PermissionLevel.SENSITIVE)

    result = run(
        PermissionGate([tool], FakeApprover(False)), ToolCall("close_app", {"name": "Spotify"})
    )

    assert tool.ran == []
    assert "contestó que no" in result.lower()


def test_no_se_pide_aprobacion_para_algo_que_ya_se_sabe_que_no_se_puede() -> None:
    tool = FakeTool("close_app", PermissionLevel.SENSITIVE, cannot="Spotify no está abierto.")
    approver = FakeApprover(True)

    result = run(PermissionGate([tool], approver), ToolCall("close_app", {"name": "Spotify"}))

    assert approver.asked == []
    assert tool.ran == []
    assert "Spotify no está abierto." in result


def test_una_accion_normal_no_pide_aprobacion() -> None:
    approver = FakeApprover(False)

    result = run(PermissionGate([FakeTool("open_app")], approver), ToolCall("open_app"))

    assert result == "open_app hecho"
    assert approver.asked == []


def test_la_aprobacion_del_usuario_no_alcanza_para_lo_critico() -> None:
    # El nivel 3 pide la clave secreta: un «sí» no la reemplaza.
    tool = FakeTool("edit_registry", PermissionLevel.CRITICAL)
    approver = FakeApprover(True)

    result = run(PermissionGate([tool], approver), ToolCall("edit_registry"))

    assert tool.ran == []
    assert approver.asked == []
    assert "no se ejecutó" in result.lower()


def test_ni_la_aprobacion_del_usuario_ejecuta_lo_prohibido() -> None:
    tool = FakeTool("format_disk", PermissionLevel.FORBIDDEN)
    approver = FakeApprover(True)

    run(PermissionGate([tool], approver), ToolCall("format_disk"))

    assert tool.ran == []
    assert approver.asked == []


def test_registra_si_el_usuario_aprobo_o_no(caplog: pytest.LogCaptureFixture) -> None:
    tool = FakeTool("close_app", PermissionLevel.SENSITIVE)

    with caplog.at_level(logging.INFO):
        run(PermissionGate([tool], FakeApprover(True)), ToolCall("close_app"))
        run(PermissionGate([tool], FakeApprover(False)), ToolCall("close_app"))

    assert "aprobada por el usuario" in caplog.messages[0]
    assert "rechazada" in caplog.messages[-1]
    assert "el usuario no la aprobó" in caplog.messages[-1]


def test_una_accion_normal_se_ejecuta_sin_preguntar() -> None:
    tool = FakeTool("open_app")
    gate = PermissionGate([tool])

    assert run(gate, ToolCall("open_app", {"name": "Spotify"})) == "open_app hecho"
    assert tool.ran == [{"name": "Spotify"}]


@pytest.mark.parametrize("level", [PermissionLevel.SENSITIVE, PermissionLevel.CRITICAL])
def test_sin_forma_de_pedir_aprobacion_lo_delicado_no_se_ejecuta(level: PermissionLevel) -> None:
    tool = FakeTool("run_command", level)

    result = run(PermissionGate([tool]), ToolCall("run_command", {"command": "dir"}))

    assert tool.ran == []
    assert "no se ejecutó" in result.lower()


def test_lo_prohibido_no_se_ejecuta_nunca() -> None:
    tool = FakeTool("format_disk", PermissionLevel.FORBIDDEN)

    result = run(PermissionGate([tool]), ToolCall("format_disk"))

    assert tool.ran == []
    assert "prohibida" in result.lower()


def test_lo_prohibido_ni_se_le_ofrece_al_modelo() -> None:
    allowed = FakeTool("open_app")
    forbidden = FakeTool("format_disk", PermissionLevel.FORBIDDEN)

    assert PermissionGate([allowed, forbidden]).specs() == [allowed.spec]


def test_una_accion_que_no_existe_se_rechaza() -> None:
    # El modelo puede inventar un nombre: no hay nada que ejecutar.
    result = run(PermissionGate([FakeTool("open_app")]), ToolCall("delete_everything"))

    assert "no existe" in result.lower()


def test_si_la_accion_no_se_puede_hacer_el_modelo_recibe_el_motivo() -> None:
    tool = FakeTool("open_app", fail_with=ToolError("No hay ninguna aplicación con ese nombre."))

    result = run(PermissionGate([tool]), ToolCall("open_app", {"name": "Xyz"}))

    assert "No hay ninguna aplicación con ese nombre." in result


def test_un_fallo_inesperado_no_corta_la_conversacion() -> None:
    tool = FakeTool("open_app", fail_with=OSError("acceso denegado"))

    result = run(PermissionGate([tool]), ToolCall("open_app", {"name": "Xyz"}))

    assert "falló" in result.lower()


def test_registra_cada_accion_ejecutada_o_rechazada(caplog: pytest.LogCaptureFixture) -> None:
    gate = PermissionGate([FakeTool("open_app"), FakeTool("run_command", PermissionLevel.CRITICAL)])

    with caplog.at_level(logging.INFO):
        run(gate, ToolCall("open_app", {"name": "Spotify"}))
        run(gate, ToolCall("run_command", {"command": "dir"}))

    assert "open_app" in caplog.messages[0]
    assert "ejecutada" in caplog.messages[0]
    assert "run_command" in caplog.messages[1]
    assert "rechazada" in caplog.messages[1]


def test_el_registro_no_guarda_los_datos_de_la_accion(caplog: pytest.LogCaptureFixture) -> None:
    # Lo que se pidió puede ser privado: queda qué acción fue, no con qué datos.
    gate = PermissionGate([FakeTool("open_app")])

    with caplog.at_level(logging.INFO):
        run(gate, ToolCall("open_app", {"name": "Diario íntimo"}))

    assert "Diario íntimo" not in caplog.text


def test_con_depuracion_el_registro_dice_por_que_no_se_pudo(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # Un open_file falló sin que el registro dijera por qué.
    tool = FakeTool("open_file", fail_with=ToolError("Hay varios archivos que pueden ser."))

    with caplog.at_level(logging.DEBUG, logger="kronos_engine"):
        run(PermissionGate([tool]), ToolCall("open_file", {"file": "CV"}))

    assert "Hay varios archivos que pueden ser." in caplog.text


def test_sin_depuracion_el_motivo_no_queda_en_el_registro(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # El motivo puede nombrar archivos del usuario.
    tool = FakeTool("open_file", fail_with=ToolError("No encontré «Diario íntimo»."))

    with caplog.at_level(logging.INFO, logger="kronos_engine"):
        run(PermissionGate([tool]), ToolCall("open_file", {"file": "Diario íntimo"}))

    assert "no se pudo hacer" in caplog.text
    assert "Diario íntimo" not in caplog.text


class FakeVault:
    def __init__(self, key: str | None = "clave-correcta", locked: int = 0) -> None:
        self._key = key
        self._locked = locked
        self.tried: list[str] = []

    def is_set(self) -> bool:
        return self._key is not None

    def locked_for(self) -> int:
        return self._locked

    def verify(self, attempt: str) -> bool:
        self.tried.append(attempt)
        return attempt == self._key


class FakeAsker:
    def __init__(self, typed: str | None) -> None:
        self._typed = typed
        self.asked: list[ApprovalRequest] = []

    async def ask_secret(self, request: ApprovalRequest) -> str | None:
        self.asked.append(request)
        return self._typed


def critical_gate(tool: FakeTool, vault: FakeVault, asker: FakeAsker | None) -> PermissionGate:
    return PermissionGate([tool], FakeApprover(True), vault, asker)


def test_lo_critico_se_ejecuta_con_la_clave_correcta() -> None:
    tool = FakeTool("edit_registry", PermissionLevel.CRITICAL)
    asker = FakeAsker("clave-correcta")

    result = run(critical_gate(tool, FakeVault(), asker), ToolCall("edit_registry", {"k": 1}))

    assert result == "edit_registry hecho"
    assert asker.asked == [ApprovalRequest("edit_registry", "hacer edit_registry con {'k': 1}")]


def test_lo_critico_no_se_ejecuta_con_una_clave_incorrecta() -> None:
    tool = FakeTool("edit_registry", PermissionLevel.CRITICAL)

    result = run(critical_gate(tool, FakeVault(), FakeAsker("otra")), ToolCall("edit_registry"))

    assert tool.ran == []
    assert "clave" in result.lower()
    assert "no se ejecutó" in result.lower()


def test_lo_critico_no_se_ejecuta_si_el_usuario_cancela() -> None:
    tool = FakeTool("edit_registry", PermissionLevel.CRITICAL)
    vault = FakeVault()

    result = run(critical_gate(tool, vault, FakeAsker(None)), ToolCall("edit_registry"))

    assert tool.ran == []
    assert vault.tried == []
    assert "no se ejecutó" in result.lower()


def test_sin_clave_configurada_lo_critico_no_se_ejecuta_ni_se_pregunta() -> None:
    tool = FakeTool("edit_registry", PermissionLevel.CRITICAL)
    asker = FakeAsker("lo-que-sea")

    result = run(critical_gate(tool, FakeVault(key=None), asker), ToolCall("edit_registry"))

    assert tool.ran == []
    assert asker.asked == []
    assert "no hay una clave secreta configurada" in result.lower()


def test_con_el_nivel_critico_bloqueado_no_se_pregunta() -> None:
    tool = FakeTool("edit_registry", PermissionLevel.CRITICAL)
    asker = FakeAsker("clave-correcta")

    result = run(critical_gate(tool, FakeVault(locked=120), asker), ToolCall("edit_registry"))

    assert tool.ran == []
    assert asker.asked == []
    assert "bloqueado" in result.lower()


def test_el_modelo_no_ve_la_clave_ni_se_registra(caplog: pytest.LogCaptureFixture) -> None:
    tool = FakeTool("edit_registry", PermissionLevel.CRITICAL)

    with caplog.at_level(logging.DEBUG):
        result = run(
            critical_gate(tool, FakeVault(), FakeAsker("intento-secreto")),
            ToolCall("edit_registry"),
        )

    assert "intento-secreto" not in result
    assert "intento-secreto" not in caplog.text


class GradedFakeTool(FakeTool):
    """Una acción cuyo nivel depende de lo que se le pide."""

    def level_for(self, arguments: Mapping[str, Any]) -> PermissionLevel:
        return PermissionLevel(arguments["level"])

    def detail_for(self, arguments: Mapping[str, Any]) -> str:
        return f"detalle {arguments['level']}"


def test_una_accion_graduada_pide_lo_que_exige_cada_pedido() -> None:
    tool = GradedFakeTool("run_command", PermissionLevel.SENSITIVE)
    approver = FakeApprover(True)
    gate = PermissionGate([tool], approver)

    assert run(gate, ToolCall("run_command", {"level": 2})) == "run_command hecho"

    assert approver.asked == [
        ApprovalRequest("run_command", "hacer run_command con {'level': 2}", "detalle 2")
    ]


def test_una_accion_graduada_prohibida_no_se_ejecuta_ni_se_pregunta() -> None:
    tool = GradedFakeTool("run_command", PermissionLevel.SENSITIVE)
    approver = FakeApprover(True)

    run(PermissionGate([tool], approver), ToolCall("run_command", {"level": 4}))

    assert tool.ran == []
    assert approver.asked == []


def test_una_accion_graduada_no_baja_del_nivel_de_fabrica() -> None:
    tool = GradedFakeTool("run_command", PermissionLevel.SENSITIVE)
    approver = FakeApprover(True)

    run(PermissionGate([tool], approver), ToolCall("run_command", {"level": 1}))

    assert len(approver.asked) == 1


def test_una_accion_graduada_critica_pide_la_clave_con_el_detalle() -> None:
    tool = GradedFakeTool("run_command", PermissionLevel.SENSITIVE)
    asker = FakeAsker("clave-correcta")
    gate = PermissionGate([tool], FakeApprover(True), FakeVault(), asker)

    assert run(gate, ToolCall("run_command", {"level": 3})) == "run_command hecho"

    assert asker.asked[0].detail == "detalle 3"
