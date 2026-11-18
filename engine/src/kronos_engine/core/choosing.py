"""Interfaz para elegir, por el significado, cuál de varias opciones es lo que pidió el usuario.

La implementa `agent/` con el modelo. La usan las acciones cuando la búsqueda por
palabras no alcanza: «mi web personal» es la carpeta «Portfolio-master».
"""

from collections.abc import Sequence
from typing import Protocol


class Chooser(Protocol):
    async def choose(self, wanted: str, options: Sequence[str]) -> int | None:
        """La posición en `options` de lo que el usuario llamó `wanted`.

        `None` si ninguna lo es con claridad o no se pudo decidir: en la duda no se elige.
        """
        ...
