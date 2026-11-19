from types import SimpleNamespace
from typing import Any

from kronos_engine.core.llm import Message
from kronos_engine.core.tools import ToolCall, ToolSpec
from kronos_engine.llm.anthropic_wire import echoed, split_system, wire_messages, wire_tools

CLOCK = ToolCall("current_time", {}, id="toolu_1")


def block(type_: str, **fields: Any) -> SimpleNamespace:
    return SimpleNamespace(type=type_, **fields)


def test_las_instrucciones_van_aparte() -> None:
    system, rest = split_system([Message("system", "Sos Kronos."), Message("user", "Hola")])

    assert system == "Sos Kronos."
    assert rest == [Message("user", "Hola")]


def test_las_acciones_van_con_su_esquema() -> None:
    spec = ToolSpec("open_app", "Abre una aplicación.", {"type": "object", "properties": {}})

    assert wire_tools([spec]) == [
        {
            "name": "open_app",
            "description": "Abre una aplicación.",
            "input_schema": {"type": "object", "properties": {}},
        }
    ]


def test_una_charla_sin_acciones_pasa_tal_cual() -> None:
    wire = wire_messages(
        [Message("user", "Hola"), Message("assistant", "Hola."), Message("user", "Chau")], {}
    )

    assert wire == [
        {"role": "user", "content": "Hola"},
        {"role": "assistant", "content": "Hola."},
        {"role": "user", "content": "Chau"},
    ]


def test_una_accion_va_con_su_id_y_el_resultado_la_nombra() -> None:
    wire = wire_messages(
        [
            Message("user", "¿Qué hora es?"),
            Message("assistant", "", (CLOCK,)),
            Message("tool", "15:42", tool_name="current_time", tool_call_id="toolu_1"),
        ],
        {},
    )

    assert wire[1] == {
        "role": "assistant",
        "content": [{"type": "tool_use", "id": "toolu_1", "name": "current_time", "input": {}}],
    }
    assert wire[2] == {
        "role": "user",
        "content": [{"type": "tool_result", "tool_use_id": "toolu_1", "content": "15:42"}],
    }


def test_lo_dicho_antes_de_la_accion_va_primero() -> None:
    wire = wire_messages([Message("user", "Hora"), Message("assistant", "Ya va.", (CLOCK,))], {})

    assert wire[1]["content"][0] == {"type": "text", "text": "Ya va."}


def test_los_resultados_de_varias_acciones_van_en_un_solo_mensaje() -> None:
    # Claude deja de pedir acciones en paralelo si cada resultado va aparte.
    second = ToolCall("open_app", {"name": "Spotify"}, id="toolu_2")
    wire = wire_messages(
        [
            Message("user", "Hora y Spotify"),
            Message("assistant", "", (CLOCK, second)),
            Message("tool", "15:42", tool_name="current_time", tool_call_id="toolu_1"),
            Message("tool", "Se abrió Spotify.", tool_name="open_app", tool_call_id="toolu_2"),
        ],
        {},
    )

    assert len(wire) == 3
    assert [part["tool_use_id"] for part in wire[2]["content"]] == ["toolu_1", "toolu_2"]


def test_acciones_sin_id_de_otro_modelo_reciben_uno_y_su_resultado_tambien() -> None:
    # Si la charla empezó con Ollama, las acciones viejas no tienen id.
    wire = wire_messages(
        [
            Message("user", "Hora"),
            Message("assistant", "", (ToolCall("current_time"),)),
            Message("tool", "15:42", tool_name="current_time"),
            Message("assistant", "Son las 15:42."),
            Message("user", "Gracias"),
        ],
        {},
    )

    made_up = wire[1]["content"][0]["id"]
    assert made_up
    assert wire[2]["content"][0]["tool_use_id"] == made_up


def test_un_turno_vacio_no_se_manda() -> None:
    # Un turno cortado sin respuesta: Claude rechaza un mensaje vacío.
    wire = wire_messages(
        [Message("user", "Hola"), Message("assistant", ""), Message("user", "¿Estás?")], {}
    )

    assert [message["role"] for message in wire] == ["user", "user"]


def test_en_el_turno_en_curso_devuelve_lo_que_mando_claude_sin_tocarlo() -> None:
    # El razonamiento tiene que volver igual mientras espera el resultado de la acción.
    raw = [block("thinking", thinking="", signature="firma"), block("tool_use", id="toolu_1")]
    wire = wire_messages(
        [Message("user", "Hora"), Message("assistant", "", (CLOCK,))], {"toolu_1": raw}
    )

    assert wire[1] == {"role": "assistant", "content": raw}


def test_de_los_turnos_anteriores_no_devuelve_el_razonamiento() -> None:
    # Kronos olvida los turnos más viejos: el razonamiento de antes ya no
    # coincidiría con la conversación, así que se saca entero.
    raw = [block("thinking", thinking="", signature="firma"), block("tool_use", id="toolu_1")]
    wire = wire_messages(
        [
            Message("user", "Hora"),
            Message("assistant", "", (CLOCK,)),
            Message("tool", "15:42", tool_name="current_time", tool_call_id="toolu_1"),
            Message("assistant", "Son las 15:42."),
            Message("user", "Gracias"),
        ],
        {"toolu_1": raw},
    )

    assert wire[1]["content"] == [
        {"type": "tool_use", "id": "toolu_1", "name": "current_time", "input": {}}
    ]


def test_sin_cambio_de_modelo_se_devuelve_todo() -> None:
    content = [block("thinking"), block("text"), block("tool_use")]

    assert echoed(content) == content


def test_si_otro_modelo_termino_la_respuesta_se_saca_lo_de_antes_del_corte() -> None:
    # Regla de la API: antes del último bloque «fallback» solo quedan los textos.
    content = [
        block("thinking"),
        block("text"),
        block("tool_use"),
        block("fallback"),
        block("thinking"),
        block("tool_use"),
    ]

    assert [part.type for part in echoed(content)] == [
        "text",
        "fallback",
        "thinking",
        "tool_use",
    ]


def test_de_los_turnos_anteriores_la_nota_va_antes_de_la_respuesta() -> None:
    # Claude tiene que saber de dónde salió lo que contestó.
    wire = wire_messages(
        [
            Message("user", "¿Boca?"),
            Message("assistant", "Ganó Boca.", aside="[Buscaste «Boca».]"),
            Message("user", "¿Cuándo?"),
        ],
        {},
    )

    assert wire[1]["content"] == [
        {"type": "text", "text": "[Buscaste «Boca».]"},
        {"type": "text", "text": "Ganó Boca."},
    ]


def test_la_nota_va_tambien_con_las_acciones() -> None:
    wire = wire_messages(
        [
            Message("user", "Hora"),
            Message("assistant", "", (CLOCK,), aside="[Buscaste «hora».]"),
            Message("tool", "15:42", tool_name="current_time", tool_call_id="toolu_1"),
            Message("assistant", "Son las 15:42."),
            Message("user", "Gracias"),
        ],
        {},
    )

    assert wire[1]["content"][0] == {"type": "text", "text": "[Buscaste «hora».]"}
    assert wire[1]["content"][1]["type"] == "tool_use"
