"""Voz a texto (Scribe) y texto a voz con ElevenLabs (https://elevenlabs.io).

Corre en la nube y es de pago: el audio y el texto salen de la computadora.

- `ElevenLabsStt` transcribe. El motor lo usa con KRONOS_STT_MODEL=elevenlabs
  (ver pipeline.py), y `engine/scripts/compare_stt.py` lo compara con
  Parakeet. A diferencia de Parakeet, deja fijar el idioma.
- `ElevenLabsTts` habla con una voz de la cuenta del usuario, y
  `ElevenLabsCatalog` lista esas voces para elegirlas en la pestaña Voz. Sus ids
  llevan el prefijo `elevenlabs:` para distinguirlas de las de Piper.
"""

import logging
from typing import Any, Literal

import httpx
import numpy as np

from kronos_engine.core.voices import VoiceInfo
from kronos_engine.voice.speaker import Speech

log = logging.getLogger(__name__)

URL = "https://api.elevenlabs.io"
MODEL = "scribe_v3"
KEY_ENV = "ELEVENLABS_API_KEY"
# El más expresivo de los rápidos (~100 ms). eleven_flash_v2_5 cuesta la mitad.
TTS_MODEL = "eleven_v4_turbo"
TTS_MODEL_ENV = "KRONOS_ELEVENLABS_TTS_MODEL"
VOICE_PREFIX = "elevenlabs:"
# Audio crudo: se reproduce sin decodificar nada.
_TTS_RATE = 24_000
_TTS_FORMAT = f"pcm_{_TTS_RATE}"
# Más voces que estas no entran cómodas en la pestaña Voz.
_MAX_PAGES = 5

_TIMEOUT = httpx.Timeout(30, connect=5)


class ElevenLabsError(RuntimeError):
    pass


def is_elevenlabs_voice(voice: str) -> bool:
    return voice.startswith(VOICE_PREFIX)


def _check_key(api_key: str) -> None:
    if not api_key:
        raise ElevenLabsError(f"Falta la clave de ElevenLabs en {KEY_ENV}.")


def _pcm16(audio: np.ndarray) -> bytes:
    """Audio de 16 kHz en el formato crudo que ElevenLabs acepta sin convertir."""
    pcm: np.ndarray = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    return pcm.tobytes()


def _failure(response: httpx.Response) -> ElevenLabsError:
    if response.status_code == httpx.codes.UNAUTHORIZED:
        return ElevenLabsError(f"ElevenLabs rechazó la clave. Revisá {KEY_ENV} y sus permisos.")
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, dict):
        detail = detail.get("message")
    return ElevenLabsError(
        f"ElevenLabs informó un error: {detail or f'código {response.status_code}'}"
    )


def _async_client(api_key: str, transport: httpx.AsyncBaseTransport | None) -> httpx.AsyncClient:
    return httpx.AsyncClient(
        base_url=URL, headers={"xi-api-key": api_key}, timeout=_TIMEOUT, transport=transport
    )


async def _post(client: httpx.AsyncClient, path: str, **request: Any) -> httpx.Response:
    try:
        response = await client.post(path, **request)
    except httpx.ConnectError as exc:
        raise ElevenLabsError("No se pudo conectar con ElevenLabs.") from exc
    except httpx.TimeoutException as exc:
        raise ElevenLabsError("ElevenLabs tardó demasiado en responder.") from exc
    if response.is_error:
        raise _failure(response)
    return response


