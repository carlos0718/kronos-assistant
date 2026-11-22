import logging
from types import SimpleNamespace
from typing import Any

import pytest

from kronos_engine.llm.anthropic_web import log_web_use, web_note


def block(type_: str, **fields: Any) -> SimpleNamespace:
    return SimpleNamespace(type=type_, **fields)


def search(id_: str, query: str) -> SimpleNamespace:
    return block("server_tool_use", id=id_, name="web_search", input={"query": query})


def found(id_: str, *results: tuple[str, str, str | None]) -> SimpleNamespace:
    return block(
        "web_search_tool_result",
        tool_use_id=id_,
        content=[
            block("web_search_result", title=title, url=url, page_age=age, encrypted_content="x")
            for title, url, age in results
        ],
    )


BOCA = [
    search("srvtoolu_1", "último partido de Boca"),
    found(
        "srvtoolu_1",
        ("Boca le ganó a River 2 a 1", "https://www.ole.com.ar/boca/partido", "November 16, 2026"),
        ("Resumen del superclásico", "https://espn.com.ar/futbol/nota", None),
    ),
    block("text", text="Boca ganó 2 a 1 el domingo."),
]


def test_sin_buscar_no_hay_nota() -> None:
    assert web_note([block("text", text="Hola.")]) == ""


def test_la_nota_dice_que_busco_y_que_encontro() -> None:
    note = web_note(BOCA)

    assert "«último partido de Boca»" in note
    assert "Boca le ganó a River 2 a 1" in note
    assert "ole.com.ar" in note
    # La fecha de la página sirve para saber si «el último» sigue siendo el último.
    assert "November 16, 2026" in note


def cited(text: str, *quotes: str) -> SimpleNamespace:
    """Un texto de Claude que cita frases de las páginas que encontró."""
    return block(
        "text",
        text=text,
        citations=[
            block("web_search_result_location", cited_text=quote, url="https://ole.com.ar/x")
            for quote in quotes
        ],
    )


def test_la_nota_lleva_las_frases_que_cito() -> None:
    # Con solo los títulos, en el turno siguiente Claude veía datos (el 2-0, los
    # goles) que no sabía de dónde sacó, y le decía al usuario que no los verificó.
    content = [
        *BOCA[:2],
        cited("Ganó 2 a 0.", "Boca venció 2-0 a Atlético Mineiro con goles de Ascacibar"),
    ]

    assert "Boca venció 2-0 a Atlético Mineiro con goles de Ascacibar" in web_note(content)


def test_cada_frase_citada_va_una_vez_y_recortada() -> None:
    long = "Boca " + "campeón " * 100
    content = [*BOCA[:2], cited("Uno.", "Ganó Boca"), cited("Dos.", "Ganó Boca", long)]

    note = web_note(content)

    assert note.count("Ganó Boca") == 1
    assert long not in note
    assert "Boca campeón" in note


def test_la_nota_dice_que_la_respuesta_ya_esta_verificada() -> None:
    note = web_note(BOCA)

    assert "verificad" in note
    # Con solo la nota a la vista, Claude no encontraba en ella los goleadores
    # que había dicho y se corregía: tiene que saber que la nota es un resumen.
    assert "solo un resumen" in note


def test_la_nota_no_lleva_direcciones_enteras() -> None:
    # Cuestan tokens en cada turno y no hacen falta: alcanza con el sitio.
    assert "/boca/partido" not in web_note(BOCA)


def test_la_nota_se_distingue_de_lo_que_se_dijo() -> None:
    note = web_note(BOCA)

    assert note.startswith("[")
    assert note.endswith("]")
    assert "no se dijo en voz alta" in note


def test_la_nota_nombra_las_paginas_que_leyo() -> None:
    content = [
        block(
            "server_tool_use", id="srvtoolu_2", name="web_fetch", input={"url": "https://a.com/x"}
        ),
        block(
            "web_fetch_tool_result",
            tool_use_id="srvtoolu_2",
            content=block(
                "web_fetch_result",
                url="https://a.com/x",
                content=block("document", title="Fixture de la Liga"),
            ),
        ),
    ]

    note = web_note(content)

    assert "Fixture de la Liga" in note
    assert "a.com" in note


def test_si_la_busqueda_fallo_la_nota_lo_dice() -> None:
    content = [
        search("srvtoolu_1", "clima"),
        block(
            "web_search_tool_result",
            tool_use_id="srvtoolu_1",
            content=block("web_search_tool_result_error", error_code="unavailable"),
        ),
    ]

    assert "falló" in web_note(content)


def test_pocas_fuentes_por_busqueda() -> None:
    results = [(f"Nota {n}", f"https://sitio{n}.com", None) for n in range(10)]
    note = web_note([search("srvtoolu_1", "algo"), found("srvtoolu_1", *results)])

    assert "Nota 4" in note
    assert "Nota 5" not in note


def test_el_registro_cuenta_las_busquedas_sin_decir_que_busco(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.INFO, logger="kronos_engine"):
        log_web_use(BOCA)

    assert "buscó en internet" in caplog.text
    # Lo que se buscó es parte de la conversación: es privado.
    assert "Boca" not in caplog.text


def test_con_depuracion_el_registro_dice_que_busco(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="kronos_engine"):
        log_web_use(BOCA)

    assert "último partido de Boca" in caplog.text


def test_el_registro_anota_si_la_busqueda_fallo(caplog: pytest.LogCaptureFixture) -> None:
    content = [
        search("srvtoolu_1", "clima"),
        block(
            "web_search_tool_result",
            tool_use_id="srvtoolu_1",
            content=block("web_search_tool_result_error", error_code="too_many_requests"),
        ),
    ]

    with caplog.at_level(logging.INFO, logger="kronos_engine"):
        log_web_use(content)

    assert "too_many_requests" in caplog.text


def test_sin_buscar_el_registro_no_anota_nada(caplog: pytest.LogCaptureFixture) -> None:
    with caplog.at_level(logging.DEBUG, logger="kronos_engine"):
        log_web_use([block("text", text="Hola.")])

    assert caplog.text == ""
