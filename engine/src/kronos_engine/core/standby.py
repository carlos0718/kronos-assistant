"""El reposo: mientras Kronos está inactivo, espera a que lo llamen por su nombre.

No sabe de audio: recibe un detector intercambiable (`WakeWord`) y avisa
cuando oyó el nombre. Mientras hay una conversación en curso no escucha, así
no se oye a sí mismo ni compite por el micrófono.
"""

import asyncio
import logging
from collections.abc import Awaitable, Callable
from typing import Protocol

log = logging.getLogger(__name__)


class WakeWord(Protocol):
    async def wait(self) -> str:
        """Espera hasta oír el nombre de Kronos.

        Devuelve lo que el usuario dijo junto con el nombre ("Kronos, ¿qué
        hora es?" → "¿qué hora es?"), o un texto vacío si solo lo nombró. El
        micrófono queda abierto mientras espera y se cierra si se la cancela.
        """
        ...


OnWake = Callable[[str], Awaitable[None]]


class Standby:
    """Enciende y apaga la espera según el ajuste del usuario y el estado de Kronos.

    `remember` guarda el ajuste cuando el usuario lo cambia.
    """

    def __init__(
        self,
        wake: WakeWord,
        enabled: bool = False,
        remember: Callable[[bool], None] | None = None,
    ) -> None:
        self._wake = wake
        self._enabled = enabled
        self._remember = remember
        self._on_wake: OnWake | None = None
        # Arranca en pausa: el servidor la reanuda cuando ya hay bucle de asyncio.
        self._idle = False
        self._task: asyncio.Task[None] | None = None

    def connect(self, on_wake: OnWake) -> None:
        """Indica a quién avisar cuando se oye el nombre."""
        self._on_wake = on_wake

    @property
    def enabled(self) -> bool:
        return self._enabled

    def set_enabled(self, enabled: bool) -> None:
        self._enabled = enabled
        if self._remember:
            self._remember(enabled)
        self._sync()

    def resume(self) -> None:
        """Kronos quedó inactivo: vuelve a esperar su nombre."""
        self._idle = True
        self._sync()

    def pause(self) -> None:
        """Kronos está conversando (o el motor se cierra): deja de escuchar."""
        self._idle = False
        self._sync()

    def _sync(self) -> None:
        wanted = self._enabled and self._idle
        running = self._task is not None and not self._task.done()
        if wanted and not running:
            self._task = asyncio.create_task(self._watch())
        elif not wanted and self._task is not None:
            self._task.cancel()
            self._task = None

    async def _watch(self) -> None:
        try:
            heard = await self._wake.wait()
        except Exception as exc:  # noqa: BLE001 - sin micrófono no hay palabra de activación, pero el motor sigue.
            log.warning("No se puede esperar la palabra de activación: %s", exc)
            return
        # Se suelta la tarea antes de avisar: la conversación que empieza pausa
        # el reposo, y no tiene que cancelar este aviso.
        self._task = None
        # No se registra lo que se dijo: puede ser privado.
        log.info("Oyó su nombre; empieza la conversación.")
        if self._on_wake:
            await self._on_wake(heard)
