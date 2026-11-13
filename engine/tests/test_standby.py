import asyncio

from kronos_engine.core.standby import Standby


class FakeWakeWord:
    """Oye el nombre cada vez que se llama a `hear`."""

    def __init__(self, fail_with: Exception | None = None) -> None:
        self._heard: asyncio.Queue[str] = asyncio.Queue()
        self._fail_with = fail_with
        self.waiting = 0

    def hear(self, text: str = "") -> None:
        self._heard.put_nowait(text)

    async def wait(self) -> str:
        if self._fail_with:
            raise self._fail_with
        self.waiting += 1
        try:
            return await self._heard.get()
        finally:
            self.waiting -= 1


class Woken:
    """Hace de conversación: anota con qué la despertaron."""

    def __init__(self) -> None:
        self.heard: list[str] = []

    async def __call__(self, heard: str) -> None:
        self.heard.append(heard)


async def settle() -> None:
    """Deja correr las tareas pendientes."""
    for _ in range(5):
        await asyncio.sleep(0)


def build(wake: FakeWakeWord, enabled: bool = True) -> tuple[Standby, Woken, list[bool]]:
    remembered: list[bool] = []
    standby = Standby(wake, enabled=enabled, remember=remembered.append)
    woken = Woken()
    standby.connect(woken)
    return standby, woken, remembered


def test_en_reposo_espera_el_nombre_y_despierta_con_lo_que_oyo() -> None:
    async def scenario() -> list[str]:
        wake = FakeWakeWord()
        standby, woken, _ = build(wake)
        standby.resume()
        await settle()
        wake.hear("¿qué hora es?")
        await settle()
        return woken.heard

    assert asyncio.run(scenario()) == ["¿qué hora es?"]


def test_mientras_kronos_conversa_no_escucha_su_nombre() -> None:
    async def scenario() -> tuple[int, int, int]:
        wake = FakeWakeWord()
        standby, _, _ = build(wake)
        standby.resume()
        await settle()
        before = wake.waiting
        standby.pause()
        await settle()
        during = wake.waiting
        standby.resume()
        await settle()
        return before, during, wake.waiting

    assert asyncio.run(scenario()) == (1, 0, 1)


def test_apagada_no_abre_el_microfono() -> None:
    async def scenario() -> int:
        wake = FakeWakeWord()
        standby, _, _ = build(wake, enabled=False)
        standby.resume()
        await settle()
        return wake.waiting

    assert asyncio.run(scenario()) == 0


def test_encenderla_y_apagarla_tiene_efecto_al_momento_y_se_recuerda() -> None:
    async def scenario() -> tuple[int, int, list[bool]]:
        wake = FakeWakeWord()
        standby, _, remembered = build(wake, enabled=False)
        standby.resume()
        standby.set_enabled(True)
        await settle()
        on = wake.waiting
        standby.set_enabled(False)
        await settle()
        return on, wake.waiting, remembered

    assert asyncio.run(scenario()) == (1, 0, [True, False])


def test_encenderla_durante_una_conversacion_espera_a_que_termine() -> None:
    async def scenario() -> tuple[int, int]:
        wake = FakeWakeWord()
        standby, _, _ = build(wake, enabled=False)
        standby.resume()
        standby.pause()
        standby.set_enabled(True)
        await settle()
        during = wake.waiting
        standby.resume()
        await settle()
        return during, wake.waiting

    assert asyncio.run(scenario()) == (0, 1)


def test_si_el_microfono_falla_el_motor_sigue() -> None:
    async def scenario() -> list[str]:
        standby, woken, _ = build(FakeWakeWord(fail_with=RuntimeError("sin micrófono")))
        standby.resume()
        await settle()
        standby.pause()
        return woken.heard

    assert asyncio.run(scenario()) == []
