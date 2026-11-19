import asyncio
import logging

import numpy as np
import pytest

from kronos_engine.voice.fallback import FallbackStt, FallbackTts, Outage
from kronos_engine.voice.speaker import Speech

AUDIO = np.zeros(1600, dtype=np.float32)


class Clock:
    def __init__(self) -> None:
        self.now = 0.0

    def __call__(self) -> float:
        return self.now


class FakeStt:
    def __init__(self, text: str, delay: float = 0, fail_with: Exception | None = None) -> None:
        self._text = text
        self._delay = delay
        self._fail_with = fail_with
        self.calls = 0
        self.preloaded = False

    def preload(self) -> None:
        self.preloaded = True

    async def transcribe(self, audio: np.ndarray) -> str:
        self.calls += 1
        await asyncio.sleep(self._delay)
        if self._fail_with:
            raise self._fail_with
        return self._text


class FakeTts:
    def __init__(self, voice: str, delay: float = 0, fail_with: Exception | None = None) -> None:
        self._voice = voice
        self._delay = delay
        self._fail_with = fail_with
        self.texts: list[str] = []
        self.preloaded = False

    @property
    def voice(self) -> str:
        return self._voice

    def set_voice(self, voice: str) -> None:
        self._voice = voice

    def preload(self) -> None:
        self.preloaded = True

    async def synthesize(self, text: str) -> Speech:
        await asyncio.sleep(self._delay)
        if self._fail_with:
            raise self._fail_with
        self.texts.append(text)
        return Speech(np.zeros(4, dtype=np.float32), 24_000)


def stt_with(cloud: FakeStt, local: FakeStt, outage: Outage | None = None) -> FallbackStt:
    return FallbackStt(cloud, local, outage or Outage(), timeout=0.05)


def test_si_la_nube_responde_a_tiempo_usa_su_texto() -> None:
    cloud, local = FakeStt("hola"), FakeStt("ola")

    assert asyncio.run(stt_with(cloud, local).transcribe(AUDIO)) == "hola"
    assert local.calls == 0


def test_si_la_nube_tarda_demasiado_transcribe_en_la_computadora() -> None:
    cloud, local = FakeStt("hola", delay=1), FakeStt("ola")

    assert asyncio.run(stt_with(cloud, local).transcribe(AUDIO)) == "ola"


def test_si_la_nube_falla_transcribe_en_la_computadora() -> None:
    cloud = FakeStt("hola", fail_with=RuntimeError("No se pudo conectar con ElevenLabs."))
    local = FakeStt("ola")

    assert asyncio.run(stt_with(cloud, local).transcribe(AUDIO)) == "ola"


def test_despues_de_un_fallo_no_espera_a_la_nube_por_un_rato() -> None:
    clock = Clock()
    outage = Outage(pause=60, clock=clock)
    cloud, local = FakeStt("hola", fail_with=RuntimeError("sin internet")), FakeStt("ola")
    stt = stt_with(cloud, local, outage)

    asyncio.run(stt.transcribe(AUDIO))
    clock.now = 59
    asyncio.run(stt.transcribe(AUDIO))

    assert cloud.calls == 1
    assert local.calls == 2


def test_pasado_el_rato_vuelve_a_probar_la_nube() -> None:
    clock = Clock()
    outage = Outage(pause=60, clock=clock)
    cloud, local = FakeStt("hola", fail_with=RuntimeError("sin internet")), FakeStt("ola")
    stt = stt_with(cloud, local, outage)

    asyncio.run(stt.transcribe(AUDIO))
    clock.now = 61
    asyncio.run(stt.transcribe(AUDIO))

    assert cloud.calls == 2


def test_avisa_en_el_registro_cuando_falla_y_cuando_vuelve(
    caplog: pytest.LogCaptureFixture,
) -> None:
    clock = Clock()
    outage = Outage(pause=60, clock=clock)
    failing = FakeStt("hola", fail_with=RuntimeError("sin internet"))
    caplog.set_level(logging.INFO)

    asyncio.run(stt_with(failing, FakeStt("ola"), outage).transcribe(AUDIO))
    clock.now = 61
    asyncio.run(stt_with(FakeStt("hola"), FakeStt("ola"), outage).transcribe(AUDIO))

    assert "sin internet" in caplog.text
    assert "60 s" in caplog.text
    assert "volvió a responder" in caplog.text


def test_un_rechazo_de_clave_tambien_pasa_a_la_computadora() -> None:
    cloud = FakeStt("hola", fail_with=RuntimeError("ElevenLabs rechazó la clave."))

    assert asyncio.run(stt_with(cloud, FakeStt("ola")).transcribe(AUDIO)) == "ola"


def test_si_tambien_falla_la_computadora_el_error_sale() -> None:
    cloud = FakeStt("hola", fail_with=RuntimeError("sin internet"))
    local = FakeStt("ola", fail_with=RuntimeError("sin modelo"))

    with pytest.raises(RuntimeError, match="sin modelo"):
        asyncio.run(stt_with(cloud, local).transcribe(AUDIO))


def test_prepara_los_dos_reconocedores() -> None:
    cloud, local = FakeStt("hola"), FakeStt("ola")

    stt_with(cloud, local).preload()

    assert cloud.preloaded
    assert local.preloaded


def tts_with(cloud: FakeTts, local: FakeTts, outage: Outage | None = None) -> FallbackTts:
    return FallbackTts(cloud, local, outage or Outage(), timeout=0.05)


def test_habla_con_la_nube_si_responde_a_tiempo() -> None:
    cloud, local = FakeTts("elevenlabs:abc"), FakeTts("es_AR-daniela-high")

    asyncio.run(tts_with(cloud, local).synthesize("Hola."))

    assert cloud.texts == ["Hola."]
    assert local.texts == []


def test_si_la_nube_tarda_esa_frase_la_dice_piper() -> None:
    cloud, local = FakeTts("elevenlabs:abc", delay=1), FakeTts("es_AR-daniela-high")

    asyncio.run(tts_with(cloud, local).synthesize("Hola."))

    assert local.texts == ["Hola."]


def test_la_voz_es_siempre_la_elegida_aunque_hable_piper() -> None:
    cloud = FakeTts("elevenlabs:abc", fail_with=RuntimeError("sin internet"))
    tts = tts_with(cloud, FakeTts("es_AR-daniela-high"))

    asyncio.run(tts.synthesize("Hola."))
    tts.set_voice("elevenlabs:xyz")

    assert tts.voice == "elevenlabs:xyz"


def test_un_fallo_al_transcribir_tambien_pasa_la_voz_a_piper() -> None:
    outage = Outage()
    asyncio.run(
        stt_with(
            FakeStt("hola", fail_with=RuntimeError("sin internet")), FakeStt("ola"), outage
        ).transcribe(AUDIO)
    )
    cloud, local = FakeTts("elevenlabs:abc"), FakeTts("es_AR-daniela-high")

    asyncio.run(tts_with(cloud, local, outage).synthesize("Hola."))

    assert cloud.texts == []
    assert local.texts == ["Hola."]


def test_prepara_las_dos_voces() -> None:
    cloud, local = FakeTts("elevenlabs:abc"), FakeTts("es_AR-daniela-high")

    tts_with(cloud, local).preload()

    assert cloud.preloaded
    assert local.preloaded
