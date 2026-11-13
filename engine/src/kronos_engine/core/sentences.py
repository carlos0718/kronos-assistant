"""Corte en frases del texto que el modelo genera de a pedazos.

La respuesta pasa a la voz frase por frase, sin esperar a que termine, para
bajar la latencia.
"""

import re

# Una frase termina en un signo de cierre seguido de espacio, o en un salto de
# línea. Exigir el espacio evita cortar decimales como "3.14".
_BOUNDARY = re.compile(r"(?<=[.!?…])\s+|\n+")


class SentenceSplitter:
    def __init__(self) -> None:
        self._buffer = ""

    def feed(self, text: str) -> list[str]:
        """Agrega texto y devuelve las frases que quedaron completas."""
        *complete, self._buffer = _BOUNDARY.split(self._buffer + text)
        return [sentence.strip() for sentence in complete if sentence.strip()]

    def flush(self) -> str | None:
        """Devuelve lo que quedó sin cerrar, al terminar la respuesta."""
        rest, self._buffer = self._buffer.strip(), ""
        return rest or None
