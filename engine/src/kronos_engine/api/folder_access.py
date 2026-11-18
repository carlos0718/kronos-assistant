"""Rutas para ver y cambiar las carpetas que Kronos puede mirar."""

from collections.abc import Callable
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field

from kronos_engine.core.folder_access import (
    MAX_DEPTH,
    MIN_DEPTH,
    FolderAccess,
    FolderAccessControl,
    FolderAccessError,
)
from kronos_engine.core.platform import Folder


class FolderAccessChoice(BaseModel):
    known: list[Folder]
    extra: list[str]
    # `strict` rechaza 2.5 o "2" en lugar de redondearlos.
    depth: int = Field(ge=MIN_DEPTH, le=MAX_DEPTH, strict=True)


def folder_access_router(
    access: FolderAccessControl, require_token: Callable[..., None]
) -> APIRouter:
    router = APIRouter(prefix="/folder-access", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> FolderAccessChoice:
        current = access.get()
        return FolderAccessChoice(
            known=[folder for folder in Folder if folder in current.known],
            extra=[str(path) for path in current.extra],
            depth=current.depth,
        )

    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    def write(choice: FolderAccessChoice) -> None:
        chosen = FolderAccess(
            frozenset(choice.known), tuple(Path(path) for path in choice.extra), choice.depth
        )
        try:
            access.set(chosen)
        except FolderAccessError as exc:
            # El texto es para el usuario: la pantalla lo muestra tal cual.
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(exc)) from exc

    return router
