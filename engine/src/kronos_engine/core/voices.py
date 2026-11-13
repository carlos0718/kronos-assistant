"""Interfaz para elegir la voz con la que habla Kronos.

La implementa `voice/`; el servidor solo conoce esta interfaz.
"""

from dataclasses import dataclass
from typing import Literal, Protocol


@dataclass(frozen=True)
class VoiceInfo:
    id: str
    name: str
    language: Literal["es", "en"]
    region: str
    gender: Literal["female", "male"]


class UnknownVoiceError(ValueError):
    """Se pidió una voz que no está en el catálogo."""


class VoiceControl(Protocol):
    def available(self) -> list[VoiceInfo]:
        """Las voces que se pueden elegir."""
        ...

    def current(self) -> str:
        """El `id` de la voz en uso."""
        ...

    async def select(self, voice_id: str) -> None:
        """Cambia la voz en uso y recuerda la elección."""
        ...

    async def preview(self, voice_id: str) -> None:
        """Dice una frase de muestra con esa voz, sin cambiar la voz en uso."""
        ...
