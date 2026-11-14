"""Ajustes del usuario, guardados en `config.toml`."""

import logging
import os
import sys
import tomllib
from dataclasses import asdict, dataclass, replace
from pathlib import Path
from typing import Any

import tomli_w

log = logging.getLogger(__name__)


@dataclass(frozen=True)
class Settings:
    voice: str | None = None  # Voz elegida; None usa la voz por defecto del idioma.
    wake_word: bool = False  # Si Kronos escucha su nombre para activarse.
    user_name: str | None = None  # Cómo quiere el usuario que lo llamen.
    user_about: str | None = None  # Descripción corta del usuario, como contexto.


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
        return Settings(
            voice=voice if isinstance(voice, str) else None,
            wake_word=wake_word if isinstance(wake_word, bool) else False,
            user_name=user_name if isinstance(user_name, str) else None,
            user_about=user_about if isinstance(user_about, str) else None,
        )

    def save(self, settings: Settings) -> None:
        # TOML no tiene valor nulo: lo que no se eligió no se escribe.
        data = {key: value for key, value in asdict(settings).items() if value is not None}
        self._path.parent.mkdir(parents=True, exist_ok=True)
        self._path.write_text(tomli_w.dumps(data), encoding="utf-8")

    def update(self, **changes: Any) -> None:
        """Cambia algunos ajustes y conserva el resto."""
        self.save(replace(self.load(), **changes))
