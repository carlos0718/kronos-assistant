from kronos_engine.core.sentences import SentenceSplitter


def feed_all(splitter: SentenceSplitter, *chunks: str) -> list[str]:
    return [sentence for chunk in chunks for sentence in splitter.feed(chunk)]


def test_no_entrega_una_frase_sin_terminar() -> None:
    splitter = SentenceSplitter()
    assert splitter.feed("Hola, ¿cómo") == []


def test_entrega_la_frase_cuando_llega_el_espacio_siguiente() -> None:
    splitter = SentenceSplitter()
    assert feed_all(splitter, "Hola.", " Soy", " Kronos.") == ["Hola."]
    assert splitter.flush() == "Soy Kronos."


def test_corta_por_punto_interrogacion_y_exclamacion() -> None:
    splitter = SentenceSplitter()
    assert splitter.feed("¿Estás ahí? ¡Claro! Aquí estoy. ") == [
        "¿Estás ahí?",
        "¡Claro!",
        "Aquí estoy.",
    ]


def test_no_corta_los_decimales() -> None:
    splitter = SentenceSplitter()
    assert splitter.feed("Pi vale 3.14 más o menos. ") == ["Pi vale 3.14 más o menos."]


def test_los_puntos_suspensivos_cuentan_como_un_solo_corte() -> None:
    splitter = SentenceSplitter()
    assert splitter.feed("A ver... Listo. ") == ["A ver...", "Listo."]


def test_el_salto_de_linea_tambien_corta() -> None:
    splitter = SentenceSplitter()
    assert splitter.feed("Primero\nSegundo\n") == ["Primero", "Segundo"]


def test_flush_devuelve_el_resto_y_vacia_el_buffer() -> None:
    splitter = SentenceSplitter()
    splitter.feed("Sin punto final")
    assert splitter.flush() == "Sin punto final"
    assert splitter.flush() is None
