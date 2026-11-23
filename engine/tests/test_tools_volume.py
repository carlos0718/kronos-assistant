import asyncio
from typing import Any

import pytest

from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.volume import VolumeTool


class FakeVolume:
    def __init__(self, level: int = 40, muted: bool = False) -> None:
        self._level = level
        self._muted = muted

    def level(self) -> int:
        return self._level

    def set_level(self, percent: int) -> None:
        self._level = percent

    def muted(self) -> bool:
        return self._muted

    def set_muted(self, muted: bool) -> None:
        self._muted = muted


def act(volume: FakeVolume, **arguments: Any) -> str:
    return asyncio.run(VolumeTool(volume).run(arguments))


def test_no_pide_permiso() -> None:
    assert VolumeTool(FakeVolume()).level == PermissionLevel.NORMAL


def test_pone_el_volumen_en_un_nivel() -> None:
    volume = FakeVolume(40)

    result = act(volume, action="set", level=65)

    assert volume.level() == 65
    assert "65" in result


@pytest.mark.parametrize(("asked", "expected"), [(150, 100), (-5, 0)])
def test_el_nivel_queda_entre_0_y_100(asked: int, expected: int) -> None:
    volume = FakeVolume(40)

    act(volume, action="set", level=asked)

    assert volume.level() == expected


def test_sube_y_baja_de_a_diez_si_no_dicen_cuanto() -> None:
    volume = FakeVolume(40)

    act(volume, action="up")
    assert volume.level() == 50

    act(volume, action="down")
    act(volume, action="down")
    assert volume.level() == 30


def test_sube_y_baja_lo_que_piden() -> None:
    volume = FakeVolume(40)

    act(volume, action="up", amount=25)

    assert volume.level() == 65


def test_no_pasa_de_100_ni_baja_de_0() -> None:
    volume = FakeVolume(95)
    act(volume, action="up", amount=20)
    assert volume.level() == 100

    act(volume, action="down", amount=300)
    assert volume.level() == 0


def test_un_salto_de_golpe_no_pasa_de_cierto_tope() -> None:
    # Subir mucho de una vez asusta: para eso está «poné el volumen en…».
    volume = FakeVolume(10)

    act(volume, action="up", amount=90)

    assert volume.level() == 40


def test_silencia_y_reactiva_el_sonido() -> None:
    volume = FakeVolume(40)

    assert "silenci" in act(volume, action="mute")
    assert volume.muted()

    act(volume, action="unmute")
    assert not volume.muted()
    assert volume.level() == 40


def test_subir_el_volumen_reactiva_el_sonido_silenciado() -> None:
    volume = FakeVolume(40, muted=True)

    act(volume, action="up")

    assert not volume.muted()


def test_dice_como_esta_sin_cambiar_nada() -> None:
    volume = FakeVolume(40)

    result = act(volume, action="get")

    assert "40" in result
    assert volume.level() == 40


def test_dice_si_esta_silenciado() -> None:
    assert "silenciado" in act(FakeVolume(40, muted=True), action="get")


def test_poner_el_nivel_exige_un_numero() -> None:
    with pytest.raises(ToolError, match="nivel"):
        act(FakeVolume(), action="set")
    with pytest.raises(ToolError, match="nivel"):
        act(FakeVolume(), action="set", level="fuerte")


def test_una_accion_desconocida_se_rechaza() -> None:
    with pytest.raises(ToolError):
        act(FakeVolume(), action="explotar")
