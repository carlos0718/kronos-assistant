"""Rutas para ver y cambiar la pausa que da por terminada la frase del usuario."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from kronos_engine.core.end_pause import MAX_MS, MIN_MS, EndPauseControl


class EndPauseChoice(BaseModel):
    # `strict` rechaza 1500.5 o "1500" en lugar de redondearlos.
    milliseconds: int = Field(ge=MIN_MS, le=MAX_MS, strict=True)


def end_pause_router(end_pause: EndPauseControl, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/end-pause", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> EndPauseChoice:
        return EndPauseChoice(milliseconds=end_pause.get())

    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    def write(choice: EndPauseChoice) -> None:
        end_pause.set(choice.milliseconds)

    return router
