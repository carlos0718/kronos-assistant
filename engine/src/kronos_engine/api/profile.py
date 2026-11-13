"""Rutas para ver y cambiar el perfil del usuario desde la configuración."""

from collections.abc import Callable
from dataclasses import asdict

from fastapi import APIRouter, Depends, status
from pydantic import BaseModel, Field

from kronos_engine.core.profile import Profile, ProfileControl

NAME_MAX = 60
# Cada conversación lleva la descripción entera al modelo: se mantiene corta.
ABOUT_MAX = 500


class ProfileBody(BaseModel):
    name: str = Field(max_length=NAME_MAX)
    about: str = Field(max_length=ABOUT_MAX)


def profile_router(profile: ProfileControl, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/profile", dependencies=[Depends(require_token)])

    @router.get("")
    def read() -> dict[str, str]:
        return asdict(profile.get())

    @router.put("", status_code=status.HTTP_204_NO_CONTENT)
    def write(body: ProfileBody) -> None:
        profile.set(Profile(name=body.name.strip(), about=body.about.strip()))

    return router
