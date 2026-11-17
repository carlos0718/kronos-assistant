import asyncio
import json
from collections.abc import Callable

import httpx
import numpy as np
import pytest

from kronos_engine.core.voices import VoiceInfo
from kronos_engine.voice.elevenlabs import (
    TTS_MODEL,
    ElevenLabsCatalog,
    ElevenLabsError,
    ElevenLabsStt,
    ElevenLabsTts,
    is_elevenlabs_voice,
)

AUDIO = np.array([0.0, 0.5, -0.5, 1.5], dtype=np.float32)


def stt(handler: Callable[[httpx.Request], httpx.Response], **options: str) -> ElevenLabsStt:
    return ElevenLabsStt("clave-de-prueba", transport=httpx.MockTransport(handler), **options)


def transcribe(recognizer: ElevenLabsStt, audio: np.ndarray = AUDIO) -> str:
    return asyncio.run(recognizer.transcribe(audio))


def field(request: httpx.Request, name: str) -> bytes:
    """El valor de un campo del formulario multipart que se mandó."""
    body = request.read()
    start = body.index(f'name="{name}"'.encode())
    value_start = body.index(b"\r\n\r\n", start) + 4
    return body[value_start : body.index(b"\r\n--", value_start)]


def test_devuelve_el_texto_sin_espacios_de_mas() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, json={"text": " Sí, confirmo. ", "language_code": "es"})

    assert transcribe(stt(handler)) == "Sí, confirmo."


def test_manda_el_audio_con_la_clave_el_modelo_y_el_idioma() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"text": "Hola"})

    transcribe(stt(handler, model="scribe_v3", language="es"))

    request = sent[0]
    assert request.method == "POST"
    assert request.url == "https://api.elevenlabs.io/v1/speech-to-text"
    assert request.headers["xi-api-key"] == "clave-de-prueba"
    assert field(request, "model_id") == b"scribe_v3"
    assert field(request, "language_code") == b"es"
    assert field(request, "tag_audio_events") == b"false"
    assert field(request, "file_format") == b"pcm_s16le_16"


def test_manda_el_audio_como_pcm_de_16_bits_recortando_lo_que_se_pasa() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, json={"text": "Hola"})

    transcribe(stt(handler))

    pcm = np.frombuffer(field(sent[0], "file"), dtype="<i2")
    assert pcm.tolist() == [0, 16383, -16383, 32767]


def test_una_clave_rechazada_dice_que_variable_revisar() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"detail": {"message": "Invalid API key"}})

    with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
        transcribe(stt(handler))


def test_otro_error_trae_el_detalle_de_elevenlabs() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(422, json={"detail": {"message": "Audio demasiado corto"}})

    with pytest.raises(ElevenLabsError, match="Audio demasiado corto"):
        transcribe(stt(handler))


def test_un_error_sin_detalle_trae_el_codigo() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, text="<html>caído</html>")

    with pytest.raises(ElevenLabsError, match="500"):
        transcribe(stt(handler))


def test_sin_conexion_lo_dice() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("sin red", request=request)

    with pytest.raises(ElevenLabsError, match="conectar"):
        transcribe(stt(handler))


def test_sin_clave_no_se_puede_crear() -> None:
    with pytest.raises(ElevenLabsError, match="ELEVENLABS_API_KEY"):
        ElevenLabsStt("")


# Voz: texto → audio.


def tts(handler: Callable[[httpx.Request], httpx.Response]) -> ElevenLabsTts:
    return ElevenLabsTts(
        "clave-de-prueba", "elevenlabs:abc123", transport=httpx.MockTransport(handler)
    )


def pcm(*values: int) -> bytes:
    return np.array(values, dtype="<i2").tobytes()


def test_la_voz_pide_el_audio_crudo_con_el_modelo_y_el_idioma() -> None:
    sent: list[httpx.Request] = []

    def handler(request: httpx.Request) -> httpx.Response:
        sent.append(request)
        return httpx.Response(200, content=pcm(0))

    asyncio.run(tts(handler).synthesize("Hola."))

    request = sent[0]
    assert request.url.path == "/v1/text-to-speech/abc123"
    assert request.url.params["output_format"] == "pcm_24000"
    assert request.headers["xi-api-key"] == "clave-de-prueba"
    assert json.loads(request.content) == {
        "text": "Hola.",
        "model_id": TTS_MODEL,
        "language_code": "es",
    }


