"""Interfaz de las acciones que Kronos puede ejecutar.

Cada acción se implementa en `tools/`. El modelo solo la propone: si se
ejecuta lo decide `permissions/`, que es código y no modelo.
"""

from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from enum import IntEnum
from types import MappingProxyType
from typing import Any, Protocol

# Esquema (JSON Schema) de una acción que no recibe datos.
NO_PARAMETERS: Mapping[str, Any] = MappingProxyType({"type": "object", "properties": {}})


class PermissionLevel(IntEnum):
    """Qué se exige antes de ejecutar una acción (ver «Autonomía» en el README)."""

    NORMAL = 1  # Nada.
    SENSITIVE = 2  # Confirmación por voz o con un clic.
    CRITICAL = 3  # La clave secreta.
    FORBIDDEN = 4  # No se ejecuta nunca.


@dataclass(frozen=True)
class ToolSpec:
    """Lo que el modelo sabe de una acción: cómo se llama, qué hace y qué datos pide."""

    name: str
    description: str
    parameters: Mapping[str, Any] = NO_PARAMETERS


@dataclass(frozen=True)
class ToolCall:
    """Una acción que el modelo pide ejecutar."""

    name: str
    arguments: Mapping[str, Any] = field(default_factory=dict)
    # Con qué id lo pidió el modelo, si el proveedor usa ids (Claude los usa
    # para emparejar cada acción con su resultado).
    id: str = ""


class ToolError(RuntimeError):
    """La acción no se pudo hacer. El mensaje lo recibe el modelo, que se lo cuenta al usuario."""


class Tool(Protocol):
    @property
    def spec(self) -> ToolSpec: ...

    @property
    def level(self) -> PermissionLevel:
        """El nivel de permiso de fábrica."""
        ...

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        """Qué haría con esos datos, en infinitivo: «cerrar Spotify».

        Es lo que ve y oye el usuario cuando se le pide que apruebe la acción.
        Si ya se sabe que no se puede hacer, lanza `ToolError`: no tiene
        sentido pedir permiso para algo imposible.
        """
        ...

    async def run(self, arguments: Mapping[str, Any]) -> str:
        """Ejecuta la acción y devuelve el resultado, en texto para el modelo."""
        ...


class Toolbox(Protocol):
    """Lo que el agente ve de las acciones: cuáles hay y cómo pedir una."""

    def specs(self) -> Sequence[ToolSpec]: ...

    async def run(self, call: ToolCall) -> str:
        """Devuelve el resultado, o el motivo por el que la acción no se ejecutó."""
        ...
