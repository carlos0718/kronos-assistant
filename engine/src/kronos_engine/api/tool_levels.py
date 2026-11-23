"""Rutas para ver y cambiar el nivel de permiso de cada acción."""

from collections.abc import Callable

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from kronos_engine.core.tool_levels import ToolLevelError, ToolLevelsControl


class ActionLevelView(BaseModel):
    name: str
    label: str
    factory: int
    level: int
    lowest: int
    fixed: bool


class LevelChoice(BaseModel):
    # `strict` rechaza 2.5 o "2" en lugar de redondearlos.
    level: int = Field(strict=True)
    # La clave secreta, que hace falta para bajar algo del nivel 3. No vuelve en ninguna respuesta.
    secret: str | None = None


def tool_levels_router(levels: ToolLevelsControl, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/tool-levels", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> list[ActionLevelView]:
        return [
            ActionLevelView(
                name=action.name,
                label=action.label,
                factory=action.factory.value,
                level=action.level.value,
                lowest=action.lowest.value,
                fixed=action.fixed,
            )
            for action in levels.actions()
        ]

    @router.put("/{name}", status_code=status.HTTP_204_NO_CONTENT)
    def write(name: str, choice: LevelChoice) -> None:
        try:
            levels.set_level(name, choice.level, choice.secret)
        except ToolLevelError as exc:
            # El texto es para el usuario: la pantalla lo muestra tal cual.
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    return router
