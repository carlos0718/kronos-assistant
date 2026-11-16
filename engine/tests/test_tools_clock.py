import asyncio
from datetime import datetime

from kronos_engine.core.tools import PermissionLevel
from kronos_engine.tools.clock import CurrentTimeTool


def test_dice_el_dia_la_fecha_y_la_hora() -> None:
    tool = CurrentTimeTool(lambda: datetime(2026, 11, 16, 9, 5))

    assert asyncio.run(tool.run({})) == "lunes 16 de noviembre de 2026, 09:05"


def test_es_una_accion_normal() -> None:
    assert CurrentTimeTool().level == PermissionLevel.NORMAL


def test_se_describe_en_infinitivo() -> None:
    assert asyncio.run(CurrentTimeTool().describe({})) == "decir la fecha y la hora"
