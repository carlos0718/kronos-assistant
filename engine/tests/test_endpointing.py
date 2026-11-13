from kronos_engine.voice.endpointing import EndpointConfig, Endpointer, Verdict

# Con cuadros de 100 ms las cuentas de los tests se leen fácil.
CONFIG = EndpointConfig(
    frame_ms=100,
    min_speech_ms=200,
    end_silence_ms=300,
    start_timeout_ms=1000,
    max_utterance_ms=2000,
    pre_roll_ms=200,
)

VOICE = 0.9
SILENCE = 0.05


def feed_all(endpointer: Endpointer, *probabilities: float) -> list[Verdict]:
    return [endpointer.feed(p) for p in probabilities]


def test_espera_mientras_no_hay_voz() -> None:
    endpointer = Endpointer(CONFIG)
    assert feed_all(endpointer, SILENCE, SILENCE) == [Verdict.WAITING, Verdict.WAITING]


def test_un_ruido_corto_no_cuenta_como_voz() -> None:
    endpointer = Endpointer(CONFIG)
    assert feed_all(endpointer, VOICE, SILENCE, SILENCE) == [Verdict.WAITING] * 3


def test_empieza_cuando_la_voz_dura_lo_suficiente() -> None:
    endpointer = Endpointer(CONFIG)
    assert feed_all(endpointer, SILENCE, VOICE, VOICE) == [
        Verdict.WAITING,
        Verdict.WAITING,
        Verdict.SPEAKING,
    ]


def test_termina_tras_el_silencio_final() -> None:
    endpointer = Endpointer(CONFIG)
    verdicts = feed_all(endpointer, VOICE, VOICE, VOICE, SILENCE, SILENCE, SILENCE)
    assert verdicts[-2:] == [Verdict.SPEAKING, Verdict.DONE]


def test_una_pausa_corta_no_termina_la_frase() -> None:
    endpointer = Endpointer(CONFIG)
    verdicts = feed_all(endpointer, VOICE, VOICE, SILENCE, SILENCE, VOICE, SILENCE, SILENCE)
    assert Verdict.DONE not in verdicts


def test_si_nadie_habla_se_rinde_al_vencer_el_plazo() -> None:
    endpointer = Endpointer(CONFIG)
    verdicts = feed_all(endpointer, *[SILENCE] * 10)
    assert verdicts[-2:] == [Verdict.WAITING, Verdict.NO_SPEECH]


def test_corta_una_frase_que_no_termina_nunca() -> None:
    endpointer = Endpointer(CONFIG)
    # El máximo son 2000 ms: 20 cuadros desde que empezó la voz.
    verdicts = feed_all(endpointer, *[VOICE] * 20)
    assert verdicts[-1] is Verdict.DONE
    assert Verdict.DONE not in verdicts[:-1]


def test_el_audio_util_incluye_un_margen_antes_de_la_voz() -> None:
    endpointer = Endpointer(CONFIG)
    feed_all(endpointer, *[SILENCE] * 5, VOICE, VOICE)
    # La voz empezó en el cuadro 5; el margen de 200 ms son 2 cuadros.
    assert endpointer.first_frame == 3


def test_el_margen_no_se_sale_del_principio() -> None:
    endpointer = Endpointer(CONFIG)
    feed_all(endpointer, SILENCE, VOICE, VOICE)
    assert endpointer.first_frame == 0
