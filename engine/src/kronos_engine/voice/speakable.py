"""Limpia el texto del modelo antes de decirlo en voz alta.

Al modelo se le pide que responda sin formato, pero a veces igual lo usa. La
voz leería los símbolos ("asterisco asterisco") o se trabaría con los emojis.
"""

import re

# Marcas al principio de una línea: títulos (#), listas (-, *, •) y citas (>).
_LINE_MARKS = re.compile(r"^\s*(?:#+|[-*•>])\s*", re.MULTILINE)
# Símbolos de énfasis y de código.
_INLINE_MARKS = re.compile(r"[*_`~]+")
# Emojis y pictogramas, con sus modificadores.
_EMOJI = re.compile("[\U0001f000-\U0001faff\u2600-\u27bf\u2b00-\u2bff\ufe0f\u200d]")
_SPACES = re.compile(r"\s+")


def speakable(text: str) -> str:
    """Devuelve el texto sin formato ni emojis. Vacío si no queda nada para decir."""
    text = _LINE_MARKS.sub("", text)
    text = _INLINE_MARKS.sub("", text)
    text = _EMOJI.sub("", text)
    return _SPACES.sub(" ", text).strip()
