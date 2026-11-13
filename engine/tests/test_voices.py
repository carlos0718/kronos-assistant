import asyncio

import numpy as np
import pytest

from kronos_engine.core.voices import UnknownVoiceError
from kronos_engine.voice.catalog import DEFAULT_VOICES, SAMPLES, VOICES
from kronos_engine.voice.speaker import Speech
from kronos_engine.voice.voices import PiperVoices

DANIELA = "es_AR-daniela-high"
DAVE = "es_ES-davefx-medium"
RYAN = "en_US-ryan-medium"


class FakeTts:
    created: list[str]

    def __init__(self, voice: str) -> None:
        self.voice = voice
        self.said: list[str] = []

    def set_voice(self, voice: str) -> None:
        self.voice = voice

    async def synthesize(self, text: str) -> Speech:
        self.said.append(text)
        return Speech(np.zeros(4, dtype=np.float32), 22_050)


class Setup:
    def __init__(self) -> None:
        self.tts = FakeTts(DANIELA)
        self.previews: list[FakeTts] = []
        self.played = 0
        self.remembered: list[str] = []
        self.voices = PiperVoices(self.tts, self._make, self._play, self.remembered.append)

    def _make(self, voice: str) -> FakeTts:
        self.previews.append(FakeTts(voice))
        return self.previews[-1]

    async def _play(self, samples: np.ndarray, sample_rate: int) -> None:
        self.played += 1


def test_el_catalogo_ofrece_voz_de_mujer_y_de_hombre_en_cada_idioma() -> None:
    offered = {(voice.language, voice.gender) for voice in VOICES}
    assert offered == {("es", "female"), ("es", "male"), ("en", "female"), ("en", "male")}
    assert len({voice.id for voice in VOICES}) == len(VOICES)
    assert set(DEFAULT_VOICES.values()) <= {voice.id for voice in VOICES}


def test_elegir_una_voz_la_pone_en_uso_y_la_recuerda() -> None:
    setup = Setup()

    asyncio.run(setup.voices.select(DAVE))

    assert setup.voices.current() == DAVE
    assert setup.tts.voice == DAVE
    assert setup.remembered == [DAVE]


def test_no_se_puede_elegir_una_voz_que_no_existe() -> None:
    setup = Setup()

    with pytest.raises(UnknownVoiceError):
        asyncio.run(setup.voices.select("es_XX-nadie-medium"))

    assert setup.voices.current() == DANIELA
    assert setup.remembered == []


def test_probar_una_voz_dice_la_muestra_sin_cambiar_la_voz_en_uso() -> None:
    setup = Setup()

    asyncio.run(setup.voices.preview(RYAN))

    assert [(tts.voice, tts.said) for tts in setup.previews] == [(RYAN, [SAMPLES["en"]])]
    assert setup.played == 1
    assert setup.voices.current() == DANIELA
    assert setup.tts.said == []
    assert setup.remembered == []


def test_probar_la_voz_en_uso_no_carga_otra_copia() -> None:
    setup = Setup()

    asyncio.run(setup.voices.preview(DANIELA))

    assert setup.previews == []
    assert setup.tts.said == [SAMPLES["es"]]


def test_volver_a_probar_la_misma_voz_reutiliza_la_que_ya_cargo() -> None:
    setup = Setup()

    async def scenario() -> None:
        await setup.voices.preview(DAVE)
        await setup.voices.preview(DAVE)
        await setup.voices.preview(RYAN)

    asyncio.run(scenario())

    assert [tts.voice for tts in setup.previews] == [DAVE, RYAN]


def test_no_se_puede_probar_una_voz_que_no_existe() -> None:
    with pytest.raises(UnknownVoiceError):
        asyncio.run(Setup().voices.preview("es_XX-nadie-medium"))