class ElevenLabsStt:
    """Transcribe audio de 16 kHz.

    Usa una sola conexión para todas las frases: la primera tarda más porque
    abre la conexión segura.
    """

    def __init__(
        self,
        api_key: str,
        model: str = MODEL,
        language: str = "es",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        _check_key(api_key)
        self._form = {
            "model_id": model,
            "language_code": language,
            "tag_audio_events": "false",
            "file_format": "pcm_s16le_16",
        }
        self._client = _async_client(api_key, transport)

    def preload(self) -> None:
        """No hay nada que cargar: el modelo corre en los servidores de ElevenLabs."""

    async def transcribe(self, audio: np.ndarray) -> str:
        files = {"file": ("frase.pcm", _pcm16(audio), "application/octet-stream")}
        response = await _post(self._client, "/v1/speech-to-text", data=self._form, files=files)
        return str(response.json().get("text", "")).strip()

    async def aclose(self) -> None:
        await self._client.aclose()


class ElevenLabsTts:
    """Habla con una voz de ElevenLabs, por ejemplo `elevenlabs:abc123`."""

    def __init__(
        self,
        api_key: str,
        voice: str,
        model: str = TTS_MODEL,
        language: str = "es",
        transport: httpx.AsyncBaseTransport | None = None,
    ) -> None:
        _check_key(api_key)
        self._voice = voice
        self._model = model
        self._language = language
        self._client = _async_client(api_key, transport)

    @property
    def voice(self) -> str:
        return self._voice

    def set_voice(self, voice: str) -> None:
        self._voice = voice

    def preload(self) -> None:
        """No hay nada que cargar: la voz está en los servidores de ElevenLabs."""

    async def synthesize(self, text: str) -> Speech:
        voice_id = self._voice.removeprefix(VOICE_PREFIX)
        response = await _post(
            self._client,
            f"/v1/text-to-speech/{voice_id}",
            params={"output_format": _TTS_FORMAT},
            json={"text": text, "model_id": self._model, "language_code": self._language},
        )
        samples = np.frombuffer(response.content, dtype="<i2").astype(np.float32) / 32768
        return Speech(samples, _TTS_RATE)


def _gender(labels: dict[str, Any]) -> Literal["female", "male"] | None:
    gender = labels.get("gender")
    if gender == "female":
        return "female"
    if gender == "male":
        return "male"
    return None


def _voice_info(entry: dict[str, Any]) -> VoiceInfo:
    labels = entry.get("labels") or {}
    accent = str(labels.get("accent") or "")
    return VoiceInfo(
        id=VOICE_PREFIX + str(entry["voice_id"]),
        name=str(entry.get("name") or entry["voice_id"]),
        # Los modelos de ElevenLabs hablan español con cualquier voz.
        language="es",
        region=accent[:1].upper() + accent[1:],
        gender=_gender(labels),
        provider="elevenlabs",
    )


class ElevenLabsCatalog:
    """Las voces de la cuenta del usuario: las de fábrica y las que sumó desde la biblioteca.

    Las pide una vez y las recuerda. Si ElevenLabs falla, no ofrece ninguna y
    vuelve a pedirlas la próxima vez.
    """

    def __init__(self, api_key: str, transport: httpx.BaseTransport | None = None) -> None:
        _check_key(api_key)
        self._api_key = api_key
        self._transport = transport
        self._voices: list[VoiceInfo] | None = None

    def voices(self) -> list[VoiceInfo]:
        if self._voices is None:
            try:
                self._voices = self._fetch()
            except (ElevenLabsError, httpx.HTTPError) as exc:
                log.warning("No se pudieron listar las voces de ElevenLabs: %s", exc)
                return []
        return list(self._voices)

    def _fetch(self) -> list[VoiceInfo]:
        found: list[VoiceInfo] = []
        params: dict[str, str | int] = {"page_size": 100}
        with httpx.Client(
            base_url=URL,
            headers={"xi-api-key": self._api_key},
            timeout=_TIMEOUT,
            transport=self._transport,
        ) as client:
            for _ in range(_MAX_PAGES):
                response = client.get("/v2/voices", params=params)
                if response.is_error:
                    raise _failure(response)
                page = response.json()
                found += [_voice_info(entry) for entry in page.get("voices", [])]
                token = page.get("next_page_token")
                if not page.get("has_more") or not token:
                    break
                params["next_page_token"] = token
        return found
