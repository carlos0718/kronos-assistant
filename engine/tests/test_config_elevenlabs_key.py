import logging

import pytest

from kronos_engine.config.elevenlabs_key import (
    NAME,
    StoredElevenLabsKey,
    move_from_env,
    saved_or_env,
)


class MemorySecrets:
    def __init__(self) -> None:
        self.saved: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.saved.get(name)

    def write(self, name: str, secret: str) -> None:
        self.saved[name] = secret

    def delete(self, name: str) -> None:
        self.saved.pop(name, None)


def test_sin_clave_guardada_devuelve_vacio() -> None:
    assert StoredElevenLabsKey(MemorySecrets()).get() == ""


def test_la_clave_se_guarda_aparte_sin_espacios() -> None:
    secrets = MemorySecrets()

    StoredElevenLabsKey(secrets).set("  sk_abc \n")

    assert secrets.saved == {NAME: "sk_abc"}
    # Otro objeto sobre el mismo almacén: es lo que pasa al reiniciar el motor.
    assert StoredElevenLabsKey(secrets).get() == "sk_abc"


def test_una_clave_vacia_borra_la_guardada() -> None:
    secrets = MemorySecrets()
    key = StoredElevenLabsKey(secrets)
    key.set("sk_abc")

    key.set("   ")

    assert secrets.saved == {}


def test_cambiar_la_clave_avisa() -> None:
    changes: list[int] = []
    key = StoredElevenLabsKey(MemorySecrets(), on_change=lambda: changes.append(1))

    key.set("sk_abc")
    key.set("")

    assert len(changes) == 2


def test_la_clave_del_env_pasa_al_almacen_si_no_habia_otra(
    caplog: pytest.LogCaptureFixture,
) -> None:
    secrets = MemorySecrets()

    with caplog.at_level(logging.INFO):
        move_from_env(StoredElevenLabsKey(secrets), " sk_del_env ")

    assert secrets.saved == {NAME: "sk_del_env"}
    assert ".env" in caplog.text
    assert "sk_del_env" not in caplog.text


def test_la_clave_cargada_en_la_app_gana_sobre_la_del_env() -> None:
    secrets = MemorySecrets()
    key = StoredElevenLabsKey(secrets)
    key.set("sk_de_la_app")

    move_from_env(key, "sk_del_env")

    assert key.get() == "sk_de_la_app"


def test_los_scripts_usan_la_clave_guardada_y_si_no_la_del_env() -> None:
    secrets = MemorySecrets()
    assert saved_or_env(secrets, " sk_del_env ") == "sk_del_env"

    secrets.saved[NAME] = "sk_de_la_app"
    assert saved_or_env(secrets, "sk_del_env") == "sk_de_la_app"


def test_los_scripts_siguen_con_la_del_env_si_no_se_puede_leer_la_guardada() -> None:
    class Broken(MemorySecrets):
        def read(self, name: str) -> str | None:
            raise OSError("sin Administrador de credenciales")

    assert saved_or_env(Broken(), "sk_del_env") == "sk_del_env"


def test_sin_clave_en_el_env_no_toca_nada() -> None:
    secrets = MemorySecrets()

    move_from_env(StoredElevenLabsKey(secrets), "")

    assert secrets.saved == {}
