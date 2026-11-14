"""La espera después de responder, guardada junto con el resto de los ajustes."""

from kronos_engine.config.settings import SettingsStore


class StoredFollowUp:
    """Implementa `FollowUpControl` sobre `config.toml`."""

    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def get(self) -> int:
        return self._store.load().follow_up_seconds

    def set(self, seconds: int) -> None:
        self._store.update(follow_up_seconds=seconds)
