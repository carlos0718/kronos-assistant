"""Rutas para elegir y probar la voz desde la pantalla de configuración."""

from collections.abc import Callable
from dataclasses import asdict
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel

from kronos_engine.core.voices import UnknownVoiceError, VoiceControl


class VoiceChoice(BaseModel):
    id: str


def voices_router(voices: VoiceControl, require_token: Callable[..., None]) -> APIRouter:
    router = APIRouter(prefix="/voices", dependencies=[Depends(require_token)])

    @router.get("")
    def list_voices() -> dict[str, Any]:
        return {
            "current": voices.current(),
            "voices": [asdict(voice) for voice in voices.available()],
        }

    @router.put("/current", status_code=status.HTTP_204_NO_CONTENT)
    async def select_voice(choice: VoiceChoice) -> None:
        try:
            await voices.select(choice.id)
        except UnknownVoiceError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc

    @router.post("/{voice_id}/preview", status_code=status.HTTP_204_NO_CONTENT)
    async def preview_voice(voice_id: str) -> None:
        try:
            await voices.preview(voice_id)
        except UnknownVoiceError as exc:
            raise HTTPException(status.HTTP_404_NOT_FOUND, str(exc)) from exc
        except RuntimeError as exc:
            # La voz no se pudo descargar o el altavoz no abrió: el texto es para el usuario.
            raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, str(exc)) from exc

    return router
