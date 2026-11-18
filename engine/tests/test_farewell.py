import pytest

from kronos_engine.core.farewell import is_farewell


@pytest.mark.parametrize(
    "text",
    [
        "Chau.",
        "chao",
        "Adiós.",
        "Adios",
        "Hasta luego.",
        "Hasta mañana, Kronos.",
        "Bueno, nos vemos.",
        "Listo, eso es todo, gracias.",
        "Nada más, gracias.",
        "Gracias, chau.",
        "Chau, Kronos, gracias.",
        "Abrí Spotify y chau.",
        "Bye!",
        "Goodbye.",
    ],
)
def test_reconoce_una_despedida(text: str) -> None:
    assert is_farewell(text)


@pytest.mark.parametrize(
    "text",
    [
        "Hola.",
        "Gracias.",
        "¿Qué hora es?",
        # Se despide pero sigue pidiendo algo.
        "Chau, pero antes abrí Spotify.",
        # Pregunta por la palabra, no se despide.
        "¿Cómo se dice chau en inglés?",
        "Decile adiós a mi hermano por WhatsApp.",
        # Una palabra que contiene una despedida.
        "Abrí la carpeta Chaumont.",
        "",
    ],
)
def test_no_confunde_otras_frases_con_una_despedida(text: str) -> None:
    assert not is_farewell(text)
