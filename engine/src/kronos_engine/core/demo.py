"""Piezas simuladas, para probar la interfaz sin micrófono ni modelo.

PROVISORIO: la Fase 1 las reemplaza una por una por las reales.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from kronos_engine.core.conversation import Pipeline
from kronos_engine.core.voices import UnknownVoiceError, VoiceInfo

DEMO_TRANSCRIPT = "Kronos, ¿estás ahí?"
DEMO_REPLY = "Aquí estoy. Todavía no escucho de verdad: esto es una demostración."


class DemoListener:
    """Oye una frase y, en la escucha siguiente, silencio: así la demo termina."""

    def __init__(self, step_seconds: float) -> None:
        self._step = step_seconds
        self._heard = False

    async def listen(
        self, on_speech_end: Callable[[], Awaitable[None]] | None = None
    ) -> str | None:
        await asyncio.sleep(self._step)
        self._heard = not self._heard
        return DEMO_TRANSCRIPT if self._heard else None


class DemoResponder:
    def __init__(self, step_seconds: float) -> None:
        self._step = step_seconds

    async def respond(self, text: str) -> AsyncIterator[str]:
        await asyncio.sleep(self._step)
        yield DEMO_REPLY


class DemoSpeaker:
    def __init__(self, step_seconds: float) -> None:
        self._step = step_seconds

    async def speak(self, sentences: AsyncIterator[str]) -> None:
        async for _ in sentences:
            await asyncio.sleep(self._step)


class DemoWakeWord:
    """Nunca oye su nombre: el interruptor se puede usar, pero no activa nada."""

    async def wait(self) -> str:
        await asyncio.Event().wait()
        return ""


class DemoVoices:
    """Dos voces de mentira: se pueden elegir, pero no suenan."""

    VOICES = (
        VoiceInfo("demo-ana", "Ana", "es", "Demo", "female"),
        VoiceInfo("demo-luis", "Luis", "es", "Demo", "male"),
    )

    def __init__(self) -> None:
        self._current = self.VOICES[0].id
        self.previewed: list[str] = []

    def available(self) -> list[VoiceInfo]:
        return list(self.VOICES)

    def current(self) -> str:
        return self._current

    async def select(self, voice_id: str) -> None:
        self._check(voice_id)
        self._current = voice_id

    async def preview(self, voice_id: str) -> None:
        self._check(voice_id)
        self.previewed.append(voice_id)

    def _check(self, voice_id: str) -> None:
        if voice_id not in {voice.id for voice in self.VOICES}:
            raise UnknownVoiceError(f"No existe la voz {voice_id}.")


def demo_pipeline(step_seconds: float = 2.0) -> Pipeline:
    return Pipeline(
        listener=DemoListener(step_seconds),
        responder=DemoResponder(step_seconds),
        speaker=DemoSpeaker(step_seconds),
    )
