"""Interfaz de la elección del reconocedor de voz: qué modelo convierte lo que oye en texto.

La implementa `config/`; el servidor y el reconocedor que cambia de modelo solo
conocen esta interfaz.
"""

from typing import Protocol

PARAKEET = "parakeet"
# Whisper en español fijo: más lento (2 s por frase), pero reconoce solo el idioma pedido.
WHISPER = "small"
ELEVENLABS = "elevenlabs"
# Los que se pueden elegir. El primero es el de fábrica.
RECOGNIZERS = (PARAKEET, WHISPER, ELEVENLABS)
DEFAULT_RECOGNIZER = PARAKEET


def checked(name: str) -> str:
    """El nombre, si es de un reconocedor que se puede elegir. Si no, lanza `ValueError`."""
    if name not in RECOGNIZERS:
        raise ValueError(f"Reconocedor desconocido: {name!r}")
    return name


class RecognizerControl(Protocol):
    def get(self) -> str:
        """El reconocedor elegido, aunque ElevenLabs no tenga clave todavía."""
        ...

    def set(self, name: str) -> None:
        """Guarda la elección. Se usa desde la próxima frase, sin reiniciar."""
        ...

    def has_key(self) -> bool:
        """Si hay una clave de ElevenLabs guardada, que es la que necesita ese reconocedor."""
        ...
