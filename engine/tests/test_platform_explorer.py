import subprocess
from pathlib import Path
from typing import Any

from kronos_engine.core.platform import Window
from kronos_engine.platform.windows.explorer import navigate, reusable_explorer

NOTEPAD = Window("Sin título - Bloc de notas", 1)
DOWNLOADS = Window("Descargas - Explorador de archivos", 2, file_browser=True)
DOCUMENTS = Window("Documentos - Explorador de archivos", 3, file_browser=True)


class FakeRun:
    def __init__(self, returncode: int = 0, error: Exception | None = None) -> None:
        self._returncode = returncode
        self._error = error
        self.calls: list[tuple[list[str], dict[str, Any]]] = []

    def __call__(self, command: list[str], **options: Any) -> subprocess.CompletedProcess[str]:
        self.calls.append((command, options))
        if self._error:
            raise self._error
        return subprocess.CompletedProcess(command, self._returncode)


def test_usa_la_ventana_del_explorador_que_esta_mas_adelante() -> None:
    # Las ventanas vienen en el orden de la pantalla: la primera es la de más adelante.
    assert reusable_explorer([NOTEPAD, DOWNLOADS, DOCUMENTS]) == DOWNLOADS


def test_sin_ventanas_del_explorador_no_hay_cual_usar() -> None:
    assert reusable_explorer([NOTEPAD]) is None


def test_lleva_la_ventana_a_la_carpeta_sin_poner_la_ruta_en_el_comando() -> None:
    run = FakeRun()
    target = Path("C:/Users/Ana/Documents/Mis proyectos & cosas")

    assert navigate(DOWNLOADS, target, run=run)

    command, options = run.calls[0]
    # La ruta va por una variable de entorno: así no la interpreta PowerShell.
    assert str(target) not in " ".join(command)
    assert options["env"]["KRONOS_PATH"] == str(target)
    assert options["env"]["KRONOS_HWND"] == "2"
    # Con pestañas, la activa es la que da nombre a la ventana.
    assert options["env"]["KRONOS_TITLE"] == DOWNLOADS.title


def test_si_powershell_no_encuentra_la_ventana_avisa_que_no_pudo() -> None:
    assert not navigate(DOWNLOADS, Path("C:/x"), run=FakeRun(returncode=2))


def test_si_powershell_falla_o_tarda_avisa_que_no_pudo() -> None:
    assert not navigate(DOWNLOADS, Path("C:/x"), run=FakeRun(error=OSError("no")))
    timeout = subprocess.TimeoutExpired("powershell", 10)
    assert not navigate(DOWNLOADS, Path("C:/x"), run=FakeRun(error=timeout))
