"""Acción: decir la fecha y la hora."""

from collections.abc import Callable, Mapping
from datetime import datetime, timedelta
from typing import Any

from kronos_engine.core.spoken_time import spoken_date, spoken_zone
from kronos_engine.core.tools import PermissionLevel, ToolSpec


class CurrentTimeTool:
    spec = ToolSpec(
        "current_time",
        "Devuelve el día de la semana, la fecha y la hora actuales (formato de 24 horas) "
        "de la computadora del usuario, y la fecha de mañana.",
    )
    level = PermissionLevel.NORMAL

    def __init__(self, now: Callable[[], datetime] = lambda: datetime.now().astimezone()) -> None:
        self._now = now

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return "decir la fecha y la hora"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        now = self._now()
        # Mañana va ya calculada: el modelo erraba la cuenta y repetía el día de hoy.
        tomorrow = (now + timedelta(days=1)).date()
        # Con la zona, Claude puede pasar a esta hora la de un partido en otro país.
        zone = f" ({spoken_zone(now)})" if now.utcoffset() is not None else ""
        # Si no se lo pide así, el modelo lee todo aunque solo le pregunten la hora.
        return (
            f"Hora: {now:%H:%M}{zone}. Hoy: {spoken_date(now.date())}. "
            f"Mañana: {spoken_date(tomorrow)}. Decí solo lo que te preguntaron."
        )
