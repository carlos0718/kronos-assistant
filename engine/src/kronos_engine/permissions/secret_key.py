"""La clave secreta del nivel crítico.

La verifica este código, nunca el modelo. Se guarda como hash Argon2 en el
almacén de claves del sistema, nunca en texto plano. Tras varios intentos
fallidos el nivel crítico se bloquea un rato; el conteo también se guarda, así
que reiniciar la app no lo reinicia.
"""

import json
import logging
import time
from collections.abc import Callable
from dataclasses import asdict, dataclass

from argon2 import PasswordHasher
from argon2.exceptions import InvalidHashError, VerificationError

from kronos_engine.core.model_choice import SecretStore
from kronos_engine.core.secret import MIN_LENGTH, SecretKeyError

log = logging.getLogger(__name__)

# Con este nombre se ve en el Administrador de credenciales.
NAME = "Kronos/secret-key"
MAX_FAILURES = 5
LOCK_SECONDS = 300


@dataclass(frozen=True)
class _State:
    hash: str
    failures: int = 0
    locked_until: float = 0.0


class SecretKey:
    def __init__(self, secrets: SecretStore, clock: Callable[[], float] = time.time) -> None:
        self._secrets = secrets
        self._clock = clock
        self._hasher = PasswordHasher()

    def is_set(self) -> bool:
        return self._load() is not None

    def locked_for(self) -> int:
        """Cuántos segundos faltan para poder volver a intentar. 0 si no está bloqueado."""
        state = self._load()
        if state is None:
            return 0
        return max(0, round(state.locked_until - self._clock()))

    def verify(self, attempt: str) -> bool:
        state = self._load()
        if state is None or self.locked_for() > 0:
            return False
        try:
            self._hasher.verify(state.hash, attempt)
        except (VerificationError, InvalidHashError):
            self._fail(state)
            return False
        if state.failures:
            self._save(_State(state.hash))
        return True

    def set(self, new: str) -> None:
        """Pone la primera clave. Para cambiarla hay que dar la actual (`change`)."""
        if self.is_set():
            raise SecretKeyError("Ya hay una clave: para cambiarla, ingresá la actual.")
        self._store(new)

    def change(self, current: str, new: str) -> None:
        self._require(current)
        self._store(new)

    def remove(self, current: str) -> None:
        self._require(current)
        self._secrets.delete(NAME)
        log.info("Se borró la clave secreta.")

    def _require(self, current: str) -> None:
        if self.locked_for() > 0:
            raise SecretKeyError("Demasiados intentos fallidos. Esperá un rato.")
        if not self.verify(current):
            raise SecretKeyError("La clave actual no es correcta.")

    def _store(self, new: str) -> None:
        if len(new) < MIN_LENGTH:
            raise SecretKeyError(f"La clave necesita al menos {MIN_LENGTH} caracteres.")
        self._save(_State(self._hasher.hash(new)))
        log.info("Se guardó la clave secreta.")

    def _fail(self, state: _State) -> None:
        failures = state.failures + 1
        if failures < MAX_FAILURES:
            self._save(_State(state.hash, failures))
            return
        log.warning("Clave secreta mal ingresada %d veces: nivel crítico bloqueado.", MAX_FAILURES)
        self._save(_State(state.hash, 0, self._clock() + LOCK_SECONDS))

    def _save(self, state: _State) -> None:
        self._secrets.write(NAME, json.dumps(asdict(state)))

    def _load(self) -> _State | None:
        raw = self._secrets.read(NAME)
        if not raw:
            return None
        try:
            data = json.loads(raw)
            return _State(str(data["hash"]), int(data["failures"]), float(data["locked_until"]))
        except (ValueError, KeyError, TypeError):
            return None
