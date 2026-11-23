"""Interfaces de la clave secreta del nivel crítico (ver «Autonomía» en el README)."""

from typing import Protocol

# Cuántos caracteres necesita, como mínimo, una clave secreta.
MIN_LENGTH = 8


class SecretKeyError(ValueError):
    """No se pudo guardar, cambiar o borrar la clave. El mensaje se le muestra al usuario."""


class SecretVault(Protocol):
    """Lo que el control de permisos sabe de la clave secreta: solo comprobarla."""

    def is_set(self) -> bool: ...

    def locked_for(self) -> int:
        """Segundos que faltan para poder volver a intentar; 0 si no está bloqueado."""
        ...

    def verify(self, attempt: str) -> bool: ...


class SecretKeyControl(SecretVault, Protocol):
    """Lo que la interfaz puede hacer con la clave: ponerla, cambiarla y borrarla."""

    def set(self, new: str) -> None: ...

    def change(self, current: str, new: str) -> None: ...

    def remove(self, current: str) -> None: ...
