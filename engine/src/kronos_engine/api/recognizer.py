"""Rutas para ver y elegir el reconocedor de voz."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from kronos_engine.core.recognizer import RECOGNIZERS, RecognizerControl


class RecognizerChoice(BaseModel):
    model: str


class RecognizerStatus(RecognizerChoice):
    # Los que se pueden elegir; el primero es el de fábrica.
    models: list[str]
    # Si hay una clave de ElevenLabs: sin ella ese reconocedor no se usa.
    has_key: bool


def recognizer_router(
    recognizer: RecognizerControl, require_token: Callable[..., None]
) -> APIRouter:
    router = APIRouter(prefix="/recognizer", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> RecognizerStatus:
        return RecognizerStatus(
            model=recognizer.get(), models=list(RECOGNIZERS), has_key=recognizer.has_key()
        )

    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    def write(choice: RecognizerChoice) -> None:
        try:
            recognizer.set(choice.model)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    return router
