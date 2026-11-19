"""Elige con el modelo, en una pregunta aparte, cuál opción es la que pidió el usuario."""

import asyncio
import logging
import re
from collections.abc import Sequence

from kronos_engine.core.llm import LLMError, LLMProvider, Message

log = logging.getLogger(__name__)

# Una pregunta corta y con respuesta cerrada: la lista no pasa por la conversación,
# así que el modelo no tiene cómo leérsela en voz alta al usuario.
_INSTRUCTIONS = """\
Elegís una opción de una lista numerada. El usuario la nombró por lo que es, \
con otras palabras o en otro idioma: los nombres suelen estar en inglés o \
abreviados. Respondé solo con el número de la opción que es claramente lo \
que pidió. Si ninguna lo es, o dudás entre varias, respondé 0. No escribas \
nada más que el número."""
# Una pregunta así tarda uno o dos segundos; si tarda mucho más, mejor no elegir.
_TIMEOUT_SECONDS = 15
_NUMBER = re.compile(r"\d+")


class ModelChooser:
    """Implementa `Chooser` con el modelo de lenguaje."""

    def __init__(self, provider: LLMProvider, timeout: float = _TIMEOUT_SECONDS) -> None:
        self._provider = provider
        self._timeout = timeout

    async def choose(self, wanted: str, options: Sequence[str]) -> int | None:
        if not options:
            return None
        listed = "\n".join(f"{number}. {option}" for number, option in enumerate(options, 1))
        # El pedido va después de la lista: así acertó 7 de 8 contra 3 de 8 con el
        # pedido arriba, que el modelo pierde de vista tras decenas de nombres.
        question = f"El usuario pidió: «{wanted}». ¿Qué número es? (0 si ninguna)"
        messages = [
            Message("system", _INSTRUCTIONS),
            Message("user", f"Opciones:\n{listed}\n\n{question}"),
        ]
        try:
            reply = await asyncio.wait_for(self._ask(messages), self._timeout)
        except (LLMError, TimeoutError) as exc:
            log.warning("No se pudo elegir con el modelo: %s", exc)
            return None
        found = _NUMBER.search(reply)
        number = int(found.group()) if found else 0
        # Cero, o un número que no está en la lista: no eligió ninguna.
        return number - 1 if 1 <= number <= len(options) else None

    async def _ask(self, messages: list[Message]) -> str:
        reply = ""
        async for piece in self._provider.stream(messages):
            if isinstance(piece, str):
                reply += piece
        return reply
