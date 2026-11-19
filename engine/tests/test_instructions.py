from datetime import datetime, timedelta, timezone

from kronos_engine.agent.instructions import INSTRUCTIONS, instructions_for

ARGENTINA = timezone(timedelta(hours=-3), "Hora estándar de Argentina")
NOW = datetime(2026, 11, 19, 15, 42, tzinfo=ARGENTINA)


def test_sin_perfil_son_las_instrucciones_de_siempre_con_la_fecha() -> None:
    result = instructions_for("", "", NOW)

    assert result.startswith(INSTRUCTIONS)
    assert "Sobre el usuario" not in result
    assert instructions_for("  ", "\n", NOW) == result


def test_sabe_que_dia_es_y_en_que_zona_horaria_esta_el_usuario() -> None:
    # Sin la fecha, Claude no sabía si «el último partido» ya se había jugado.
    result = instructions_for("", "", NOW)

    assert "jueves 19 de noviembre de 2026" in result
    assert "UTC-3" in result


def test_la_hora_exacta_la_pide_con_la_accion() -> None:
    # La hora cambia a cada minuto: en las instrucciones haría que Claude no
    # pudiera reusar la conversación ya procesada y cobraría todo de nuevo.
    result = instructions_for("", "", NOW)

    assert "15:42" not in result
    assert "current_time" in result


def test_las_fechas_de_internet_las_compara_con_hoy() -> None:
    text = INSTRUCTIONS.lower()

    assert "el último" in text
    assert "zona horaria del usuario" in text


def test_con_nombre_le_pide_al_modelo_que_lo_use() -> None:
    result = instructions_for("Carlos", "", NOW)

    assert result.startswith(INSTRUCTIONS)
    assert "Carlos" in result


def test_con_descripcion_se_la_pasa_al_modelo() -> None:
    result = instructions_for("", "Programo y me gusta correr.", NOW)

    assert "Programo y me gusta correr." in result


def test_el_nombre_no_se_repite_en_cada_frase() -> None:
    # Llamar al usuario por su nombre todo el tiempo suena artificial en voz alta.
    assert "no lo repitas" in instructions_for("Carlos", "", NOW).lower()


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
