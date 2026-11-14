"""Interfaz de la espera después de responder: cuánto sigue escuchando Kronos.

La implementa `config/`; el servidor solo conoce esta interfaz.
"""

from typing import Protocol

DEFAULT_SECONDS = 8
# Tope de la espera: el micrófono no queda abierto más que esto sin que nadie hable.
MAX_SECONDS = 60


class FollowUpControl(Protocol):
    def get(self) -> int:
        """Segundos que Kronos espera otra frase después de responder.

        Con cero no sigue escuchando: la conversación termina con la respuesta.
        """
        ...

    def set(self, seconds: int) -> None:
        """Guarda la espera. Se usa desde la próxima respuesta de Kronos."""
        ...
