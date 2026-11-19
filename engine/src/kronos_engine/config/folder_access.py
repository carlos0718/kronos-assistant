"""Las carpetas que Kronos puede mirar, guardadas junto con el resto de los ajustes."""

from pathlib import Path

from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.folder_access import FolderAccess, checked
from kronos_engine.core.platform import Folder


class StoredFolderAccess:
    """Implementa `FolderAccessControl` sobre `config.toml`."""

    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def get(self) -> FolderAccess:
        settings = self._store.load()
        return FolderAccess(
            frozenset(Folder(name) for name in settings.folders_known),
            tuple(Path(path) for path in settings.folders_extra),
            settings.folder_depth,
        )

    def set(self, access: FolderAccess) -> None:
        access = checked(access)
        self._store.update(
            # En el orden de siempre: el archivo no cambia si no cambió lo elegido.
            folders_known=tuple(folder.value for folder in Folder if folder in access.known),
            folders_extra=tuple(str(path) for path in access.extra),
            folder_depth=access.depth,
        )
