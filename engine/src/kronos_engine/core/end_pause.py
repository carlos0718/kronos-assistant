"""Interfaz de la pausa que da por terminada la frase del usuario.

La implementa `config/`; el servidor solo conoce esta interfaz.
"""

from typing import Protocol

# Con menos, Kronos contesta antes pero corta a quien hace una pausa para pensar.
DEFAULT_MS = 1500
# Por debajo de esto corta entre una palabra y la siguiente.
MIN_MS = 500
MAX_MS = 5000


class EndPauseControl(Protocol):
    def get(self) -> int:
        """Milisegundos de silencio que dan por terminada la frase del usuario."""
        ...

    def set(self, milliseconds: int) -> None:
        """Guarda la pausa. Se usa desde la próxima vez que Kronos escucha."""
        ...
