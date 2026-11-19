"""Rutas para elegir qué modelo responde y guardar la clave de un modelo en la nube.

La clave entra por acá, pero ninguna ruta la devuelve: solo se informa si hay una.
"""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from kronos_engine.core.model_choice import ANTHROPIC, ANTHROPIC_MODELS, ModelChoice, ModelControl

# Una clave de Anthropic tiene unos cien caracteres.
_MAX_KEY = 1000


class ModelChoiceBody(BaseModel):
    provider: str
    model: str = Field(default="", max_length=100)


class ModelStatus(ModelChoiceBody):
    # Los modelos de Claude que se pueden elegir, el primero es el de fábrica.
    models: list[str]
    has_key: bool


class KeyBody(BaseModel):
    provider: str
    key: str = Field(max_length=_MAX_KEY)


def model_router(model: ModelControl, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/model", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> ModelStatus:
        current = model.get()
        return ModelStatus(
            provider=current.provider,
            model=current.model,
            models=list(ANTHROPIC_MODELS),
            has_key=model.key(ANTHROPIC) is not None,
        )

    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    def write(choice: ModelChoiceBody) -> None:
        try:
            model.set(ModelChoice(choice.provider, choice.model))
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    @router.put("/key", status_code=status.HTTP_204_NO_CONTENT)
    def write_key(body: KeyBody) -> None:
        try:
            model.set_key(body.provider, body.key)
        except ValueError as exc:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc
        except OSError as exc:
            # Windows no dejó guardarla: el mensaje no incluye la clave.
            raise HTTPException(status.HTTP_500_INTERNAL_SERVER_ERROR, str(exc)) from exc

    return router
