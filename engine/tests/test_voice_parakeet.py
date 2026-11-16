import asyncio

import numpy as np

from kronos_engine.voice.parakeet import ParakeetStt, Recognize

AUDIO = np.zeros(1600, dtype=np.float32)


class FakeModel:
    """Un modelo que anota cuántas veces se cargó y qué audio recibió."""

    def __init__(self, text: str = "hola") -> None:
        self.text = text
        self.loads = 0
        self.heard: list[np.ndarray] = []

    def load(self) -> Recognize:
        self.loads += 1
        return self.recognize

    def recognize(self, audio: np.ndarray) -> str:
        self.heard.append(audio)
        return self.text


def test_devuelve_el_texto_que_reconoce_el_modelo() -> None:
    model = FakeModel(" ¿Qué hora es? ")
    stt = ParakeetStt(model.load)

    text = asyncio.run(stt.transcribe(AUDIO))

    assert text == "¿Qué hora es?"
    assert model.heard[0] is AUDIO


def test_le_pasa_al_modelo_el_audio_en_coma_flotante_de_32_bits() -> None:
    model = FakeModel()
    stt = ParakeetStt(model.load)

    asyncio.run(stt.transcribe(AUDIO.astype(np.float64)))

    assert model.heard[0].dtype == np.float32


def test_carga_el_modelo_una_sola_vez() -> None:
    model = FakeModel()
    stt = ParakeetStt(model.load)

    async def twice() -> None:
        await asyncio.gather(stt.transcribe(AUDIO), stt.transcribe(AUDIO))

    asyncio.run(twice())

    assert model.loads == 1
    assert len(model.heard) == 2


def test_no_carga_el_modelo_hasta_que_hace_falta() -> None:
    model = FakeModel()

    ParakeetStt(model.load)

    assert model.loads == 0
