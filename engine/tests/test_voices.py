import asyncio

import numpy as np
import pytest

from kronos_engine.core.voices import UnknownVoiceError, VoiceInfo
from kronos_engine.voice.catalog import DEFAULT_VOICES, SAMPLES, VOICES
from kronos_engine.voice.speaker import Speech
from kronos_engine.voice.voices import RoutedTts, SelectableVoices

DANIELA = "es_AR-daniela-high"
DAVE = "es_ES-davefx-medium"
RYAN = "en_US-ryan-medium"
VALENTINA = "elevenlabs:abc"
CLOUD = [VoiceInfo(VALENTINA, "Valentina", "es", "Argentine", "female", "elevenlabs")]


class FakeTts:
    def __init__(self, voice: str) -> None:
        self.voice = voice
        self.said: list[str] = []
        self.preloaded = 0

    def set_voice(self, voice: str) -> None:
        self.voice = voice

    def preload(self) -> None:
        self.preloaded += 1

    async def synthesize(self, text: str) -> Speech:
        self.said.append(text)
        return Speech(np.zeros(4, dtype=np.float32), 22_050)


class Setup:
    def __init__(self, cloud: list[VoiceInfo] | None = None) -> None:
        self.tts = FakeTts(DANIELA)
        self.previews: list[FakeTts] = []
        self.played = 0
        self.remembered: list[str] = []
        self.voices = SelectableVoices(
            self.tts,
            self._make,
            self._play,
            self.remembered.append,
            catalog=lambda: [*VOICES, *(cloud or [])],
        )

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


def test_ofrece_tambien_las_voces_de_la_nube() -> None:
    setup = Setup(cloud=CLOUD)

    assert setup.voices.available()[-1] == CLOUD[0]

    asyncio.run(setup.voices.select(VALENTINA))

    assert setup.voices.current() == VALENTINA
    assert setup.remembered == [VALENTINA]


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


# RoutedTts: una sola voz en uso, de Piper o de ElevenLabs.


class Factory:
    def __init__(self) -> None:
        self.made: list[FakeTts] = []

    def __call__(self, voice: str) -> FakeTts:
        self.made.append(FakeTts(voice))
        return self.made[-1]


def test_habla_con_la_voz_con_que_arranca() -> None:
    make = Factory()
    tts = RoutedTts(DANIELA, make)

    asyncio.run(tts.synthesize("Hola."))

    assert tts.voice == DANIELA
    assert [(made.voice, made.said) for made in make.made] == [(DANIELA, ["Hola."])]


def test_otra_voz_del_mismo_proveedor_reusa_el_que_tiene() -> None:
    make = Factory()
    tts = RoutedTts(DANIELA, make)

    tts.set_voice(DAVE)

    assert tts.voice == DAVE
    assert [made.voice for made in make.made] == [DAVE]


def test_pasar_a_otro_proveedor_crea_uno_nuevo_y_lo_prepara() -> None:
    make = Factory()
    tts = RoutedTts(DANIELA, make)

    tts.set_voice(VALENTINA)
    asyncio.run(tts.synthesize("Hola."))

    assert tts.voice == VALENTINA
    assert [made.voice for made in make.made] == [DANIELA, VALENTINA]
    assert make.made[1].preloaded == 1
    assert make.made[1].said == ["Hola."]
    assert make.made[0].said == []


def test_preparar_prepara_la_voz_en_uso() -> None:
    make = Factory()
    tts = RoutedTts(DANIELA, make)

    tts.preload()

    assert make.made[0].preloaded == 1
