"""Qué modelo responde, guardado con el resto de los ajustes; la clave, aparte."""

from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.model_choice import OLLAMA, ModelChoice, SecretStore, checked


class StoredModelChoice:
    """Implementa `ModelControl`: la elección en `config.toml`, la clave en `secrets`.

    La clave no se escribe en ningún archivo: `config.toml` es texto plano.
    """

    def __init__(self, store: SettingsStore, secrets: SecretStore) -> None:
        self._store = store
        self._secrets = secrets

    def get(self) -> ModelChoice:
        settings = self._store.load()
        return ModelChoice(settings.llm_provider, settings.llm_model)

    def set(self, choice: ModelChoice) -> None:
        choice = checked(choice)
        self._store.update(llm_provider=choice.provider, llm_model=choice.model)

    def key(self, provider: str) -> str | None:
        return self._secrets.read(_key_name(provider))

    def set_key(self, provider: str, key: str) -> None:
        name = _key_name(provider)
        if key := key.strip():
            self._secrets.write(name, key)
        else:
            self._secrets.delete(name)


def _key_name(provider: str) -> str:
    checked(ModelChoice(provider))
    if provider == OLLAMA:
        raise ValueError("Ollama corre en la computadora: no usa clave.")
    return f"Kronos/{provider}"
