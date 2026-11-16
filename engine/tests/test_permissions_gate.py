import asyncio
import logging
from collections.abc import Mapping
from typing import Any

import pytest

from kronos_engine.core.tools import PermissionLevel, ToolCall, ToolError, ToolSpec
from kronos_engine.permissions.gate import PermissionGate


class FakeTool:
    def __init__(
        self,
        name: str,
        level: PermissionLevel = PermissionLevel.NORMAL,
        fail_with: Exception | None = None,
    ) -> None:
        self.spec = ToolSpec(name, f"Acción {name}.")
        self.level = level
        self._fail_with = fail_with
        self.ran: list[Mapping[str, Any]] = []

    async def run(self, arguments: Mapping[str, Any]) -> str:
        self.ran.append(arguments)
        if self._fail_with:
            raise self._fail_with
        return f"{self.spec.name} hecho"


def run(gate: PermissionGate, call: ToolCall) -> str:
    return asyncio.run(gate.run(call))


def test_una_accion_normal_se_ejecuta_sin_preguntar() -> None:
    tool = FakeTool("open_app")
    gate = PermissionGate([tool])

    assert run(gate, ToolCall("open_app", {"name": "Spotify"})) == "open_app hecho"
    assert tool.ran == [{"name": "Spotify"}]


@pytest.mark.parametrize("level", [PermissionLevel.SENSITIVE, PermissionLevel.CRITICAL])
def test_lo_que_pide_confirmacion_o_clave_todavia_no_se_ejecuta(level: PermissionLevel) -> None:
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
