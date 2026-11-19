import asyncio
from datetime import datetime

from kronos_engine.core.tools import PermissionLevel
from kronos_engine.tools.clock import CurrentTimeTool


def test_dice_el_dia_la_fecha_y_la_hora() -> None:
    tool = CurrentTimeTool(lambda: datetime(2026, 11, 16, 9, 5))

    result = asyncio.run(tool.run({}))

    assert "Hora: 09:05." in result
    assert "Hoy: lunes 16 de noviembre de 2026." in result


def test_trae_la_fecha_de_manana_ya_calculada() -> None:
    # qwen3:8b decía que mañana era el mismo día que le daba el reloj.
    tool = CurrentTimeTool(lambda: datetime(2026, 11, 19, 15, 42))

    assert "Mañana: viernes 20 de noviembre de 2026." in asyncio.run(tool.run({}))


def test_manana_cambia_de_mes_y_de_ano() -> None:
    tool = CurrentTimeTool(lambda: datetime(2026, 12, 31, 23, 50))

    assert "Mañana: viernes 1 de enero de 2027." in asyncio.run(tool.run({}))


def test_es_una_accion_normal() -> None:
    assert CurrentTimeTool().level == PermissionLevel.NORMAL


def test_se_describe_en_infinitivo() -> None:
    assert asyncio.run(CurrentTimeTool().describe({})) == "decir la fecha y la hora"


def test_pide_decir_solo_lo_preguntado() -> None:
    # Con la fecha de mañana en el resultado, el modelo la leía al preguntarle la hora.
    assert "solo lo que te preguntaron" in asyncio.run(CurrentTimeTool().run({}))
