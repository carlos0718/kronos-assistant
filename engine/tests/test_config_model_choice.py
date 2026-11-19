from pathlib import Path

import pytest

from kronos_engine.config.model_choice import StoredModelChoice
from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.model_choice import ANTHROPIC, OLLAMA, ModelChoice


class MemorySecrets:
    def __init__(self) -> None:
        self.saved: dict[str, str] = {}

    def read(self, name: str) -> str | None:
        return self.saved.get(name)

    def write(self, name: str, secret: str) -> None:
        self.saved[name] = secret

    def delete(self, name: str) -> None:
        self.saved.pop(name, None)


def test_de_fabrica_responde_ollama(tmp_path: Path) -> None:
    control = StoredModelChoice(SettingsStore(tmp_path / "config.toml"), MemorySecrets())

    assert control.get() == ModelChoice(OLLAMA, "")


def test_la_eleccion_queda_guardada(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"

    StoredModelChoice(SettingsStore(path), MemorySecrets()).set(
        ModelChoice(ANTHROPIC, "claude-sonnet-5-5")
    )

    # Otro objeto sobre el mismo archivo: es lo que pasa al reiniciar el motor.
    assert StoredModelChoice(SettingsStore(path), MemorySecrets()).get() == ModelChoice(
        ANTHROPIC, "claude-sonnet-5-5"
    )


def test_rechaza_un_proveedor_o_un_modelo_desconocido(tmp_path: Path) -> None:
    control = StoredModelChoice(SettingsStore(tmp_path / "config.toml"), MemorySecrets())

    with pytest.raises(ValueError, match="Proveedor"):
        control.set(ModelChoice("openai"))
    with pytest.raises(ValueError, match="Modelo"):
        control.set(ModelChoice(ANTHROPIC, "claude-3-opus"))


def test_un_config_editado_a_mano_con_algo_desconocido_vuelve_a_ollama(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    path.write_text('llm_provider = "otro"\nllm_model = 3\n', encoding="utf-8")

    assert StoredModelChoice(SettingsStore(path), MemorySecrets()).get() == ModelChoice(OLLAMA)


def test_la_clave_no_va_al_archivo_de_configuracion(tmp_path: Path) -> None:
    path = tmp_path / "config.toml"
    secrets = MemorySecrets()
    control = StoredModelChoice(SettingsStore(path), secrets)

    control.set(ModelChoice(ANTHROPIC))
    control.set_key(ANTHROPIC, "  sk-ant-secreta  ")

    assert control.key(ANTHROPIC) == "sk-ant-secreta"
    assert "sk-ant" not in path.read_text(encoding="utf-8")


def test_una_clave_vacia_borra_la_guardada(tmp_path: Path) -> None:
    control = StoredModelChoice(SettingsStore(tmp_path / "config.toml"), MemorySecrets())
    control.set_key(ANTHROPIC, "sk-ant-secreta")

    control.set_key(ANTHROPIC, "")

    assert control.key(ANTHROPIC) is None


def test_ollama_no_tiene_clave(tmp_path: Path) -> None:
    control = StoredModelChoice(SettingsStore(tmp_path / "config.toml"), MemorySecrets())

    with pytest.raises(ValueError, match="clave"):
        control.set_key(OLLAMA, "algo")
