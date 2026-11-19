"""Ventanas abiertas en Windows: cuáles hay a la vista y cómo pedirles que se cierren."""

import ctypes
import sys
from collections.abc import Callable
from typing import Any

from kronos_engine.core.platform import Window

_WM_CLOSE = 0x0010
_SW_RESTORE = 9
_GW_OWNER = 4
_GWL_EXSTYLE = -20
_WS_EX_TOOLWINDOW = 0x80
_DWMWA_CLOAKED = 14
# El escritorio y la barra de tareas también son ventanas: no se tocan.
_SHELL_CLASSES = {"Progman", "WorkerW", "Shell_TrayWnd", "Shell_SecondaryTrayWnd"}
# La clase de las ventanas del explorador de archivos.
_EXPLORER_CLASS = "CabinetWClass"


def list_windows() -> list[Window]:
    """Las ventanas principales que el usuario ve, como las que muestra Alt+Tab."""
    if sys.platform != "win32":
        return []
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    dwmapi = ctypes.windll.dwmapi
    user32.GetWindow.restype = wintypes.HWND
    found: list[Window] = []

    def text(read: Callable[..., Any], hwnd: int, size: int) -> str:
        buffer = ctypes.create_unicode_buffer(size)
        read(hwnd, buffer, size)
        return buffer.value

    def on_screen(hwnd: int) -> bool:
        if not user32.IsWindowVisible(hwnd) or user32.GetWindow(hwnd, _GW_OWNER):
            return False
        if user32.GetWindowLongW(hwnd, _GWL_EXSTYLE) & _WS_EX_TOOLWINDOW:
            return False
        # Windows deja «visibles» ventanas de aplicaciones de la tienda que en
        # realidad están ocultas (suspendidas o en otro escritorio).
        cloaked = wintypes.DWORD()
        dwmapi.DwmGetWindowAttribute(
            wintypes.HWND(hwnd), _DWMWA_CLOAKED, ctypes.byref(cloaked), ctypes.sizeof(cloaked)
        )
        return not cloaked.value

    def visit(hwnd: int, _: int) -> bool:
        window_class = text(user32.GetClassNameW, hwnd, 256) if on_screen(hwnd) else ""
        if window_class and window_class not in _SHELL_CLASSES:
            length = user32.GetWindowTextLengthW(hwnd)
            if length and (title := text(user32.GetWindowTextW, hwnd, length + 1).strip()):
                found.append(Window(title, hwnd, file_browser=window_class == _EXPLORER_CLASS))
        return True

    callback = ctypes.WINFUNCTYPE(wintypes.BOOL, wintypes.HWND, wintypes.LPARAM)
    user32.EnumWindows(callback(visit), 0)
    return found


def close_window(window: Window) -> None:
    """Le manda a la ventana el mismo aviso que la X: la aplicación decide cómo cerrarse."""
    if sys.platform != "win32":
        return
    from ctypes import wintypes

    post = ctypes.windll.user32.PostMessageW
    post.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
    post(window.id, _WM_CLOSE, 0, 0)


def focus_window(window: Window) -> None:
    """Trae la ventana al frente; si estaba minimizada, la restaura."""
    if sys.platform != "win32":
        return
    from ctypes import wintypes

    user32 = ctypes.windll.user32
    hwnd = wintypes.HWND(window.id)
    if user32.IsIconic(hwnd):
        user32.ShowWindow(hwnd, _SW_RESTORE)
    # Windows solo deja traer una ventana al frente al programa que el usuario
    # está usando. Unirse por un momento a ese programa levanta la traba; si no
    # alcanza, Windows hace parpadear la ventana en la barra de tareas.
    current = ctypes.windll.kernel32.GetCurrentThreadId()
    active = user32.GetWindowThreadProcessId(user32.GetForegroundWindow(), None)
    joined = active and active != current and user32.AttachThreadInput(current, active, True)
    try:
        user32.BringWindowToTop(hwnd)
        user32.SetForegroundWindow(hwnd)
    finally:
        if joined:
            user32.AttachThreadInput(current, active, False)
