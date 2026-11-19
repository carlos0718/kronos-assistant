from kronos_engine.agent.instructions import INSTRUCTIONS, instructions_for


def test_sin_perfil_son_las_instrucciones_de_siempre() -> None:
    assert instructions_for("", "") == INSTRUCTIONS
    assert instructions_for("  ", "\n") == INSTRUCTIONS


def test_con_nombre_le_pide_al_modelo_que_lo_use() -> None:
    result = instructions_for("Carlos", "")

    assert result.startswith(INSTRUCTIONS)
    assert "Carlos" in result


def test_con_descripcion_se_la_pasa_al_modelo() -> None:
    result = instructions_for("", "Programo y me gusta correr.")

    assert "Programo y me gusta correr." in result


def test_el_nombre_no_se_repite_en_cada_frase() -> None:
    # Llamar al usuario por su nombre todo el tiempo suena artificial en voz alta.
    assert "no lo repitas" in instructions_for("Carlos", "").lower()


def test_lo_que_sabe_lo_contesta_sin_internet() -> None:
    # qwen3:8b se negaba a explicar qué es un agujero negro: tomaba la regla de
    # «no podés consultar internet» como «no podés contestar nada que no sea una acción».
    text = INSTRUCTIONS.lower()

    assert "conocimiento general" in text
    assert "no necesitás internet" in text


def test_lo_que_busca_en_internet_lo_cuenta_corto_y_sin_leer_direcciones() -> None:
    # Las respuestas se dicen en voz alta: una dirección web no se puede leer.
    text = INSTRUCTIONS.lower()

    assert "internet" in text
    assert "direcciones web" in text
