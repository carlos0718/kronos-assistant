"""Los niveles de permiso que el usuario cambió, guardados junto con el resto de los ajustes."""

from kronos_engine.config.settings import SettingsStore


class StoredLevels:
    """Implementa `LevelStore` sobre `config.toml`."""

    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def get(self) -> dict[str, int]:
        return dict(self._store.load().tool_levels)

    def set(self, levels: dict[str, int]) -> None:
        self._store.update(tool_levels=dict(levels))
