import json

import pytest

from kronos_engine.core.secret import MIN_LENGTH, SecretKeyError
from kronos_engine.permissions.secret_key import (
    LOCK_SECONDS,
    MAX_FAILURES,
    NAME,
    SecretKey,
)

GOOD = "una-clave-larga"


class MemorySecrets:
    def __init__(self) -> None:
        self.saved: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.saved.get(name)

    def write(self, name: str, secret: str) -> None:
        self.saved[name] = secret

    def delete(self, name: str) -> None:
        self.saved.pop(name, None)


class Clock:
    def __init__(self) -> None:
        self.now = 1000.0

    def __call__(self) -> float:
        return self.now


def make() -> tuple[SecretKey, MemorySecrets, Clock]:
    secrets, clock = MemorySecrets(), Clock()
    return SecretKey(secrets, clock), secrets, clock


def test_sin_clave_configurada_nada_se_verifica() -> None:
    key, _, _ = make()
    assert key.is_set() is False
    assert key.verify(GOOD) is False


def test_la_clave_guardada_se_verifica() -> None:
    key, _, _ = make()
    key.set(GOOD)
    assert key.is_set() is True
    assert key.verify(GOOD) is True
    assert key.verify("otra-clave-larga") is False


def test_se_guarda_el_hash_y_nunca_la_clave() -> None:
    key, secrets, _ = make()
    key.set(GOOD)
    stored = secrets.saved[NAME]
    assert GOOD not in stored
    assert json.loads(stored)["hash"].startswith("$argon2id$")


def test_una_clave_corta_no_se_acepta() -> None:
    key, secrets, _ = make()
    with pytest.raises(SecretKeyError):
        key.set("a" * (MIN_LENGTH - 1))
    assert secrets.saved == {}


def test_tras_varios_fallos_se_bloquea_aunque_la_clave_sea_buena() -> None:
    key, _, _ = make()
    key.set(GOOD)
    for _ in range(MAX_FAILURES):
        assert key.verify("mala-clave-larga") is False
    assert key.locked_for() == LOCK_SECONDS
    assert key.verify(GOOD) is False


def test_pasado_el_bloqueo_se_puede_volver_a_intentar() -> None:
    key, _, clock = make()
    key.set(GOOD)
    for _ in range(MAX_FAILURES):
        key.verify("mala-clave-larga")
    clock.now += LOCK_SECONDS + 1
    assert key.locked_for() == 0
    assert key.verify(GOOD) is True


def test_un_acierto_borra_los_fallos() -> None:
    key, _, _ = make()
    key.set(GOOD)
    for _ in range(MAX_FAILURES - 1):
        key.verify("mala-clave-larga")
    assert key.verify(GOOD) is True
    for _ in range(MAX_FAILURES - 1):
        key.verify("mala-clave-larga")
    assert key.locked_for() == 0


def test_el_bloqueo_sobrevive_a_un_reinicio() -> None:
    key, secrets, clock = make()
    key.set(GOOD)
    for _ in range(MAX_FAILURES):
        key.verify("mala-clave-larga")
    assert SecretKey(secrets, clock).locked_for() == LOCK_SECONDS


def test_cambiar_la_clave_pide_la_actual() -> None:
    key, _, _ = make()
    key.set(GOOD)
    with pytest.raises(SecretKeyError):
        key.change("mala-clave-larga", "nueva-clave-larga")
    key.change(GOOD, "nueva-clave-larga")
    assert key.verify("nueva-clave-larga") is True
    assert key.verify(GOOD) is False


def test_borrarla_pide_la_actual() -> None:
    key, _, _ = make()
    key.set(GOOD)
    with pytest.raises(SecretKeyError):
        key.remove("mala-clave-larga")
    key.remove(GOOD)
    assert key.is_set() is False


def test_con_el_bloqueo_activo_no_se_puede_cambiar() -> None:
    key, _, _ = make()
    key.set(GOOD)
    for _ in range(MAX_FAILURES):
        key.verify("mala-clave-larga")
    with pytest.raises(SecretKeyError):
        key.change(GOOD, "nueva-clave-larga")


def test_lo_guardado_ilegible_cuenta_como_sin_clave() -> None:
    key, secrets, _ = make()
    secrets.saved[NAME] = "no es json"
    assert key.is_set() is False
    assert key.verify(GOOD) is False


def test_poner_clave_cuando_ya_hay_una_se_rechaza() -> None:
    key, _, _ = make()
    key.set(GOOD)
    with pytest.raises(SecretKeyError):
        key.set("nueva-clave-larga")
    assert key.verify(GOOD) is True
