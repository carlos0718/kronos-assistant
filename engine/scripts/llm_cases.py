"""Los pedidos con que se comparan los modelos de lenguaje, y cómo se juzga cada respuesta.

Lo usa `compare_llm.py`.
"""

import re
import unicodedata
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field
from typing import Any

from kronos_engine.core.tools import ToolCall, ToolSpec


@dataclass(frozen=True)
class Case:
    """Un pedido y lo que debería hacer el modelo con él."""

    said: str
    # La acción que corresponde, o "" si no corresponde ninguna.
    tool: str = ""
    # Palabras que tienen que aparecer en los datos de la acción («bloc» en el nombre).
    words: tuple[str, ...] = ()
    # Palabras que tienen que aparecer en la respuesta («París»).
    reply_words: tuple[str, ...] = ()
    # Palabras que no tienen que aparecer: lo que no se preguntó.
    avoid_words: tuple[str, ...] = ()


# Los pedidos de las pruebas con micrófono, más los que tienen que contestarse
# sin acción: despedirse, una pregunta general y cosas que Kronos todavía no puede.
CASES = [
    # La acción también da la fecha de mañana: no hay que decirla si no la piden.
    Case("¿Qué hora es?", "current_time", avoid_words=("manana", "viernes")),
    # El reloj simulado dice jueves: mañana es viernes.
    Case("¿Qué día es mañana?", "current_time", reply_words=("viernes",)),
    Case("What time is it?", "current_time", avoid_words=("manana", "tomorrow", "friday")),
    Case("Abrí el bloc de notas.", "open_app", ("bloc",)),
    # Así lo transcribió Parakeet en una prueba con micrófono.
    Case("Abrí el blog de notas.", "open_app", ("bloc", "blog")),
    Case("Abrí Spotify.", "open_app", ("spotify",)),
    Case("Cerrá el bloc de notas.", "close_app", ("bloc",)),
    Case("Abrí la carpeta Documentos.", "open_folder", ("document",)),
    Case("Abrí la carpeta de mi portafolio.", "open_folder", ("portafolio", "portfolio")),
    # Con «aplicación», qwen3:8b a veces abre aplicaciones en vez de carpetas.
    Case("Abrí la carpeta de la aplicación de préstamos.", "open_folder", ("prestamo",)),
    Case("¿Cuál es la capital de Francia?", reply_words=("paris",)),
    # qwen3:8b contestaba que no podía, por la regla de no ofrecer lo que no puede hacer.
    Case("Explicame qué es un agujero negro.", reply_words=("gravedad",)),
    Case("Escribí hola en el bloc de notas."),
    Case("¿Qué temperatura hace hoy?"),
    Case("Chau, gracias."),
]

# Lo que no se puede decir en voz alta: Markdown, viñetas y emojis.
_UNSPEAKABLE = re.compile(r"[*#_`|]|^\s*(?:[-•]|\d+\.)\s", re.MULTILINE)
_EMOJI = re.compile("[\U0001f000-\U0001faff☀-➿]")


def plain(text: str) -> str:
    """Sin mayúsculas, tildes ni signos, para comparar palabras."""
    text = unicodedata.normalize("NFD", text.casefold())
    kept = "".join(c if c.isalnum() else " " for c in text if not unicodedata.combining(c))
    return " ".join(kept.split())


def arguments_text(arguments: Mapping[str, Any]) -> str:
    values: list[str] = []
    for value in arguments.values():
        values += [str(item) for item in value] if isinstance(value, list) else [str(value)]
    return plain(" ".join(values))


@dataclass
class Turn:
    """Lo que pasó con un pedido en una ronda."""

    calls: list[ToolCall] = field(default_factory=list)
    reply: str = ""
    first_word: float | None = None
    total: float = 0.0
    error: str = ""

    def right_action(self, case: Case) -> bool:
        if self.error:
            return False
        if not case.tool:
            return not self.calls
        if [call.name for call in self.calls] != [case.tool]:
            return False
        found = arguments_text(self.calls[0].arguments)
        return not case.words or any(word in found for word in case.words)

    def right_reply(self, case: Case) -> bool:
        reply = plain(self.reply)
        if any(word in reply.split() for word in case.avoid_words):
            return False
        return bool(reply) and all(word in reply for word in case.reply_words)

    def speakable(self) -> bool:
        return not _UNSPEAKABLE.search(self.reply) and not _EMOJI.search(self.reply)


def _name(arguments: Mapping[str, Any]) -> str:
    return str(arguments.get("name") or "la aplicación")


def _folder(arguments: Mapping[str, Any]) -> str:
    subfolders = arguments.get("subfolders") or []
    named = subfolders[-1] if subfolders else arguments.get("folder")
    return f"la carpeta {named or 'pedida'}"


class SimulatedTools:
    """Ofrece las acciones reales de Kronos, pero solo anota las que pide el modelo.

    Devuelve lo que devolvería la acción si saliera bien, con la confirmación
    aprobada, sin tocar nada de la computadora.
    """

    def __init__(self, specs: Sequence[ToolSpec], clock: str) -> None:
        self._specs = list(specs)
        self._clock = clock
        self.calls: list[ToolCall] = []

    def specs(self) -> Sequence[ToolSpec]:
        return self._specs

    async def run(self, call: ToolCall) -> str:
        self.calls.append(call)
        arguments = call.arguments
        results = {
            "current_time": self._clock,
            "open_app": f"Se abrió {_name(arguments)}.",
            "close_app": f"Hecho: se cerró {_name(arguments)}.",
            "open_folder": f"Se abrió {_folder(arguments)}.",
        }
        return results.get(call.name, f"No existe la acción {call.name}.")
