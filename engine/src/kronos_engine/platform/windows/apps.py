"""Windows: las aplicaciones del menú Inicio y las ventanas abiertas."""

import json
import logging
import subprocess
import threading
import time

from kronos_engine.core.platform import App, Window
from kronos_engine.platform.windows import open_windows

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

    def windows(self) -> list[Window]:
        return open_windows.list_windows()

    def close_window(self, window: Window) -> None:
        open_windows.close_window(window)
