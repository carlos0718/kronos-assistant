import asyncio
import sys

import pytest

pytestmark = pytest.mark.skipif(sys.platform != "win32", reason="Es la terminal de Windows.")


def test_ejecuta_un_comando_real_y_devuelve_lo_que_escribio() -> None:
    from kronos_engine.platform.windows.shell import PowerShell

    result = asyncio.run(PowerShell().run("Write-Output 'canción'; exit 3", 20))

    assert result.exit_code == 3
    assert "canción" in result.output


def test_corta_un_comando_que_tarda_de_mas() -> None:
    from kronos_engine.platform.windows.shell import PowerShell

    result = asyncio.run(PowerShell().run("Write-Output 'empezó'; Start-Sleep 30", 3))

    assert result.exit_code is None
