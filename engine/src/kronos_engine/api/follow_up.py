"""Rutas para ver y cambiar cuánto sigue escuchando Kronos después de responder."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from kronos_engine.core.follow_up import MAX_SECONDS, FollowUpControl


class FollowUpChoice(BaseModel):
    # `strict` rechaza 2.5 o "8" en lugar de redondearlos.
    seconds: int = Field(ge=0, le=MAX_SECONDS, strict=True)


def follow_up_router(follow_up: FollowUpControl, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/follow-up", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> FollowUpChoice:
        return FollowUpChoice(seconds=follow_up.get())

    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    def write(choice: FollowUpChoice) -> None:
        follow_up.set(choice.seconds)

    return router
