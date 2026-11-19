"""El explorador de archivos de Windows: llevar una ventana ya abierta a otra carpeta.

Así Kronos no abre una ventana nueva por cada carpeta que se le pide.
"""

import logging
import os
import subprocess
from collections.abc import Callable, Sequence
from pathlib import Path
from typing import Any

from kronos_engine.core.platform import Window

log = logging.getLogger(__name__)

# `Shell.Application` da una entrada por cada pestaña del explorador, con la
# ventana a la que pertenece. Con pestañas, la que está a la vista es la que da
# nombre a la ventana; si no se puede saber, se usa la primera. Los datos llegan
# por variables de entorno: la ruta nunca pasa por el intérprete de PowerShell.
_NAVIGATE = """
$tabs = @((New-Object -ComObject Shell.Application).Windows() |
    Where-Object { [long]$_.HWND -eq [long]$env:KRONOS_HWND })
if (-not $tabs) { exit 2 }
$tab = $tabs | Where-Object { $_.LocationName -and $env:KRONOS_TITLE.StartsWith($_.LocationName) } |
    Sort-Object { $_.LocationName.Length } -Descending | Select-Object -First 1
if (-not $tab) { $tab = $tabs[0] }
$tab.Navigate2($env:KRONOS_PATH)
"""
_TIMEOUT = 10
# Sin esto, cada llamada abre una ventana de consola por un instante. Solo existe en Windows.
_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)


def reusable_explorer(windows: Sequence[Window]) -> Window | None:
    """La ventana del explorador que está más adelante, o `None` si no hay ninguna.

    `windows` viene en el orden de la pantalla, de adelante hacia atrás.
    """
    return next((window for window in windows if window.file_browser), None)


def navigate(
    window: Window,
    path: Path,
    run: Callable[..., subprocess.CompletedProcess[Any]] = subprocess.run,
) -> bool:
    """Lleva la ventana del explorador a la carpeta. Devuelve si lo logró."""
    env = {
        **os.environ,
        "KRONOS_HWND": str(window.id),
        "KRONOS_TITLE": window.title,
        "KRONOS_PATH": str(path),
    }
    try:
        result = run(
            ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _NAVIGATE],
            env=env,
            capture_output=True,
            timeout=_TIMEOUT,
            creationflags=_NO_WINDOW,
            check=False,
        )
    except (OSError, subprocess.SubprocessError) as exc:
        log.warning("No se pudo usar la ventana del explorador: %s", exc)
        return False
    return result.returncode == 0
