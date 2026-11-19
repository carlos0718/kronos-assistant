"""Interfaz de la elección del modelo de lenguaje: cuál responde y con qué clave.

La implementa `config/`; el servidor y el proveedor que cambia de modelo solo
conocen esta interfaz.
"""

from dataclasses import dataclass
from typing import Protocol

OLLAMA = "ollama"
ANTHROPIC = "anthropic"
PROVIDERS = (OLLAMA, ANTHROPIC)

# Los modelos de Claude que se pueden elegir. El primero es el de fábrica.
ANTHROPIC_MODELS = ("claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5")


@dataclass(frozen=True)
class ModelChoice:
    provider: str = OLLAMA
    # Vacío: el modelo de fábrica del proveedor.
    model: str = ""


def checked(choice: ModelChoice) -> ModelChoice:
    """La elección, si es válida. Si no, lanza `ValueError`."""
    if choice.provider not in PROVIDERS:
        raise ValueError(f"Proveedor desconocido: {choice.provider!r}")
    if choice.provider == ANTHROPIC and choice.model and choice.model not in ANTHROPIC_MODELS:
        raise ValueError(f"Modelo de Claude desconocido: {choice.model!r}")
    return choice


class SecretStore(Protocol):
    """Guarda claves fuera de los archivos de configuración."""

    def read(self, name: str) -> str | None: ...

    def write(self, name: str, secret: str) -> None: ...

    def delete(self, name: str) -> None:
        """Borra la clave. Si no estaba, no hace nada."""
        ...


class ModelControl(Protocol):
    def get(self) -> ModelChoice: ...

    def set(self, choice: ModelChoice) -> None:
        """Guarda la elección. Se usa desde la próxima respuesta, sin reiniciar."""
        ...

    def key(self, provider: str) -> str | None:
        """La clave guardada para ese proveedor, o `None`."""
        ...

    def set_key(self, provider: str, key: str) -> None:
        """Guarda la clave; vacía la borra."""
        ...
