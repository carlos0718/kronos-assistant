"""Cuánto tarda un turno, paso por paso: transcribir, modelo y voz.

Es la demora que el usuario percibe entre que termina de hablar y que Kronos
empieza a responder. No incluye el silencio que el oyente espera para dar la
frase por terminada.
"""

import time
from collections.abc import Callable
from enum import Enum

Clock = Callable[[], float]


class Step(Enum):
    SPEECH_END = "speech_end"  # El usuario terminó de hablar: se cerró el micrófono.
    TRANSCRIBED = "transcribed"  # Ya está el texto de lo que dijo.
    FIRST_SENTENCE = "first_sentence"  # El modelo completó la primera frase.
    FIRST_SOUND = "first_sound"  # La voz empezó a sonar.


# Cada tramo: nombre que se muestra, dónde empieza y dónde termina.
_STAGES = (
    ("transcribir", Step.SPEECH_END, Step.TRANSCRIBED),
    ("modelo", Step.TRANSCRIBED, Step.FIRST_SENTENCE),
    ("voz", Step.FIRST_SENTENCE, Step.FIRST_SOUND),
)


def _seconds(value: float) -> str:
    return f"{value:.2f} s".replace(".", ",")


class TurnTimer:
    def __init__(self, clock: Clock = time.perf_counter) -> None:
        self._clock = clock
        self._marks: dict[Step, float] = {}

    def mark(self, step: Step) -> None:
        """Anota cuándo pasó. Si el paso se repite, vale la primera vez."""
        if step not in self._marks:
            self._marks[step] = self._clock()

    def summary(self) -> str | None:
        """Los tiempos del turno en una línea, o None si Kronos no llegó a hablar."""
        marks = self._marks
        if Step.FIRST_SOUND not in marks:
            return None
        parts = [
            f"{name} {_seconds(marks[end] - marks[start])}"
            for name, start, end in _STAGES
            if start in marks and end in marks
        ]
        parts.append(f"total {_seconds(marks[Step.FIRST_SOUND] - min(marks.values()))}")
        return " · ".join(parts)
