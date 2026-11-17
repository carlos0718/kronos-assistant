"""Voz a texto con Scribe, de ElevenLabs (https://elevenlabs.io).

Corre en la nube y es de pago: el audio sale de la computadora. Por ahora solo
lo usa `engine/scripts/compare_stt.py` para compararlo con Parakeet; el motor
no lo usa. A diferencia de Parakeet, deja fijar el idioma.
"""

import httpx
import numpy as np

URL = "https://api.elevenlabs.io"
MODEL = "scribe_v3"
KEY_ENV = "ELEVENLABS_API_KEY"

_TIMEOUT = httpx.Timeout(30, connect=5)


class ElevenLabsError(RuntimeError):
    pass


def _pcm16(audio: np.ndarray) -> bytes:
    """Audio de 16 kHz en el formato crudo que ElevenLabs acepta sin convertir."""
    pcm: np.ndarray = (np.clip(audio, -1.0, 1.0) * 32767).astype("<i2")
    return pcm.tobytes()


def _failure(response: httpx.Response) -> ElevenLabsError:
    if response.status_code == httpx.codes.UNAUTHORIZED:
        return ElevenLabsError(f"ElevenLabs rechazó la clave. Revisá {KEY_ENV}.")
    try:
        detail = response.json().get("detail")
    except (ValueError, AttributeError):
        detail = None
    if isinstance(detail, dict):
        detail = detail.get("message")
    return ElevenLabsError(
        f"ElevenLabs informó un error: {detail or f'código {response.status_code}'}"
    )


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
        if not api_key:
            raise ElevenLabsError(f"Falta la clave de ElevenLabs en {KEY_ENV}.")
        self._form = {
            "model_id": model,
            "language_code": language,
            "tag_audio_events": "false",
            "file_format": "pcm_s16le_16",
        }
        self._client = httpx.AsyncClient(
            base_url=URL,
            headers={"xi-api-key": api_key},
            timeout=_TIMEOUT,
            transport=transport,
        )

    async def transcribe(self, audio: np.ndarray) -> str:
        files = {"file": ("frase.pcm", _pcm16(audio), "application/octet-stream")}
        try:
            response = await self._client.post("/v1/speech-to-text", data=self._form, files=files)
        except httpx.ConnectError as exc:
            raise ElevenLabsError("No se pudo conectar con ElevenLabs.") from exc
        except httpx.TimeoutException as exc:
            raise ElevenLabsError("ElevenLabs tardó demasiado en responder.") from exc
        if response.is_error:
            raise _failure(response)
        return str(response.json().get("text", "")).strip()

    async def aclose(self) -> None:
        await self._client.aclose()
