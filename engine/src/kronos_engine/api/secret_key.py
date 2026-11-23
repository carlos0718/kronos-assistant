"""Rutas para poner, cambiar y borrar la clave secreta del nivel crítico.

La clave llega por acá y no vuelve: la respuesta solo dice si hay una y si el
nivel crítico está bloqueado.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from kronos_engine.core.secret import SecretKeyControl, SecretKeyError


class SecretKeyStatus(BaseModel):
    is_set: bool
    # Segundos que faltan para poder volver a intentar; 0 si no está bloqueado.
    locked_for: int


class NewSecretKey(BaseModel):
    new: str
    # Obligatoria para cambiar una clave que ya existe; la primera no la necesita.
    current: str | None = None


class CurrentSecretKey(BaseModel):
    current: str


def secret_key_router(key: SecretKeyControl, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/secret-key", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> SecretKeyStatus:
        return SecretKeyStatus(is_set=key.is_set(), locked_for=key.locked_for())

    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    def write(body: NewSecretKey) -> None:
        try:
            if key.is_set():
                key.change(body.current or "", body.new)
            else:
                key.set(body.new)
        except SecretKeyError as exc:
            # El texto es para el usuario: la pantalla lo muestra tal cual.
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    @router.post("/remove", status_code=status.HTTP_204_NO_CONTENT)
    def remove(body: CurrentSecretKey) -> None:
        try:
            key.remove(body.current)
        except SecretKeyError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    return router
