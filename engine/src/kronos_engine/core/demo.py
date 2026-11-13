"""Piezas simuladas, para probar la interfaz sin micrófono ni modelo.

PROVISORIO: la Fase 1 las reemplaza una por una por las reales.
"""

import asyncio
from collections.abc import AsyncIterator, Awaitable, Callable

from kronos_engine.core.conversation import Pipeline

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

    async def speak(self, text: str) -> None:
        await asyncio.sleep(self._step)


class SilentSpeaker:
    """No dice nada. PROVISORIO: hasta que llegue la voz.

    No espera: así Kronos vuelve a escuchar apenas termina de responder. La
    respuesta queda en pantalla mientras escucha.
    """

    async def speak(self, text: str) -> None:
        return None


def demo_pipeline(step_seconds: float = 2.0) -> Pipeline:
    return Pipeline(
        listener=DemoListener(step_seconds),
        responder=DemoResponder(step_seconds),
        speaker=DemoSpeaker(step_seconds),
    )
