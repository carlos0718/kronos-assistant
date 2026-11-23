import asyncio
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import pytest

from kronos_engine.config.settings import SettingsStore
from kronos_engine.config.tool_levels import StoredLevels
from kronos_engine.core.approval import ApprovalRequest
from kronos_engine.core.tool_levels import ToolLevelError
from kronos_engine.core.tools import PermissionLevel, ToolCall, ToolSpec
from kronos_engine.permissions.gate import PermissionGate
from kronos_engine.permissions.levels import ToolLevels

NORMAL = PermissionLevel.NORMAL
SENSITIVE = PermissionLevel.SENSITIVE
CRITICAL = PermissionLevel.CRITICAL
FORBIDDEN = PermissionLevel.FORBIDDEN
KEY = "clave-correcta"


class FakeTool:
    def __init__(self, name: str, level: PermissionLevel) -> None:
        self.spec = ToolSpec(name, name)
        self.level = level
        self.ran = 0

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return f"hacer {self.spec.name}"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        self.ran += 1
        return "hecho"


class GradedFakeTool(FakeTool):
    def level_for(self, arguments: Mapping[str, Any]) -> PermissionLevel:
        return SENSITIVE

    def detail_for(self, arguments: Mapping[str, Any]) -> str:
        return ""


class FakeVault:
    def __init__(self, key: str | None = KEY, locked: int = 0) -> None:
        self._key = key
        self._locked = locked

    def is_set(self) -> bool:
        return self._key is not None

    def locked_for(self) -> int:
        return self._locked

    def verify(self, attempt: str) -> bool:
        return attempt == self._key


class FakeApprover:
    def __init__(self) -> None:
        self.asked: list[ApprovalRequest] = []

    async def confirm(self, request: ApprovalRequest) -> bool:
        self.asked.append(request)
        return True


def build(
    tmp_path: Path, vault: FakeVault | None = None
) -> tuple[ToolLevels, dict[str, FakeTool], SettingsStore]:
    tools = {
        "open_app": FakeTool("open_app", NORMAL),
        "close_app": FakeTool("close_app", SENSITIVE),
        "edit_registry": FakeTool("edit_registry", CRITICAL),
        "format_disk": FakeTool("format_disk", FORBIDDEN),
        "run_command": GradedFakeTool("run_command", SENSITIVE),
    }
    store = SettingsStore(tmp_path / "config.toml")
    levels = ToolLevels(list(tools.values()), StoredLevels(store), vault or FakeVault())
    return levels, tools, store


def level_of(levels: ToolLevels, name: str) -> PermissionLevel:
    return next(action.level for action in levels.actions() if action.name == name)


