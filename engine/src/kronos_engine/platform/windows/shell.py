"""La terminal de Windows: ejecuta comandos de PowerShell."""

import asyncio
import contextlib
import logging
from pathlib import Path

from kronos_engine.core.platform import CommandResult

log = logging.getLogger(__name__)

# CREATE_NO_WINDOW: sin abrir una ventana de consola en la pantalla del usuario.
_NO_WINDOW = 0x08000000
# Para que lo que escribe PowerShell llegue en UTF-8 y no en la página de códigos de la consola.
_UTF8 = "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "


class PowerShell:
    """Corre cada comando en un PowerShell nuevo, con los permisos de Kronos (no admin)."""

    async def run(self, command: str, seconds: float) -> CommandResult:
        process = await asyncio.create_subprocess_exec(
            "powershell.exe",
            "-NoProfile",
            "-NonInteractive",
            "-Command",
            _UTF8 + command,
            stdin=asyncio.subprocess.DEVNULL,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.STDOUT,
            cwd=Path.home(),
            creationflags=_NO_WINDOW,
        )
        try:
            output, _ = await asyncio.wait_for(process.communicate(), seconds)
        except TimeoutError:
            await _kill_tree(process)
            # Lo que alcanzó a escribir antes de cortarse.
            partial = b""
            with contextlib.suppress(Exception):
                partial = await asyncio.wait_for(_drain(process), 2)
            return CommandResult(partial.decode("utf-8", errors="replace"), None)
        return CommandResult(output.decode("utf-8", errors="replace"), process.returncode)


async def _drain(process: asyncio.subprocess.Process) -> bytes:
    return await process.stdout.read() if process.stdout else b""


async def _kill_tree(process: asyncio.subprocess.Process) -> None:
    """Corta el comando y todo lo que lanzó: `kill` solo mata el PowerShell."""
    killer = await asyncio.create_subprocess_exec(
        "taskkill",
        "/T",
        "/F",
        "/PID",
        str(process.pid),
        stdout=asyncio.subprocess.DEVNULL,
        stderr=asyncio.subprocess.DEVNULL,
        creationflags=_NO_WINDOW,
    )
    await killer.wait()
    with contextlib.suppress(ProcessLookupError):
        process.kill()
    await process.wait()
