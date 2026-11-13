"""Decide cuándo empieza y cuándo termina lo que dice el usuario.

Recibe, cuadro por cuadro, la probabilidad de voz que calcula el detector
(VAD). No sabe de audio: solo cuenta cuadros.
"""

from dataclasses import dataclass
from enum import Enum


class Verdict(Enum):
    WAITING = "waiting"  # Todavía no habló nadie.
    SPEAKING = "speaking"  # El usuario está hablando.
    DONE = "done"  # Terminó la frase.
    NO_SPEECH = "no_speech"  # Venció el plazo sin que hablara nadie.


@dataclass(frozen=True)
class EndpointConfig:
    frame_ms: float = 32  # 512 muestras a 16 kHz, el cuadro que pide Silero.
    start_threshold: float = 0.5
    # Más bajo que el de inicio, para no cortar en las sílabas débiles.
    end_threshold: float = 0.35
    min_speech_ms: float = 96  # Voz seguida que hace falta para dar por empezada la frase.
    end_silence_ms: float = 800  # Silencio que da por terminada la frase.
    start_timeout_ms: float = 8000  # Espera máxima a que alguien hable.
    max_utterance_ms: float = 30000
    pre_roll_ms: float = 320  # Audio previo a la voz que se conserva.

    def frames(self, milliseconds: float) -> int:
        return max(1, round(milliseconds / self.frame_ms))


class Endpointer:
    def __init__(self, config: EndpointConfig | None = None) -> None:
        self._config = config or EndpointConfig()
        self._count = 0
        self._voiced_run = 0
        self._silent_run = 0
        self._start: int | None = None

    @property
    def first_frame(self) -> int:
        """Primer cuadro que vale la pena transcribir."""
        if self._start is None:
            return 0
        return max(0, self._start - self._config.frames(self._config.pre_roll_ms))

    def feed(self, probability: float) -> Verdict:
        config = self._config
        index = self._count
        self._count += 1

        if self._start is None:
            self._voiced_run = self._voiced_run + 1 if probability >= config.start_threshold else 0
            if self._voiced_run >= config.frames(config.min_speech_ms):
                self._start = index - self._voiced_run + 1
                return Verdict.SPEAKING
            if self._count >= config.frames(config.start_timeout_ms):
                return Verdict.NO_SPEECH
            return Verdict.WAITING

        self._silent_run = self._silent_run + 1 if probability < config.end_threshold else 0
        too_long = self._count - self._start >= config.frames(config.max_utterance_ms)
        if too_long or self._silent_run >= config.frames(config.end_silence_ms):
            return Verdict.DONE
        return Verdict.SPEAKING
