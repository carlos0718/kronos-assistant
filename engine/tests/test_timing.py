from kronos_engine.core.timing import Step, TurnTimer


class FakeClock:
    """Devuelve, en orden, las horas que se le indican."""

    def __init__(self, *times: float) -> None:
        self._times = list(times)

    def __call__(self) -> float:
        return self._times.pop(0)


def test_resume_cuanto_tardo_cada_paso() -> None:
    timer = TurnTimer(FakeClock(10.0, 10.62, 11.5, 11.81))

    timer.mark(Step.SPEECH_END)
    timer.mark(Step.TRANSCRIBED)
    timer.mark(Step.FIRST_SENTENCE)
    timer.mark(Step.FIRST_SOUND)

    assert timer.summary() == "transcribir 0,62 s · modelo 0,88 s · voz 0,31 s · total 1,81 s"


def test_sin_escucha_el_total_cuenta_desde_que_hay_texto() -> None:
    # Al llamarlo por su nombre el pedido ya viene transcrito.
    timer = TurnTimer(FakeClock(5.0, 6.0, 6.25))

    timer.mark(Step.TRANSCRIBED)
    timer.mark(Step.FIRST_SENTENCE)
    timer.mark(Step.FIRST_SOUND)

    assert timer.summary() == "modelo 1,00 s · voz 0,25 s · total 1,25 s"


def test_si_kronos_no_llego_a_hablar_no_hay_resumen() -> None:
    timer = TurnTimer(FakeClock(1.0, 2.0))

    timer.mark(Step.SPEECH_END)
    timer.mark(Step.TRANSCRIBED)

    assert timer.summary() is None


def test_de_un_paso_repetido_vale_la_primera_vez() -> None:
    # La primera frase es la que define la demora; las siguientes no cuentan.
    timer = TurnTimer(FakeClock(1.0, 2.0, 3.0))

    timer.mark(Step.TRANSCRIBED)
    timer.mark(Step.FIRST_SOUND)
    timer.mark(Step.FIRST_SOUND)

    assert timer.summary() == "total 1,00 s"
