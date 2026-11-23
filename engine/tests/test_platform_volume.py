import asyncio
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Es el audio de Windows.")


@pytest.mark.skipif(sys.platform != "win32", reason="Es el audio de Windows.")
def test_lee_el_volumen_real_desde_otro_hilo() -> None:
    # La acción lo usa desde un hilo aparte: el audio de Windows (COM) tiene que andar ahí.
    from kronos_engine.platform.windows.volume import WindowsVolume

    volume = WindowsVolume()

    level = asyncio.run(asyncio.to_thread(volume.level))

    assert 0 <= level <= 100
    assert isinstance(volume.muted(), bool)


def test_poner_el_mismo_nivel_no_lo_cambia() -> None:
    # No se cambia el volumen real de quien corre las pruebas: se vuelve a poner el que tiene.
    from kronos_engine.platform.windows.volume import WindowsVolume

    volume = WindowsVolume()
    before = volume.level()

    asyncio.run(asyncio.to_thread(volume.set_level, before))

    assert volume.level() == before