def test_la_voz_devuelve_el_audio_entre_menos_uno_y_uno() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=pcm(0, 16384, -16384))

    speech = asyncio.run(tts(handler).synthesize("Hola."))

    assert speech.samples.tolist() == [0.0, 0.5, -0.5]
    assert speech.sample_rate == 24_000


def test_cambiar_de_voz_usa_la_nueva() -> None:
    paths: list[str] = []

    def handler(request: httpx.Request) -> httpx.Response:
        paths.append(request.url.path)
        return httpx.Response(200, content=pcm(0))

    voice = tts(handler)
    voice.set_voice("elevenlabs:xyz789")
    asyncio.run(voice.synthesize("Hola."))

    assert voice.voice == "elevenlabs:xyz789"
    assert paths == ["/v1/text-to-speech/xyz789"]


def test_una_voz_que_el_plan_no_permite_trae_el_motivo() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(402, json={"detail": {"message": "Free users cannot use this"}})

    with pytest.raises(ElevenLabsError, match="Free users cannot use this"):
        asyncio.run(tts(handler).synthesize("Hola."))


# Catálogo: las voces de la cuenta.


def voice_entry(voice_id: str, name: str, **labels: str) -> dict[str, object]:
    return {"voice_id": voice_id, "name": name, "labels": labels}


def catalog(handler: Callable[[httpx.Request], httpx.Response]) -> ElevenLabsCatalog:
    return ElevenLabsCatalog("clave-de-prueba", transport=httpx.MockTransport(handler))


def test_el_catalogo_ofrece_las_voces_de_la_cuenta() -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200,
            json={
                "voices": [
                    voice_entry("abc", "Valentina", gender="female", accent="argentine"),
                    voice_entry("def", "Roger", gender="male", accent="american"),
                    voice_entry("ghi", "River", gender="neutral", accent="irish"),
                    voice_entry("jkl", "Robot"),
                ],
                "has_more": False,
            },
        )

    assert catalog(handler).voices() == [
        VoiceInfo("elevenlabs:abc", "Valentina", "es", "Argentina", "female", "elevenlabs"),
        VoiceInfo("elevenlabs:def", "Roger", "es", "Estados Unidos", "male", "elevenlabs"),
        VoiceInfo("elevenlabs:ghi", "River", "es", "Irish", None, "elevenlabs"),
        VoiceInfo("elevenlabs:jkl", "Robot", "es", "", None, "elevenlabs"),
    ]


def test_el_catalogo_sigue_las_paginas() -> None:
    tokens: list[str | None] = []

    def handler(request: httpx.Request) -> httpx.Response:
        token = request.url.params.get("next_page_token")
        tokens.append(token)
        if token is None:
            return httpx.Response(
                200,
                json={"voices": [voice_entry("a", "A")], "has_more": True, "next_page_token": "p2"},
            )
        return httpx.Response(200, json={"voices": [voice_entry("b", "B")], "has_more": False})

    assert [voice.name for voice in catalog(handler).voices()] == ["A", "B"]
    assert tokens == [None, "p2"]


def test_el_catalogo_pregunta_una_sola_vez() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(200, json={"voices": [voice_entry("a", "A")], "has_more": False})

    voices = catalog(handler)
    voices.voices()
    voices.voices()

    assert len(calls) == 1


def test_si_elevenlabs_falla_el_catalogo_queda_vacio_y_vuelve_a_intentar() -> None:
    calls: list[int] = []

    def handler(request: httpx.Request) -> httpx.Response:
        calls.append(1)
        return httpx.Response(401, json={"detail": {"message": "missing permission"}})

    voices = catalog(handler)

    assert voices.voices() == []
    assert voices.voices() == []
    assert len(calls) == 2


def test_reconoce_las_voces_de_elevenlabs_por_su_id() -> None:
    assert is_elevenlabs_voice("elevenlabs:abc")
    assert not is_elevenlabs_voice("es_AR-daniela-high")
