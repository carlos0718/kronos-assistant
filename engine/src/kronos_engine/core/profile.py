"""Interfaz del perfil del usuario: cómo se llama y qué cuenta de sí mismo.

La implementa `config/`; el servidor solo conoce esta interfaz.
"""

from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class Profile:
    name: str = ""
    about: str = ""


class ProfileControl(Protocol):
    def get(self) -> Profile:
        """El perfil guardado; con textos vacíos si el usuario no cargó nada."""
        ...

    def set(self, profile: Profile) -> None:
        """Guarda el perfil. Se usa desde la próxima respuesta de Kronos."""
        ...
