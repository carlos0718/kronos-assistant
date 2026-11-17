"""La pausa de fin de frase, guardada junto con el resto de los ajustes."""

from kronos_engine.config.settings import SettingsStore


class StoredEndPause:
    """Implementa `EndPauseControl` sobre `config.toml`."""

    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def get(self) -> int:
        return self._store.load().end_pause_ms

    def set(self, milliseconds: int) -> None:
        self._store.update(end_pause_ms=milliseconds)
