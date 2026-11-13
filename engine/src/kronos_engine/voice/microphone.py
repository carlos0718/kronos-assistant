"""Captura del micrófono en cuadros de 16 kHz."""

import asyncio
import contextlib
from collections.abc import AsyncIterator

import numpy as np

from kronos_engine.voice import FRAME_SAMPLES, SAMPLE_RATE


class MicrophoneError(RuntimeError):
    pass


@contextlib.asynccontextmanager
async def open_microphone() -> AsyncIterator[AsyncIterator[np.ndarray]]:
    """Abre el micrófono por defecto y entrega sus cuadros.

    El micrófono solo queda abierto dentro del bloque `async with`.
    """
    import sounddevice

    loop = asyncio.get_running_loop()
    frames: asyncio.Queue[np.ndarray] = asyncio.Queue()

    def on_audio(data: np.ndarray, _frames: int, _time: object, _status: object) -> None:
        # Corre en un hilo de audio: se copia el cuadro y se pasa al bucle de asyncio.
        loop.call_soon_threadsafe(frames.put_nowait, data[:, 0].copy())

    try:
        stream = sounddevice.InputStream(
            samplerate=SAMPLE_RATE,
            channels=1,
            dtype="float32",
            blocksize=FRAME_SAMPLES,
            callback=on_audio,
        )
        stream.start()
    except sounddevice.PortAudioError as exc:
        raise MicrophoneError(f"No se pudo abrir el micrófono: {exc}") from exc

    async def read() -> AsyncIterator[np.ndarray]:
        while True:
            yield await frames.get()

    try:
        yield read()
    finally:
        stream.stop()
        stream.close()
