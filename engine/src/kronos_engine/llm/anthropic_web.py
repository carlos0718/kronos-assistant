"""Lo que Claude buscó o leyó en internet: una nota para recordarlo y el registro.

Claude busca en los servidores de Anthropic, y lo que encuentra llega en
bloques que Kronos no guarda en el historial: devolverlos en cada turno
costaría miles de tokens. En su lugar queda una nota corta con lo que buscó y
de dónde salió, con las frases que citó de esas páginas. Sin ella, en el turno
siguiente Claude ve una respuesta que no sabe de dónde sacó y la pone en duda:
vuelve a buscar o le dice al usuario que no la verificó.
"""

import logging
from collections.abc import Sequence
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import urlparse

log = logging.getLogger(__name__)

_SEARCH = "web_search"
_FETCH = "web_fetch"
_RESULTS = {"web_search_tool_result", "web_fetch_tool_result"}
# Alcanza para saber de dónde salió la respuesta; cada fuente cuesta tokens en cada turno.
_MAX_SOURCES = 5
# Las frases citadas son la prueba de los datos de la respuesta (un resultado,
# quién hizo los goles): pocas y cortas, porque también van en cada turno.
_MAX_QUOTES = 6
_QUOTE_CHARS = 200


@dataclass
class _Use:
    """Una búsqueda o una página leída, con lo que devolvió."""

    kind: str
    # Lo que buscó, o la dirección que leyó.
    target: str
    sources: list[str] = field(default_factory=list)
    error: str = ""


def web_note(content: Sequence[Any]) -> str:
    """La nota de lo que Claude hizo en internet en esta respuesta, o "" si no hizo nada."""
    uses = _uses(content)
    if not uses:
        return ""
    parts = [_told(use) for use in uses]
    if quotes := _quotes(content):
        parts.append("Lo que citaste de esas páginas: " + "; ".join(quotes) + ".")
    if any(not use.error for use in uses):
        parts.append(
            "Esto es solo un resumen: las páginas completas las leíste al responder, y "
            "todos los datos de tu respuesta salieron de ahí, aunque no aparezcan en esta "
            "nota. Ya está verificado: no lo corrijas ni hace falta volver a buscarlo."
        )
    return "[Nota de Kronos, no se dijo en voz alta: " + " ".join(parts) + "]"


def log_web_use(content: Sequence[Any]) -> None:
    """Anota cuánto usó internet y qué falló. Lo que buscó, solo con KRONOS_DEBUG=1."""
    uses = _uses(content)
    if not uses:
        return
    searches = sum(use.kind == _SEARCH for use in uses)
    pages = len(uses) - searches
    log.info(
        "Claude buscó en internet: %s y %s.",
        _count(searches, "búsqueda"),
        _count(pages, "página leída", "páginas leídas"),
    )
    for use in uses:
        # Lo que buscó es parte de la conversación: es privado.
        log.debug("%s «%s».", "Buscó" if use.kind == _SEARCH else "Leyó", use.target)
        if use.error:
            what = "una búsqueda" if use.kind == _SEARCH else "leer una página"
            log.info("Falló %s en internet (%s).", what, use.error)


def _uses(content: Sequence[Any]) -> list[_Use]:
    uses: dict[str, _Use] = {}
    for part in content:
        if part.type == "server_tool_use" and part.name in (_SEARCH, _FETCH):
            arguments = dict(getattr(part, "input", None) or {})
            target = arguments.get("query") or arguments.get("url") or ""
            uses[part.id] = _Use(part.name, str(target))
        elif part.type in _RESULTS and (use := uses.get(part.tool_use_id)):
            _fill(use, part.content)
    return list(uses.values())


def _quotes(content: Sequence[Any]) -> list[str]:
    """Las frases de las páginas que Claude citó en la respuesta, sin repetir."""
    quotes: list[str] = []
    for part in content:
        if part.type != "text":
            continue
        for citation in getattr(part, "citations", None) or []:
            text = " ".join(str(getattr(citation, "cited_text", "") or "").split())
            if len(text) > _QUOTE_CHARS:
                text = text[:_QUOTE_CHARS].rsplit(" ", 1)[0] + "…"
            if text and f"«{text}»" not in quotes:
                quotes.append(f"«{text}»")
    return quotes[:_MAX_QUOTES]


def _fill(use: _Use, result: Any) -> None:
    if isinstance(result, list):
        use.sources = [
            _source(item.title, item.url, getattr(item, "page_age", None))
            for item in result[:_MAX_SOURCES]
        ]
    elif result.type.endswith("_error"):
        use.error = getattr(result, "error_code", "") or "error"
    else:
        document = getattr(result, "content", None)
        use.sources = [_source(getattr(document, "title", "") or "", result.url, None)]


def _told(use: _Use) -> str:
    if use.kind == _SEARCH:
        if use.error:
            return f"La búsqueda «{use.target}» falló."
        if not use.sources:
            return f"Buscaste en internet «{use.target}»."
        return f"Buscaste en internet «{use.target}» y encontraste: {'; '.join(use.sources)}."
    if use.error:
        return f"No se pudo leer {_site(use.target)}."
    return f"Leíste la página {use.sources[0] if use.sources else _site(use.target)}."


def _source(title: str, url: str, age: str | None) -> str:
    where = ", ".join(part for part in (_site(url), age) if part)
    return f"{title} ({where})" if title else where


def _site(url: str) -> str:
    return urlparse(url).netloc.removeprefix("www.") or url


def _count(number: int, one: str, many: str = "") -> str:
    return f"{number} {one if number == 1 else many or one + 's'}"
