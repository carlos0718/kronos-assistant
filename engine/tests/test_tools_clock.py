import asyncio
from datetime import datetime, timedelta, timezone

from kronos_engine.core.spoken_time import spoken_zone
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


def test_la_hora_lleva_la_zona_horaria() -> None:
    # Claude pasaba mal la hora de un partido: no sabía en qué zona estaba el usuario.
    argentina = timezone(timedelta(hours=-3))
    tool = CurrentTimeTool(lambda: datetime(2026, 11, 19, 15, 42, tzinfo=argentina))

    assert "Hora: 15:42 (UTC-3)." in asyncio.run(tool.run({}))


def test_la_zona_se_dice_con_los_minutos_si_los_tiene() -> None:
    india = timezone(timedelta(hours=5, minutes=30))

    assert spoken_zone(datetime(2026, 1, 1, tzinfo=india)) == "UTC+5:30"


def test_la_zona_lleva_el_nombre_que_le_da_windows() -> None:
    zone = timezone(timedelta(hours=-3), "Hora estándar de Argentina")

    assert spoken_zone(datetime(2026, 1, 1, tzinfo=zone)) == "UTC-3, Hora estándar de Argentina"


def test_sin_zona_no_inventa_una() -> None:
    assert spoken_zone(datetime(2026, 1, 1)) == ""
