"""Acción: decir la fecha y la hora."""

from collections.abc import Callable, Mapping
from datetime import date, datetime, timedelta
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
        "de la computadora del usuario, y la fecha de mañana.",
    )
    level = PermissionLevel.NORMAL

    def __init__(self, now: Callable[[], datetime] = datetime.now) -> None:
        self._now = now

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return "decir la fecha y la hora"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        now = self._now()
        # Mañana va ya calculada: el modelo erraba la cuenta y repetía el día de hoy.
        tomorrow = (now + timedelta(days=1)).date()
        # Si no se lo pide así, el modelo lee todo aunque solo le pregunten la hora.
        return (
            f"Hora: {now:%H:%M}. Hoy: {_spoken(now.date())}. Mañana: {_spoken(tomorrow)}. "
            "Decí solo lo que te preguntaron."
        )


def _spoken(day: date) -> str:
    """«jueves 19 de noviembre de 2026»."""
    return f"{_DAYS[day.weekday()]} {day.day} de {_MONTHS[day.month - 1]} de {day.year}"
