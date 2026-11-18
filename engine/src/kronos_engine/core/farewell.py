"""Reconoce cuándo el usuario se despide, para terminar la conversación.

Mira cómo termina la frase: «abrí Spotify y chau» se despide, pero «chau,
pero antes abrí Spotify» sigue pidiendo algo. Una pregunta nunca es una
despedida («¿cómo se dice chau en inglés?»).
"""

import re
import unicodedata

# Sin tildes ni mayúsculas, como queda la frase al compararla.
_FAREWELLS = [
    tuple(phrase.split())
    for phrase in (
        "chau",
        "chao",
        "adios",
        "hasta luego",
        "hasta manana",
        "hasta pronto",
        "hasta despues",
        "hasta la proxima",
        "hasta la vista",
        "nos vemos",
        "nos hablamos",
        "me voy",
        "eso es todo",
        "nada mas",
        "bye",
        "goodbye",
        "see you",
    )
]
# Lo que suele venir después de despedirse: «chau, Kronos, gracias».
_TRAILING = {"kronos", "gracias", "muchas", "che"}


def _words(text: str) -> list[str]:
    plain = unicodedata.normalize("NFD", text.lower())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    return re.findall(r"[a-z0-9]+", plain)


def is_farewell(text: str) -> bool:
    if "?" in text:
        return False
    words = _words(text)
    while words and words[-1] in _TRAILING:
        words.pop()
    return any(tuple(words[-len(phrase) :]) == phrase for phrase in _FAREWELLS)
