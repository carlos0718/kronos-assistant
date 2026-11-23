"""El volumen general de Windows, el mismo que mueve el ícono de la barra de tareas."""

from collections.abc import Iterator
from contextlib import contextmanager
from typing import Any


@contextmanager
def _endpoint() -> Iterator[Any]:
    # comtypes y pycaw tardan en cargar y solo existen en Windows: se importan al usarlos.
    import comtypes
    from pycaw.pycaw import AudioUtilities  # type: ignore[import-untyped]

    # El audio de Windows (COM) hay que iniciarlo en cada hilo, y la acción corre en uno aparte.
    comtypes.CoInitialize()  # type: ignore[no-untyped-call]
    try:
        # Se pide cada vez: el usuario puede cambiar de parlantes a auriculares entre pedidos.
        device = AudioUtilities.GetSpeakers()
        endpoint = device.EndpointVolume
        try:
            yield endpoint
        finally:
            # Los objetos COM se sueltan antes de cerrar COM en este hilo.
            del endpoint, device
    finally:
        comtypes.CoUninitialize()  # type: ignore[no-untyped-call]


class WindowsVolume:
    def level(self) -> int:
        with _endpoint() as endpoint:
            return round(float(endpoint.GetMasterVolumeLevelScalar()) * 100)

    def set_level(self, percent: int) -> None:
        with _endpoint() as endpoint:
            endpoint.SetMasterVolumeLevelScalar(max(0, min(100, percent)) / 100, None)

    def muted(self) -> bool:
        with _endpoint() as endpoint:
            return bool(endpoint.GetMute())

    def set_muted(self, muted: bool) -> None:
        with _endpoint() as endpoint:
            endpoint.SetMute(int(muted), None)
