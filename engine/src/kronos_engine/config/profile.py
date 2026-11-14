"""El perfil del usuario, guardado junto con el resto de los ajustes."""

from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.profile import Profile


class StoredProfile:
    """Implementa `ProfileControl` sobre `config.toml`."""

    def __init__(self, store: SettingsStore) -> None:
        self._store = store

    def get(self) -> Profile:
        settings = self._store.load()
        return Profile(name=settings.user_name or "", about=settings.user_about or "")

    def set(self, profile: Profile) -> None:
        # Lo que queda vacío no se escribe en el archivo.
        self._store.update(user_name=profile.name or None, user_about=profile.about or None)
