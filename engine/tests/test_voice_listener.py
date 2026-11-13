import asyncio
import contextlib
from collections.abc import AsyncIterator

import numpy as np

from kronos_engine.voice import FRAME_SAMPLES
from kronos_engine.voice.endpointing import EndpointConfig
from kronos_engine.voice.listener import VoiceListener

CONFIG = EndpointConfig(
    frame_ms=100,
    min_speech_ms=200,
    end_silence_ms=200,
    start_timeout_ms=500,
    pre_roll_ms=100,
)

VOICE = 0.9
SILENCE = 0.05


def frame(mark: float) -> np.ndarray:
    """Un cuadro reconocible: todas sus muestras valen `mark`."""
    return np.full(FRAME_SAMPLES, mark, dtype=np.float32)


class FakeMicrophone:
    def __init__(self, count: int) -> None:
        self._count = count
        self.is_open = False
        self.read = 0

    @contextlib.asynccontextmanager
    async def open(self) -> AsyncIterator[AsyncIterator[np.ndarray]]:
        async def frames() -> AsyncIterator[np.ndarray]:
            for index in range(self._count):
                self.read += 1
                yield frame(float(index))

        self.is_open = True
        try:
            yield frames()
        finally:
            self.is_open = False


class FakeVad:
    """Devuelve las probabilidades que se le indican, una por cuadro."""

    def __init__(self, probabilities: list[float]) -> None:
        self._probabilities = probabilities
        self.resets = 0
        self._next = 0

    def reset(self) -> None:
        self.resets += 1

    def probability(self, _frame: np.ndarray) -> float:
        value = self._probabilities[self._next]
        self._next += 1
        return value


class FakeStt:
    def __init__(self, microphone: FakeMicrophone) -> None:
        self._microphone = microphone
        self.audios: list[np.ndarray] = []
        self.microphone_was_open: bool | None = None

    async def transcribe(self, audio: np.ndarray) -> str:
        self.microphone_was_open = self._microphone.is_open
        self.audios.append(audio)
        return "prendé la luz"


def build(probabilities: list[float]) -> tuple[VoiceListener, FakeMicrophone, FakeVad, FakeStt]:
    microphone = FakeMicrophone(len(probabilities))
    vad = FakeVad(probabilities)
    stt = FakeStt(microphone)
    return VoiceListener(microphone.open, vad, stt, CONFIG), microphone, vad, stt


def test_transcribe_la_frase_con_su_margen_previo() -> None:
    # El último cuadro (el 6) no se llega a leer.
    listener, microphone, vad, stt = build(
        [SILENCE, SILENCE, VOICE, VOICE, SILENCE, SILENCE, VOICE]
    )

    assert asyncio.run(listener.listen()) == "prendé la luz"

    # La voz empezó en el cuadro 2; con 100 ms de margen el audio arranca en el 1.
    marks = stt.audios[0].reshape(-1, FRAME_SAMPLES)[:, 0].tolist()
    assert marks == [1.0, 2.0, 3.0, 4.0, 5.0]
    assert microphone.read == 6  # Dejó de leer apenas terminó la frase.
    assert vad.resets == 1


def test_cierra_el_microfono_antes_de_transcribir() -> None:
    listener, microphone, _, stt = build([VOICE, VOICE, SILENCE, SILENCE])

    asyncio.run(listener.listen())

    assert stt.microphone_was_open is False
    assert microphone.is_open is False


def test_avisa_cuando_termina_de_escuchar() -> None:
    async def scenario() -> list[str]:
        listener, microphone, _, _ = build([VOICE, VOICE, SILENCE, SILENCE])
        log: list[str] = []

        async def on_speech_end() -> None:
            log.append(f"fin de voz, micrófono abierto: {microphone.is_open}")

        log.append(str(await listener.listen(on_speech_end)))
        return log

    assert asyncio.run(scenario()) == ["fin de voz, micrófono abierto: False", "prendé la luz"]


def test_si_nadie_habla_devuelve_none_sin_transcribir() -> None:
    listener, microphone, _, stt = build([SILENCE] * 8)

    assert asyncio.run(listener.listen()) is None
    assert stt.audios == []
    assert microphone.is_open is False
