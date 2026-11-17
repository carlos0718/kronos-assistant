"""Variables de un archivo `.env`, para las claves que no van al repositorio.

Solo en desarrollo: el motor lee el `.env` de la raíz del proyecto (modelo en
`.env.example`, que explica cada variable). El motor empaquetado no lo busca.
"""

import os
import sys
from pathlib import Path


def project_env_file() -> Path | None:
    """El `.env` de la raíz del proyecto, o None si el motor está empaquetado."""
    if getattr(sys, "frozen", False):
        return None
    # engine/src/kronos_engine/config/env_file.py → la raíz está cuatro carpetas arriba.
    return Path(__file__).resolve().parents[4] / ".env"


def load_env_file(path: Path) -> None:
    """Suma las variables de un archivo `NOMBRE=valor`; las que ya existen ganan."""
    if not path.exists():
        return
    # utf-8-sig: algunos editores de Windows guardan una marca al comienzo del archivo.
    for line in path.read_text(encoding="utf-8-sig").splitlines():
        name, sep, value = line.strip().partition("=")
        if sep and name and not name.startswith("#"):
            os.environ.setdefault(name.strip(), value.strip().strip("\"'"))
