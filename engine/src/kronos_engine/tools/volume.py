"""Acción: el volumen de la computadora."""

import asyncio
from collections.abc import Mapping
from typing import Any

from kronos_engine.core.platform import Volume
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec

# Cuánto sube o baja si el usuario no dice cuánto.
DEFAULT_STEP = 10
# Lo más que sube de golpe: una subida grande sorprende (y asusta) con auriculares.
MAX_JUMP = 30
_ACTIONS = ("set", "up", "down", "mute", "unmute", "get")


def _percent(value: Any, what: str) -> int:
    try:
        return int(value)
    except (TypeError, ValueError):
        raise ToolError(f"Falta {what}: tiene que ser un número de 0 a 100.") from None


class VolumeTool:
    spec = ToolSpec(
        "volume",
        "Cambia o consulta el volumen de la computadora del usuario. Con action «set» lo "
        "pone en un nivel (en level, de 0 a 100); «up» y «down» lo suben o bajan (amount "
        "dice cuánto: 10 si no pidió una cantidad); «mute» y «unmute» lo silencian y "
        "reactivan; «get» dice cómo está.",
        {
            "type": "object",
            "required": ["action"],
            "properties": {
                "action": {"type": "string", "enum": list(_ACTIONS)},
                "level": {
                    "type": "integer",
                    "description": "Solo con «set»: el volumen deseado, de 0 a 100.",
                },
                "amount": {
                    "type": "integer",
                    "description": "Solo con «up» o «down»: cuántos puntos. 10 por defecto.",
                },
            },
        },
    )
    level = PermissionLevel.NORMAL

    def __init__(self, volume: Volume) -> None:
        self._volume = volume

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return "cambiar el volumen"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        # El sistema de audio puede tardar en contestar: no se frena al resto del motor.
        return await asyncio.to_thread(self._apply, arguments)

    def _apply(self, arguments: Mapping[str, Any]) -> str:
        action = str(arguments.get("action") or "")
        volume = self._volume
        match action:
            case "set":
                self._move(_clamp(_percent(arguments.get("level"), "el nivel")))
            case "up" | "down":
                step = abs(_percent(arguments.get("amount", DEFAULT_STEP), "la cantidad"))
                if action == "up":
                    self._move(_clamp(volume.level() + min(step, MAX_JUMP)))
                else:
                    self._move(_clamp(volume.level() - step), unmute=False)
            case "mute":
                volume.set_muted(True)
            case "unmute":
                volume.set_muted(False)
            case "get":
                pass
            case _:
                raise ToolError(
                    f"No existe la acción «{action}». Las que hay: {', '.join(_ACTIONS)}."
                )
        if volume.muted():
            return f"El sonido está silenciado (el volumen está en {volume.level()} %)."
        return f"El volumen está en {volume.level()} %."

    def _move(self, percent: int, unmute: bool = True) -> None:
        self._volume.set_level(percent)
        # Subir el volumen con el sonido silenciado no se oiría: se reactiva.
        if unmute and percent > 0 and self._volume.muted():
            self._volume.set_muted(False)


def _clamp(percent: int) -> int:
    return max(0, min(100, percent))