def test_de_fabrica_cada_accion_tiene_su_nivel(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    assert [(a.name, a.level, a.factory) for a in levels.actions()][:2] == [
        ("open_app", NORMAL, NORMAL),
        ("close_app", SENSITIVE, SENSITIVE),
    ]


def test_las_acciones_salen_con_su_nombre_para_la_pantalla(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    labels = {action.name: action.label for action in levels.actions()}

    assert labels["open_app"] == "Abrir aplicaciones"
    # Una acción sin nombre propio se muestra con el que tiene.
    assert labels["edit_registry"] == "edit_registry"


def test_subir_una_accion_siempre_se_puede(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    levels.set_level("open_app", 2)
    assert level_of(levels, "open_app") == SENSITIVE

    levels.set_level("open_app", 3)
    assert level_of(levels, "open_app") == CRITICAL


def test_bajar_entre_el_1_y_el_2_se_puede_sin_clave(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path, FakeVault(key=None))

    levels.set_level("close_app", 1)

    assert level_of(levels, "close_app") == NORMAL


def test_no_se_baja_del_nivel_1(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    with pytest.raises(ToolLevelError):
        levels.set_level("open_app", 0)


def test_lo_que_vuelve_al_nivel_de_fabrica_no_queda_guardado(tmp_path: Path) -> None:
    levels, _, store = build(tmp_path)
    levels.set_level("open_app", 2)

    levels.set_level("open_app", 1)

    assert store.load().tool_levels == {}


def test_el_cambio_se_guarda_y_otro_arranque_lo_lee(tmp_path: Path) -> None:
    levels, _, store = build(tmp_path)
    levels.set_level("open_app", 2)

    again = ToolLevels(
        [FakeTool("open_app", NORMAL)],
        StoredLevels(SettingsStore(tmp_path / "config.toml")),
        FakeVault(),
    )

    assert level_of(again, "open_app") == SENSITIVE
    assert store.load().tool_levels == {"open_app": 2}


def test_bajar_del_nivel_3_exige_la_clave(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    with pytest.raises(ToolLevelError, match="clave"):
        levels.set_level("edit_registry", 2)
    with pytest.raises(ToolLevelError, match="no es correcta"):
        levels.set_level("edit_registry", 2, "otra")
    assert level_of(levels, "edit_registry") == CRITICAL

    levels.set_level("edit_registry", 2, KEY)
    assert level_of(levels, "edit_registry") == SENSITIVE


def test_bajar_algo_que_se_subio_a_3_tambien_exige_la_clave(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)
    levels.set_level("open_app", 3)

    with pytest.raises(ToolLevelError):
        levels.set_level("open_app", 1)

    levels.set_level("open_app", 1, KEY)
    assert level_of(levels, "open_app") == NORMAL


def test_sin_clave_creada_no_se_baja_del_nivel_3(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path, FakeVault(key=None))

    with pytest.raises(ToolLevelError, match="todavía no creaste"):
        levels.set_level("edit_registry", 2, KEY)


def test_con_el_nivel_critico_bloqueado_ni_se_prueba_la_clave(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path, FakeVault(locked=120))

    with pytest.raises(ToolLevelError, match="bloqueado"):
        levels.set_level("edit_registry", 2, KEY)


def test_el_nivel_4_no_se_cambia(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    with pytest.raises(ToolLevelError, match="prohibida"):
        levels.set_level("format_disk", 1)
    assert next(a for a in levels.actions() if a.name == "format_disk").fixed


def test_no_se_puede_poner_nivel_4_a_una_accion(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    with pytest.raises(ToolLevelError):
        levels.set_level("open_app", 4)


def test_una_accion_que_no_existe_se_rechaza(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    with pytest.raises(ToolLevelError, match="no existe"):
        levels.set_level("explotar", 2)


def test_la_terminal_no_baja_de_su_nivel_de_fabrica(tmp_path: Path) -> None:
    levels, _, _ = build(tmp_path)

    with pytest.raises(ToolLevelError):
        levels.set_level("run_command", 1)
    assert next(a for a in levels.actions() if a.name == "run_command").lowest == SENSITIVE


def test_un_archivo_editado_a_mano_no_baja_lo_que_no_se_puede(tmp_path: Path) -> None:
    levels, _, store = build(tmp_path)
    store.update(tool_levels={"run_command": 1, "format_disk": 1, "open_app": 9})

    assert level_of(levels, "run_command") == SENSITIVE
    assert level_of(levels, "format_disk") == FORBIDDEN
    assert level_of(levels, "open_app") == NORMAL


def run(gate: PermissionGate, name: str) -> str:
    return asyncio.run(gate.run(ToolCall(name)))


def test_el_control_de_permisos_usa_el_nivel_elegido(tmp_path: Path) -> None:
    levels, tools, _ = build(tmp_path)
    approver = FakeApprover()
    gate = PermissionGate(list(tools.values()), approver, levels=levels)

    run(gate, "open_app")
    assert approver.asked == []

    levels.set_level("open_app", 2)
    run(gate, "open_app")
    assert len(approver.asked) == 1

    levels.set_level("close_app", 1)
    run(gate, "close_app")
    assert len(approver.asked) == 1
    assert tools["close_app"].ran == 1


def test_una_accion_subida_a_3_pide_la_clave(tmp_path: Path) -> None:
    levels, tools, _ = build(tmp_path)
    levels.set_level("open_app", 3)
    gate = PermissionGate(list(tools.values()), FakeApprover(), levels=levels)

    result = run(gate, "open_app")

    assert tools["open_app"].ran == 0
    assert "clave secreta" in result
