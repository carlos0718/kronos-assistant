"""Piezas simuladas, para probar la interfaz sin micrófono ni modelo.

PROVISORIO: la Fase 1 las reemplaza una por una por las reales.
"""

import asyncio
from collections.abc import AsyncIterator

from kronos_engine.core.conversation import Pipeline

DEMO_TRANSCRIPT = "Kronos, ¿estás ahí?"
DEMO_REPLY = "Aquí estoy. Todavía no escucho de verdad: esto es una demostración."


class DemoListener:
    def __init__(self, step_seconds: float) -> None:
        self._step = step_seconds

    async def listen(self) -> str:
        await asyncio.sleep(self._step)
        return DEMO_TRANSCRIPT


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


def demo_pipeline(step_seconds: float = 2.0) -> Pipeline:
    return Pipeline(
        listener=DemoListener(step_seconds),
        responder=DemoResponder(step_seconds),
        speaker=DemoSpeaker(step_seconds),
    )
