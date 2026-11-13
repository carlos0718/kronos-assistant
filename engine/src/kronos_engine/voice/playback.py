"""Reproducción de audio por el altavoz por defecto."""

import asyncio

import numpy as np


class SpeakerError(RuntimeError):
    pass


async def play(samples: np.ndarray, sample_rate: int) -> None:
    """Reproduce el audio y vuelve cuando terminó de sonar.

    Si se cancela (el usuario cortó a Kronos), el sonido se corta en el acto.
    """
    import sounddevice

    loop = asyncio.get_running_loop()
    finished = asyncio.Event()
    samples = samples.astype(np.float32, copy=False)
    position = 0

    def on_audio(out: np.ndarray, frames: int, _time: object, _status: object) -> None:
        # Corre en un hilo de audio: copia el tramo que sigue y avisa cuando no queda más.
        nonlocal position
        chunk = samples[position : position + frames]
        out[: len(chunk), 0] = chunk
        out[len(chunk) :, 0] = 0
        position += frames
        if position >= len(samples):
            raise sounddevice.CallbackStop

    def on_finished() -> None:
        loop.call_soon_threadsafe(finished.set)

    try:
        stream = sounddevice.OutputStream(
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            callback=on_audio,
            finished_callback=on_finished,
        )
    except sounddevice.PortAudioError as exc:
        raise SpeakerError(f"No se pudo abrir el altavoz: {exc}") from exc

    try:
        stream.start()
        await finished.wait()
    finally:
        # `abort` corta sin esperar a que se vacíe lo que quedaba por sonar.
        stream.abort()
        stream.close()
