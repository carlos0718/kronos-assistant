import asyncio
import contextlib
from collections.abc import AsyncIterator

import numpy as np
import pytest

from kronos_engine.voice import FRAME_SAMPLES
from kronos_engine.voice.endpointing import EndpointConfig
from kronos_engine.voice.wake import WhisperWakeWord, after_wake_word

CONFIG = EndpointConfig(
    frame_ms=100,
    min_speech_ms=200,
    end_silence_ms=200,
    start_timeout_ms=1000,
    pre_roll_ms=100,
)

VOICE = 0.9
SILENCE = 0.05
# Una frase y el silencio que la cierra.
PHRASE = [VOICE, VOICE, SILENCE, SILENCE]


@pytest.mark.parametrize(
    ("text", "expected"),
    [
        ("Kronos", ""),
        ("Kronos.", ""),
        ("¡Kronos!", ""),
        ("Hola, Kronos", ""),
        ("Kronos, ¿qué hora es?", "¿qué hora es?"),
        ("Oye Kronos, poné música.", "poné música."),
        # Whisper lo escribe de varias maneras.
        ("cronos qué hora es", "qué hora es"),
        ("Chronos, abrí el navegador", "abrí el navegador"),
        ("Cronós: ¿estás ahí?", "¿estás ahí?"),
        # El pedido puede venir antes del nombre.
        ("¿Qué hora es, Kronos?", "¿Qué hora es?"),
    ],
)
def test_reconoce_el_nombre_y_devuelve_el_pedido(text: str, expected: str) -> None:
    assert after_wake_word(text) == expected


@pytest.mark.parametrize(
    "text",
    ["", "¿Qué hora es?", "El cronómetro está en cero", "Me compré unos tronos", "macronos"],
)
def test_sin_el_nombre_no_se_activa(text: str) -> None:
    assert after_wake_word(text) is None


class FakeMicrophone:
    """Entrega un cuadro por probabilidad; después queda mudo para siempre."""

    def __init__(self, count: int) -> None:
        self._count = count
        self.opened = 0
        self.is_open = False

    @contextlib.asynccontextmanager
    async def open(self) -> AsyncIterator[AsyncIterator[np.ndarray]]:
        async def frames() -> AsyncIterator[np.ndarray]:
            for index in range(self._count):
                yield np.full(FRAME_SAMPLES, float(index), dtype=np.float32)
            await asyncio.Event().wait()

        self.opened += 1
        self.is_open = True
        try:
            yield frames()
        finally:
            self.is_open = False


class FakeVad:
    def __init__(self, probabilities: list[float]) -> None:
        self._probabilities = iter(probabilities)
        self.resets = 0

    def reset(self) -> None:
        self.resets += 1

    def probability(self, _frame: np.ndarray) -> float:
        return next(self._probabilities)


class FakeStt:
    def __init__(self, *texts: str) -> None:
        self._texts = list(texts)
        self.audios: list[np.ndarray] = []

    async def transcribe(self, audio: np.ndarray) -> str:
        self.audios.append(audio)
        return self._texts.pop(0)


def build(
    probabilities: list[float], *texts: str
) -> tuple[WhisperWakeWord, FakeMicrophone, FakeStt]:
    microphone = FakeMicrophone(len(probabilities))
    stt = FakeStt(*texts)
    return WhisperWakeWord(microphone.open, FakeVad(probabilities), stt, CONFIG), microphone, stt


def marks(audio: np.ndarray) -> list[float]:
    """Qué cuadros del micrófono forman el audio."""
    return [float(mark) for mark in audio.reshape(-1, FRAME_SAMPLES)[:, 0]]


def test_devuelve_lo_que_se_dijo_despues_del_nombre() -> None:
    wake, microphone, _ = build(PHRASE, "Kronos, ¿qué hora es?")

    assert asyncio.run(wake.wait()) == "¿qué hora es?"
    assert microphone.is_open is False


def test_ignora_lo_que_no_lo_nombra_y_sigue_con_el_microfono_abierto() -> None:
    wake, microphone, stt = build(PHRASE + PHRASE, "pasame la sal", "Kronos")

    assert asyncio.run(wake.wait()) == ""
    assert len(stt.audios) == 2
    assert microphone.opened == 1  # No lo cierra entre una frase y otra.


def test_transcribe_cada_frase_por_separado_con_su_margen_previo() -> None:
    silence = [SILENCE] * 4
    wake, _, stt = build(silence + PHRASE + silence + PHRASE, "otra cosa", "Kronos")

    asyncio.run(wake.wait())

    # La voz empezó en los cuadros 4 y 12; con 100 ms de margen arrancan uno antes.
    assert marks(stt.audios[0]) == [3.0, 4.0, 5.0, 6.0, 7.0]
    assert marks(stt.audios[1]) == [11.0, 12.0, 13.0, 14.0, 15.0]


def test_el_silencio_largo_no_corta_la_espera() -> None:
    # Vence el plazo de `start_timeout_ms` varias veces antes de que alguien hable.
    silence = [SILENCE] * 25
    wake, microphone, stt = build(silence + PHRASE, "Kronos")

    assert asyncio.run(wake.wait()) == ""
    assert marks(stt.audios[0]) == [24.0, 25.0, 26.0, 27.0, 28.0]
    assert microphone.opened == 1


def test_al_cancelar_la_espera_se_cierra_el_microfono() -> None:
    async def scenario() -> bool:
        wake, microphone, _ = build([SILENCE] * 3)
        waiting = asyncio.create_task(wake.wait())
        await asyncio.sleep(0.01)
        assert microphone.is_open is True
        waiting.cancel()
        with contextlib.suppress(asyncio.CancelledError):
            await waiting
        return microphone.is_open

    assert asyncio.run(scenario()) is False
