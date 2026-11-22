"""El reconocedor de voz elegido, guardado junto con el resto de los ajustes."""

from collections.abc import Callable

from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.recognizer import DEFAULT_RECOGNIZER, checked


class StoredRecognizer:
    """Implementa `RecognizerControl` sobre `config.toml`.

    Si el usuario no eligió nada, vale `from_env` (la variable KRONOS_STT_MODEL, para
    probar un modelo sin pasar por la configuración) y, si tampoco está, el de fábrica.
    `on_change` se llama después de guardar una elección.
    """

    def __init__(
        self,
        store: SettingsStore,
        has_key: Callable[[], bool],
        from_env: str = "",
        on_change: Callable[[], None] = lambda: None,
    ) -> None:
        self._store = store
        self._has_key = has_key
        self._from_env = from_env.strip()
        self._on_change = on_change

    def get(self) -> str:
        return self._store.load().stt_model or self._from_env or DEFAULT_RECOGNIZER

    def set(self, name: str) -> None:
        self._store.update(stt_model=checked(name))
        self._on_change()

    def has_key(self) -> bool:
        return self._has_key()
