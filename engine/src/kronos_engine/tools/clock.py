"""Acción: decir la fecha y la hora."""

from collections.abc import Callable, Mapping
from datetime import datetime
from typing import Any

from kronos_engine.core.tools import PermissionLevel, ToolSpec

# Escritos a mano para no depender del idioma en que esté configurado el sistema.
_DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


class CurrentTimeTool:
    spec = ToolSpec(
        "current_time",
        "Devuelve el día de la semana, la fecha y la hora actuales (formato de 24 horas) "
        "de la computadora del usuario.",
    )
    level = PermissionLevel.NORMAL

    def __init__(self, now: Callable[[], datetime] = datetime.now) -> None:
        self._now = now

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return "decir la fecha y la hora"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        now = self._now()
        day, month = _DAYS[now.weekday()], _MONTHS[now.month - 1]
        return f"{day} {now.day} de {month} de {now.year}, {now:%H:%M}"
