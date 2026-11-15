"""Voz: micrófono, detección de voz (VAD), transcripción (STT) y habla (TTS)."""

from typing import Final

SAMPLE_RATE: Final = 16_000
# Muestras por cuadro: el tamaño que pide Silero a 16 kHz (32 ms).
FRAME_SAMPLES = 512
