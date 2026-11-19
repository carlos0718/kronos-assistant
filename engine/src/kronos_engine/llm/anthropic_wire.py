"""Traduce la conversación de Kronos al formato de la API de Claude.

Claude razona antes de contestar, y ese razonamiento queda atado a la
conversación exacta en la que se produjo: si se devuelve después de cambiar un
turno anterior, la API lo rechaza. Kronos olvida los turnos más viejos, así que
el razonamiento solo se devuelve dentro del turno en curso, mientras Claude
espera el resultado de una acción; el de los turnos anteriores se saca entero,
que es lo que la API permite.
"""

import itertools
from collections.abc import Iterator, Mapping, Sequence
from typing import Any

from kronos_engine.core.llm import Message
from kronos_engine.core.tools import ToolSpec


def split_system(messages: Sequence[Message]) -> tuple[str, list[Message]]:
    """Las instrucciones, que Claude recibe aparte, y el resto de la conversación."""
    system = "\n\n".join(message.content for message in messages if message.role == "system")
    return system, [message for message in messages if message.role != "system"]


def wire_tools(tools: Sequence[ToolSpec]) -> list[dict[str, Any]]:
    return [
        {"name": tool.name, "description": tool.description, "input_schema": dict(tool.parameters)}
        for tool in tools
    ]


def wire_messages(
    messages: Sequence[Message], replay: Mapping[str, Sequence[Any]]
) -> list[dict[str, Any]]:
    """La conversación sin instrucciones, en el formato de Claude.

    `replay` tiene lo que mandó Claude en cada pedido de acciones, tal cual,
    según el id de la primera acción: se usa solo en el turno en curso.
    """
    users = [index for index, message in enumerate(messages) if message.role == "user"]
    current_turn = users[-1] if users else 0
    made_up = (f"toolu_kronos_{number}" for number in itertools.count(1))
    # Ids de las acciones que todavía esperan resultado, en orden.
    waiting: list[str] = []
    wire: list[dict[str, Any]] = []
    for index, message in enumerate(messages):
        if message.role == "tool":
            result_id = message.tool_call_id or (waiting[0] if waiting else next(made_up))
            if result_id in waiting:
                waiting.remove(result_id)
            _add_result(wire, result_id, message.content)
        elif message.role == "assistant":
            ids = [call.id or next(made_up) for call in message.tool_calls]
            waiting = ids
            raw = replay.get(ids[0]) if ids and index > current_turn else None
            if raw is not None:
                wire.append({"role": "assistant", "content": raw})
            elif content := list(_assistant_blocks(message, ids)):
                plain = len(content) == 1 and content[0]["type"] == "text"
                wire.append({"role": "assistant", "content": message.content if plain else content})
        elif message.role == "user":
            wire.append({"role": "user", "content": message.content})
    return wire


def _assistant_blocks(message: Message, ids: Sequence[str]) -> Iterator[dict[str, Any]]:
    if message.content:
        yield {"type": "text", "text": message.content}
    for call, call_id in zip(message.tool_calls, ids, strict=True):
        yield {"type": "tool_use", "id": call_id, "name": call.name, "input": dict(call.arguments)}


def _add_result(wire: list[dict[str, Any]], tool_use_id: str, result: str) -> None:
    part = {"type": "tool_result", "tool_use_id": tool_use_id, "content": result}
    last = wire[-1] if wire else None
    # Todos los resultados de un pedido van juntos, en un solo mensaje.
    if last and last["role"] == "user" and isinstance(last["content"], list):
        last["content"].append(part)
    else:
        wire.append({"role": "user", "content": [part]})


def echoed(content: Sequence[Any]) -> list[Any]:
    """Lo que se devuelve de una respuesta de Claude en el pedido siguiente.

    Si Claude se negó a mitad de la respuesta y la terminó otro modelo, la API
    marca el corte con un bloque `fallback`: de lo anterior solo vuelven los
    textos, y el bloque queda donde estaba.
    """
    cuts = [index for index, part in enumerate(content) if part.type == "fallback"]
    if not cuts:
        return list(content)
    cut = cuts[-1]
    return [part for part in content[:cut] if part.type == "text"] + list(content[cut:])
