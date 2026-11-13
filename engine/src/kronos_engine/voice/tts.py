"""Texto a voz con Piper."""

import asyncio
import logging
import os
import sys
import threading
from pathlib import Path
from typing import Any

import numpy as np

from kronos_engine.voice.speaker import Speech

log = logging.getLogger(__name__)


class TtsError(RuntimeError):
    pass


def voices_dir() -> Path:
    """Carpeta de caché donde se guardan las voces descargadas."""
    if sys.platform == "win32":
        base = Path(os.environ.get("LOCALAPPDATA", Path.home() / "AppData" / "Local"))
        return base / "Kronos" / "voices"
    return Path(os.environ.get("XDG_CACHE_HOME", Path.home() / ".cache")) / "kronos" / "voices"


class PiperTts:
    """Sintetiza voz con una voz de Piper, por ejemplo `es_AR-daniela-high`.

    La voz se descarga la primera vez (entre 60 y 115 MB) y se carga una sola
    vez. `preload` permite hacerlo al arrancar, sin esperar a la primera
    respuesta.
    """

    def __init__(self, voice: str, directory: Path | None = None) -> None:
        self._voice_name = voice
        self._directory = directory or voices_dir()
        # Any: Piper no publica tipos.
        self._voice: Any = None
        self._lock = threading.Lock()

    def preload(self) -> None:
        threading.Thread(target=self._preload, daemon=True).start()

    def _preload(self) -> None:
        # Si falla (por ejemplo, sin internet), se avisa cuando Kronos quiera hablar.
        try:
            self._load()
        except TtsError as exc:
            log.warning("%s", exc)

    def _load(self) -> Any:
        with self._lock:
            if self._voice is None:
                # Se importa acá porque tarda: así no demora el arranque del motor.
                from piper import PiperVoice
                from piper.download_voices import download_voice

                model = self._directory / f"{self._voice_name}.onnx"
                try:
                    if not model.exists():
                        self._directory.mkdir(parents=True, exist_ok=True)
                        download_voice(self._voice_name, self._directory)
                    self._voice = PiperVoice.load(model)
                    log.info("Voz %s lista.", self._voice_name)
                except Exception as exc:
                    raise TtsError(f"No se pudo preparar la voz {self._voice_name}: {exc}") from exc
            return self._voice

    def _synthesize(self, text: str) -> Speech:
        chunks = list(self._load().synthesize(text))
        if not chunks:
            return Speech(np.zeros(0, dtype=np.float32), 22_050)
        samples = np.concatenate([chunk.audio_float_array for chunk in chunks])
        return Speech(samples.astype(np.float32, copy=False), chunks[0].sample_rate)

    async def synthesize(self, text: str) -> Speech:
        return await asyncio.to_thread(self._synthesize, text)
