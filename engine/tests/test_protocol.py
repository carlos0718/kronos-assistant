"""El protocolo está escrito dos veces: en el motor y en la interfaz.

Estos tests fallan si un lado cambia y el otro no.
"""

import re
from enum import StrEnum
from pathlib import Path

import pytest

from kronos_engine import PROTOCOL_VERSION
from kronos_engine.core.protocol import AssistantState, ClientMessage, ServerMessage

PROTOCOL_TS = Path(__file__).parents[2] / "apps/desktop/src/engine/protocol.ts"


def ts_list(name: str) -> list[str]:
    """Lee una lista `export const NAME = [...] as const` de protocol.ts."""
    source = PROTOCOL_TS.read_text(encoding="utf-8")
    found = re.search(rf"export const {name} = \[(.*?)\] as const", source, re.DOTALL)
    assert found, f"protocol.ts no define la lista {name}"
    return re.findall(r'"([^"]+)"', found.group(1))


@pytest.mark.parametrize(
    ("ts_name", "python_enum"),
    [
        ("ENGINE_STATES", AssistantState),
        ("SERVER_MESSAGES", ServerMessage),
        ("CLIENT_MESSAGES", ClientMessage),
    ],
)
def test_la_interfaz_y_el_motor_conocen_los_mismos_valores(
    ts_name: str, python_enum: type[StrEnum]
) -> None:
    assert sorted(ts_list(ts_name)) == sorted(member.value for member in python_enum)


def test_la_interfaz_y_el_motor_usan_la_misma_version() -> None:
    source = PROTOCOL_TS.read_text(encoding="utf-8")
    found = re.search(r"export const PROTOCOL_VERSION = (\d+);", source)
    assert found, "protocol.ts no define PROTOCOL_VERSION"
    assert int(found.group(1)) == PROTOCOL_VERSION
