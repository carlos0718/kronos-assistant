"""Rutas para encender y apagar la palabra de activación desde la configuración."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel

from kronos_engine.core.standby import Standby


class WakeWordChoice(BaseModel):
    enabled: bool


def wake_router(standby: Standby, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/wake-word", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> WakeWordChoice:
        return WakeWordChoice(enabled=standby.enabled)

    # Es `async` para correr en el bucle del servidor: encenderla lanza una tarea.
    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    async def write(choice: WakeWordChoice) -> None:
        standby.set_enabled(choice.enabled)

    return router
