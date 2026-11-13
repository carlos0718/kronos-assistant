"""Voz a texto con faster-whisper."""

import asyncio
import threading
from typing import Any

import numpy as np


class WhisperStt:
    """Transcribe audio de 16 kHz.

    El modelo se descarga la primera vez (unos 500 MB el `small`) y se carga
    una sola vez. `preload` permite hacerlo al arrancar, sin esperar a que el
    usuario hable.
    """

    def __init__(self, model_size: str = "small", language: str | None = "es") -> None:
        self._model_size = model_size
        self._language = language
        # Any: faster-whisper no publica tipos.
        self._model: Any = None
        self._lock = threading.Lock()

    def preload(self) -> None:
        threading.Thread(target=self._load, daemon=True).start()

    def _load(self) -> Any:
        with self._lock:
            if self._model is None:
                # Se importa acá porque tarda: así no demora el arranque del motor.
                from faster_whisper import WhisperModel

                # int8 en CPU: la opción liviana que funciona en cualquier equipo.
                self._model = WhisperModel(self._model_size, device="cpu", compute_type="int8")
            return self._model

    def _transcribe(self, audio: np.ndarray) -> str:
        segments, _ = self._load().transcribe(
            audio.astype(np.float32, copy=False),
            language=self._language,
            # Cada frase es independiente: sin esto whisper a veces repite la anterior.
            condition_on_previous_text=False,
        )
        return " ".join(segment.text.strip() for segment in segments).strip()

    async def transcribe(self, audio: np.ndarray) -> str:
        return await asyncio.to_thread(self._transcribe, audio)
