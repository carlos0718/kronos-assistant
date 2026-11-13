"""Empaqueta el motor con PyInstaller en modo carpeta (--onedir).

Uso:  uv run --project engine python engine/scripts/build.py
Salida: engine/dist/kronos-engine/  (ejecutable + carpeta _internal)

La app de escritorio incluye esa carpeta completa como recurso del instalador.
"""

from pathlib import Path

import PyInstaller.__main__

ENGINE_DIR = Path(__file__).resolve().parent.parent
NAME = "kronos-engine"


def main() -> None:
    PyInstaller.__main__.run(
        [
            str(ENGINE_DIR / "src" / "kronos_engine" / "__main__.py"),
            "--name", NAME,
            "--onedir",
            "--console",  # Necesita salida estándar; la app lo lanza sin ventana.
            "--noconfirm",
            "--clean",
            "--paths", str(ENGINE_DIR / "src"),
            "--distpath", str(ENGINE_DIR / "dist"),
            "--workpath", str(ENGINE_DIR / "build"),
            "--specpath", str(ENGINE_DIR / "build"),
            # uvicorn y websockets cargan módulos por nombre; PyInstaller no los detecta solo.
            "--collect-submodules", "uvicorn",
            "--collect-submodules", "websockets",
            # El modelo de detección de voz (Silero) viaja dentro de faster-whisper.
            "--collect-data", "faster_whisper",
            # Piper trae los datos de pronunciación (espeak-ng) dentro del paquete.
            "--collect-data", "piper",
        ]
    )  # fmt: skip
    print(f"Motor empaquetado en {ENGINE_DIR / 'dist' / NAME}")


if __name__ == "__main__":
    main()
