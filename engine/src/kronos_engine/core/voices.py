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
    region: str  # Vacío si no se sabe.
    gender: Literal["female", "male"] | None  # None si no se sabe.
    # Piper corre en la computadora; ElevenLabs, en la nube y de pago.
    provider: Literal["piper", "elevenlabs"] = "piper"


class UnknownVoiceError(ValueError):
    """Se pidió una voz que no está en el catálogo."""


class CloudKey(Protocol):
    """La clave de ElevenLabs que cargó el usuario."""

    def get(self) -> str:
        """La clave, o "" si no hay."""
        ...

    def set(self, key: str) -> None:
        """Guarda la clave; vacía, la borra."""
        ...


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

    def has_key(self) -> bool:
        """Si hay una clave de ElevenLabs guardada. La clave nunca sale del motor."""
        ...

    async def set_key(self, key: str) -> None:
        """Guarda la clave de ElevenLabs; vacía, la borra.

        Sin clave, si la voz en uso era de ElevenLabs, vuelve a una de la computadora.
        """
        ...
