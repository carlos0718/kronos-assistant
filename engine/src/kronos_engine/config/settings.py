"""Ajustes del usuario, guardados en `config.toml`."""

import logging
import os
import sys
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import tomli_w

from kronos_engine.core.end_pause import DEFAULT_MS, MAX_MS, MIN_MS
from kronos_engine.core.folder_access import DEFAULT_DEPTH, MAX_DEPTH, MIN_DEPTH
from kronos_engine.core.follow_up import DEFAULT_SECONDS, MAX_SECONDS
from kronos_engine.core.model_choice import OLLAMA, ModelChoice, checked
from kronos_engine.core.platform import Folder

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    voice: str | None = None  # Voz elegida; None usa la voz por defecto del idioma.
    wake_word: bool = False  # Si Kronos escucha su nombre para activarse.
    user_name: str | None = None  # Cómo quiere el usuario que lo llamen.
    user_about: str | None = None  # Descripción corta del usuario, como contexto.
    # Segundos que sigue escuchando después de responder; cero es no seguir.
    follow_up_seconds: int = DEFAULT_SECONDS
    # Milisegundos de silencio que dan por terminada la frase del usuario.
    end_pause_ms: int = DEFAULT_MS
    # Las carpetas conocidas que Kronos puede mirar («desktop», «documents»…).
    folders_known: tuple[str, ...] = tuple(folder.value for folder in Folder)
    # Otras carpetas que sumó el usuario, con su ruta completa.
    folders_extra: tuple[str, ...] = ()
    # Cuántos niveles adentro de esas carpetas busca.
    folder_depth: int = DEFAULT_DEPTH
    # Qué modelo responde: el proveedor («ollama», «anthropic») y el modelo
    # (vacío: el de fábrica). La clave no va acá: ver `config/model_choice.py`.
    llm_provider: str = OLLAMA
    llm_model: str = ""


def _follow_up_seconds(value: object) -> int:
    # `bool` es un `int` para Python: `true` no cuenta como un segundo.
    if isinstance(value, int) and not isinstance(value, bool) and 0 <= value <= MAX_SECONDS:
        return value
    return DEFAULT_SECONDS


def _end_pause_ms(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and MIN_MS <= value <= MAX_MS:
        return value
    return DEFAULT_MS


def _folders_known(value: object) -> tuple[str, ...]:
    if not isinstance(value, list):
        return Settings.folders_known
    # Un nombre desconocido (de una versión futura, o mal escrito) se ignora.
    names = {folder.value for folder in Folder}
    return tuple(item for item in value if isinstance(item, str) and item in names)


def _folders_extra(value: object) -> tuple[str, ...]:
    # No se mira si existen: un disco desconectado no borra lo que eligió el usuario.
    if not isinstance(value, list):
        return ()
    return tuple(item for item in value if isinstance(item, str) and item)


def _folder_depth(value: object) -> int:
    if isinstance(value, int) and not isinstance(value, bool) and MIN_DEPTH <= value <= MAX_DEPTH:
        return value
    return DEFAULT_DEPTH


def _model_choice(provider: object, model: object) -> ModelChoice:
    # Algo desconocido (de una versión futura, o editado a mano) vuelve a Ollama.
    try:
        return checked(ModelChoice(str(provider), model if isinstance(model, str) else ""))
    except ValueError:
        return ModelChoice()


def config_dir() -> Path:
    """Carpeta de la app en el perfil del usuario."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", Path.home() / "AppData" / "Roaming"))
        return base / "Kronos"
    return Path(os.environ.get("XDG_CONFIG_HOME", Path.home() / ".config")) / "kronos"


class SettingsStore:
    def __init__(self, path: Path | None = None) -> None:
        self._path = path or config_dir() / "config.toml"

    def load(self) -> Settings:
        """Lee los ajustes. Si el archivo falta o está roto, devuelve los de fábrica."""
        try:
            data = tomllib.loads(self._path.read_text(encoding="utf-8"))
        except FileNotFoundError:
            return Settings()
        except (OSError, tomllib.TOMLDecodeError) as exc:
            log.warning("No se pudo leer %s (%s); se usan los ajustes de fábrica.", self._path, exc)
            return Settings()
        voice = data.get("voice")
        wake_word = data.get("wake_word")
        user_name = data.get("user_name")
        user_about = data.get("user_about")
        model = _model_choice(data.get("llm_provider", OLLAMA), data.get("llm_model"))
        return Settings(
            voice=voice if isinstance(voice, str) else None,
            wake_word=wake_word if isinstance(wake_word, bool) else False,
            user_name=user_name if isinstance(user_name, str) else None,
            user_about=user_about if isinstance(user_about, str) else None,
            follow_up_seconds=_follow_up_seconds(data.get("follow_up_seconds")),
            end_pause_ms=_end_pause_ms(data.get("end_pause_ms")),
            folders_known=_folders_known(data.get("folders_known")),
            folders_extra=_folders_extra(data.get("folders_extra")),
            folder_depth=_folder_depth(data.get("folder_depth")),
            llm_provider=model.provider,
            llm_model=model.model,
        )

    def save(self, settings: Settings) -> None:
        # TOML no tiene valor nulo: lo que no se eligió no se escribe.
        data = {key: value for key, value in asdict(settings).items() if value is not None}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(tomli_w.dumps(data), encoding="utf-8")

    def update(self, **changes: Any) -> None:
        """Cambia algunos ajustes y conserva el resto."""
        self.save(replace(self.load(), **changes))
