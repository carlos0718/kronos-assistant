"""Windows: las aplicaciones del menú Inicio, las carpetas del usuario y las ventanas abiertas."""

import json
import logging
import os
import subprocess
import sys
import threading
import time
from collections.abc import Callable, Sequence, Set
from pathlib import Path

from kronos_engine.core.platform import App, Folder, Window
from kronos_engine.platform.windows import known_folders, open_windows

log = logging.getLogger(__name__)

# `Get-StartApps` lista lo mismo que el menú Inicio, incluidas las aplicaciones
# de la tienda, que no tienen un .exe que se pueda ejecutar por su ruta.
_LIST_COMMAND = (
    "[Console]::OutputEncoding = [Text.Encoding]::UTF8; Get-StartApps | ConvertTo-Json -Compress"
)
_LIST_TIMEOUT = 20
# Listar tarda cerca de un segundo: la lista se guarda y se renueva cada tanto,
# por si el usuario instaló algo.
_CACHE_SECONDS = 300
# Sin esto, cada llamada abre una ventana de consola por un instante. Solo existe en Windows.
_NO_WINDOW: int = getattr(subprocess, "CREATE_NO_WINDOW", 0)

# Cuánto se espera a que el explorador muestre la carpeta, y cada cuánto se mira.
_FOLDER_WAIT = 3.0
_FOLDER_STEP = 0.1


def new_window(
    before: Set[int],
    windows: Callable[[], Sequence[Window]],
    timeout: float = _FOLDER_WAIT,
    sleep: Callable[[float], None] = time.sleep,
) -> Window | None:
    """La primera ventana que aparece y no estaba en `before`, o `None` si no aparece a tiempo."""
    waited = 0.0
    while True:
        if fresh := [window for window in windows() if window.id not in before]:
            return fresh[0]
        if waited >= timeout:
            return None
        sleep(_FOLDER_STEP)
        waited += _FOLDER_STEP


def parse_apps(output: str) -> list[App]:
    """Convierte la salida de `Get-StartApps | ConvertTo-Json` en aplicaciones."""
    try:
        entries = json.loads(output)
    except ValueError:
        return []
    if isinstance(entries, dict):
        # Con un solo elemento, PowerShell no arma una lista.
        entries = [entries]
    apps: list[App] = []
    for entry in entries if isinstance(entries, list) else []:
        if not isinstance(entry, dict):
            continue
        name, app_id = entry.get("Name"), entry.get("AppID")
        if isinstance(name, str) and isinstance(app_id, str) and name.strip() and app_id.strip():
            apps.append(App(name.strip(), app_id.strip()))
    return apps


class WindowsPlatform:
    def __init__(self) -> None:
        self._apps: list[App] = []
        self._listed_at: float | None = None
        self._lock = threading.Lock()

    def preload(self) -> None:
        """Lista las aplicaciones en segundo plano, mientras el usuario todavía no habló."""
        threading.Thread(target=self.apps, daemon=True).start()

    def apps(self) -> list[App]:
        with self._lock:
            fresh = (
                self._listed_at is not None and time.monotonic() - self._listed_at < _CACHE_SECONDS
            )
            if not fresh:
                # Si falla, queda la lista anterior: mejor vieja que vacía.
                self._apps = self._list() or self._apps
                self._listed_at = time.monotonic()
            return list(self._apps)

    def _list(self) -> list[App]:
        try:
            result = subprocess.run(
                ["powershell.exe", "-NoProfile", "-NonInteractive", "-Command", _LIST_COMMAND],
                capture_output=True,
                encoding="utf-8",
                timeout=_LIST_TIMEOUT,
                creationflags=_NO_WINDOW,
                check=False,
            )
        except (OSError, subprocess.SubprocessError) as exc:
            log.warning("No se pudieron listar las aplicaciones: %s", exc)
            return []
        return parse_apps(result.stdout or "")

    def open_app(self, app: App) -> None:
        # El explorador abre cualquier entrada del menú Inicio por su identificador.
        # Va como un solo argumento, sin pasar por un intérprete de comandos.
        subprocess.Popen(["explorer.exe", f"shell:AppsFolder\\{app.id}"], creationflags=_NO_WINDOW)

    def folder_path(self, folder: Folder) -> Path:
        return known_folders.known_folder(folder)

    def open_path(self, path: Path) -> None:
        # Abrir un archivo lo ejecutaría: solo se abren carpetas.
        if sys.platform != "win32" or not path.is_dir():
            return
        before = {window.id for window in self.windows()}
        # Como un doble clic: sin pasar la ruta por un intérprete de comandos.
        os.startfile(path)
        # La ventana la crea el explorador que ya estaba corriendo, y Windows no
        # la deja pasar al frente: queda atrás, parpadeando en la barra de
        # tareas, y una barra que se oculta sola no se oculta. Se la trae al
        # frente como si el usuario la hubiera tocado.
        if window := new_window(before, self.windows):
            self.focus_window(window)

    def windows(self) -> list[Window]:
        return open_windows.list_windows()

    def close_window(self, window: Window) -> None:
        open_windows.close_window(window)

    def focus_window(self, window: Window) -> None:
        open_windows.focus_window(window)
