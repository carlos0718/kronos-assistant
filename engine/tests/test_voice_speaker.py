import asyncio
from collections.abc import AsyncIterator

import numpy as np
import pytest

from kronos_engine.voice.speaker import Speech, VoiceSpeaker

SAMPLE_RATE = 22_050


async def sentences(*texts: str) -> AsyncIterator[str]:
    for text in texts:
        yield text


class FakeTts:
    def __init__(self, fail_with: Exception | None = None) -> None:
        self._fail_with = fail_with
        self.texts: list[str] = []

    async def synthesize(self, text: str) -> Speech:
        if self._fail_with:
            raise self._fail_with
        self.texts.append(text)
        return Speech(np.full(4, len(self.texts), dtype=np.float32), SAMPLE_RATE)


class FakePlayer:
    def __init__(self, wait: asyncio.Event | None = None) -> None:
        self._wait = wait
        self.played: list[tuple[list[float], int]] = []

    async def __call__(self, samples: np.ndarray, sample_rate: int) -> None:
        if self._wait:
            await self._wait.wait()
        self.played.append((samples.tolist(), sample_rate))


def test_sintetiza_cada_frase_y_las_reproduce_en_orden() -> None:
    tts, player = FakeTts(), FakePlayer()

    asyncio.run(VoiceSpeaker(tts, player).speak(sentences("Son las tres.", "¿Algo más?")))

    assert tts.texts == ["Son las tres.", "¿Algo más?"]
    assert player.played == [
        ([1.0, 1.0, 1.0, 1.0], SAMPLE_RATE),
        ([2.0, 2.0, 2.0, 2.0], SAMPLE_RATE),
    ]


def test_no_dice_los_simbolos_de_formato() -> None:
    tts, player = FakeTts(), FakePlayer()

    asyncio.run(VoiceSpeaker(tts, player).speak(sentences("Es **muy** importante 😊")))

    assert tts.texts == ["Es muy importante"]


def test_saltea_las_frases_sin_nada_para_decir() -> None:
    tts, player = FakeTts(), FakePlayer()

    asyncio.run(VoiceSpeaker(tts, player).speak(sentences("😊", "Hola.")))

    assert tts.texts == ["Hola."]
    assert len(player.played) == 1


def test_prepara_la_frase_siguiente_mientras_suena_la_anterior() -> None:
    # Así no queda un silencio entre frase y frase.
    async def scenario() -> list[str]:
        finished = asyncio.Event()
        tts = FakeTts()
        speaker = VoiceSpeaker(tts, FakePlayer(wait=finished))
        speaking = asyncio.create_task(speaker.speak(sentences("Uno.", "Dos.")))
        await asyncio.sleep(0.01)  # La primera frase todavía está sonando.
        prepared = list(tts.texts)
        finished.set()
        await speaking
        return prepared

    assert asyncio.run(scenario()) == ["Uno.", "Dos."]


def test_vuelve_recien_cuando_termino_de_sonar() -> None:
    async def scenario() -> list[str]:
        finished = asyncio.Event()
        speaker = VoiceSpeaker(FakeTts(), FakePlayer(wait=finished))
        log: list[str] = []
        speaking = asyncio.create_task(speaker.speak(sentences("Hola.")))
        await asyncio.sleep(0.01)
        log.append(f"terminó antes de sonar: {speaking.done()}")
        finished.set()
        await speaking
        log.append(f"terminó después de sonar: {speaking.done()}")
        return log

    assert asyncio.run(scenario()) == [
        "terminó antes de sonar: False",
        "terminó después de sonar: True",
    ]


def test_un_fallo_de_la_voz_se_informa() -> None:
    speaker = VoiceSpeaker(FakeTts(fail_with=RuntimeError("sin voz")), FakePlayer())

    with pytest.raises(RuntimeError, match="sin voz"):
        asyncio.run(speaker.speak(sentences("Hola.")))
