import asyncio
from collections.abc import Callable

import httpx
import numpy as np
import pytest

from kronos_engine.voice.elevenlabs import ElevenLabsError, ElevenLabsStt

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
