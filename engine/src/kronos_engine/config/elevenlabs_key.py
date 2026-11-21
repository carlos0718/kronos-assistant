"""La clave de ElevenLabs, en el almacén de claves (en Windows, el Administrador de credenciales).

No va en `config.toml`, que es texto plano. Antes se ponía en el `.env`:
`move_from_env` la pasa de lugar al arrancar, para no perderla.
"""

import logging
from collections.abc import Callable

from kronos_engine.core.model_choice import SecretStore

log = logging.getLogger(__name__)

# Con este nombre se ve en el Administrador de credenciales, junto a «Kronos/anthropic».
NAME = "Kronos/elevenlabs"


class StoredElevenLabsKey:
    """Implementa `CloudKey`. `on_change` se llama cada vez que se guarda o se borra."""

    def __init__(self, secrets: SecretStore, on_change: Callable[[], None] = lambda: None) -> None:
        self._secrets = secrets
        self._on_change = on_change

    def get(self) -> str:
        return self._secrets.read(NAME) or ""

    def set(self, key: str) -> None:
        if key := key.strip():
            self._secrets.write(NAME, key)
        else:
            self._secrets.delete(NAME)
        self._on_change()


def saved_or_env(secrets: SecretStore, from_env: str) -> str:
    """Para los scripts de medición: la clave de la pestaña Voz o, si no hay, la del `.env`."""
    try:
        saved = secrets.read(NAME)
    except OSError:
        # Fuera de Windows no hay Administrador de credenciales.
        saved = None
    return saved or from_env.strip()


def move_from_env(key: StoredElevenLabsKey, from_env: str) -> None:
    """Guarda la clave del `.env` si no había otra: la cargada en la app gana."""
    if not (from_env := from_env.strip()) or key.get():
        return
    key.set(from_env)
    log.info(
        "La clave de ElevenLabs del .env pasó al Administrador de credenciales; "
        "desde ahora se cambia en la pestaña Voz y se puede borrar del .env."
    )
