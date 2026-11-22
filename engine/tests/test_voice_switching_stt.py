import asyncio

import numpy as np

from kronos_engine.core.recognizer import ELEVENLABS, PARAKEET, WHISPER
from kronos_engine.voice.fallback import FallbackStt, Outage
from kronos_engine.voice.parakeet import ParakeetStt
from kronos_engine.voice.stt import WhisperStt
from kronos_engine.voice.switching_stt import SwitchingStt


class Choice:
    def __init__(self, name: str) -> None:
        self.name = name

    def __call__(self) -> str:
        return self.name


def switching(choice: Choice, key: str = "clave") -> SwitchingStt:
    return SwitchingStt(choice, "es", Outage(), lambda: key)


def test_usa_el_reconocedor_elegido() -> None:
    stt = switching(Choice(PARAKEET))

    assert isinstance(stt._current(), ParakeetStt)


def test_cambiar_la_eleccion_se_nota_en_la_proxima_frase() -> None:
    choice = Choice(PARAKEET)
    stt = switching(choice)
    assert isinstance(stt._current(), ParakeetStt)

    choice.name = WHISPER

    assert isinstance(stt._current(), WhisperStt)


def test_elevenlabs_lleva_a_parakeet_de_respaldo() -> None:
    assert isinstance(switching(Choice(ELEVENLABS))._current(), FallbackStt)


def test_elevenlabs_sin_clave_reconoce_parakeet_sin_esperar_a_la_nube() -> None:
    stt = switching(Choice(ELEVENLABS), key="")

    assert isinstance(stt._current(), ParakeetStt)


def test_conserva_cada_reconocedor_en_lugar_de_armarlo_de_nuevo() -> None:
    choice = Choice(PARAKEET)
    stt = switching(choice)
    first = stt._current()

    choice.name = WHISPER
    stt._current()
    choice.name = PARAKEET

    assert stt._current() is first


def test_parakeet_se_comparte_con_el_respaldo_de_elevenlabs() -> None:
    choice = Choice(ELEVENLABS)
    stt = switching(choice)
    stt._current()

    choice.name = PARAKEET
    alone = stt._current()

    assert alone is stt._made[PARAKEET]
    assert len(stt._made) == 2


def test_transcribe_con_el_reconocedor_elegido() -> None:
    class Fixed:
        def preload(self) -> None: ...

        async def transcribe(self, audio: np.ndarray) -> str:
            return "hola"

    stt = switching(Choice(PARAKEET))
    stt._made[PARAKEET] = Fixed()

    assert asyncio.run(stt.transcribe(np.zeros(160, dtype=np.float32))) == "hola"
