import pytest

from kronos_engine.voice.speakable import speakable


@pytest.mark.parametrize(
    ("text", "spoken"),
    [
        ("Son las tres.", "Son las tres."),
        ("Esto es **muy** importante.", "Esto es muy importante."),
        ("Usá el comando `ls` para listar.", "Usá el comando ls para listar."),
        ("# Título", "Título"),
        ("- Primer punto", "Primer punto"),
        ("¡Hola! 😊 ¿Cómo estás?", "¡Hola! ¿Cómo estás?"),
        ("Mirá   esto\n\nya.", "Mirá esto ya."),
        ("Cuesta 3,50 y pesa 2.5 kg.", "Cuesta 3,50 y pesa 2.5 kg."),
        ("¿El 50% de 10? Es 5.", "¿El 50% de 10? Es 5."),
    ],
)
def test_deja_solo_lo_que_se_puede_decir(text: str, spoken: str) -> None:
    assert speakable(text) == spoken


@pytest.mark.parametrize("text", ["", "   ", "😊", "**", "- "])
def test_si_no_queda_nada_para_decir_devuelve_vacio(text: str) -> None:
    assert speakable(text) == ""
