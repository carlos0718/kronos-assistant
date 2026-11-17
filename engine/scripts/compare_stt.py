"""Compara reconocedores de voz con frases cortas grabadas por el usuario.

Uso:  pnpm engine:compare-stt grabar              (una tanda de frases)
      pnpm engine:compare-stt grabar --tomas 2    (cada frase dos veces)
      pnpm engine:compare-stt comparar

`grabar` pide las frases de a una y las graba con el micrófono, igual que
Kronos: el mismo detector de voz y la misma pausa de fin de frase que eligió el
usuario en la pestaña Voz. Las guarda fuera del repositorio, en
`%LOCALAPPDATA%\\Kronos\\pruebas-voz`, porque son la voz del usuario.

`comparar` pasa cada grabación por Parakeet, whisper `small` con el español
fijo y Scribe de ElevenLabs, e informa cuántas acertó cada uno y cuánto tardó.
ElevenLabs corre en la nube y es de pago: las grabaciones salen de la
computadora. Se usa solo si está la clave: en la variable ELEVENLABS_API_KEY o
en el archivo `.env` de la raíz del proyecto (ver `.env.example`).
"""

import argparse
import asyncio
import json
import os
import statistics
import time
import unicodedata
import wave
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

from kronos_engine import pipeline
from kronos_engine.config.env_file import load_env_file, project_env_file
from kronos_engine.config.settings import SettingsStore
from kronos_engine.voice import SAMPLE_RATE
from kronos_engine.voice.elevenlabs import KEY_ENV, MODEL, ElevenLabsError, ElevenLabsStt
from kronos_engine.voice.endpointing import EndpointConfig
from kronos_engine.voice.listener import Stt, capture
from kronos_engine.voice.microphone import open_microphone
from kronos_engine.voice.vad import SileroVad

# Lo que más falla hoy: respuestas de una o dos palabras, el nombre de Kronos
# y los pedidos de las pruebas con micrófono del 16 nov.
PHRASES = [
    "Sí.",
    "No.",
    "Sí, confirmo.",
    "No, dejalo.",
    "Dale.",
    "Kronos.",
    "Abrí el bloc de notas.",
    "Cerrá el bloc de notas.",
    "¿Qué hora es?",
    "Abrí la carpeta Documentos.",
    "Sí.",
    "No.",
]
RECOGNIZERS = ["parakeet", "small", "elevenlabs"]
LIST_FILE = "frases.json"
# Si no se oye nada en este tiempo, se vuelve a pedir la frase.
WAIT_MS = 15000
TRIES = 3


def default_folder() -> Path:
    base = os.environ.get("LOCALAPPDATA") or str(Path.home())
    return Path(base) / "Kronos" / "pruebas-voz"


def normalized(text: str) -> str:
    """Sin mayúsculas, tildes ni signos: «¿Qué hora es?» y «que hora es» valen igual."""
    plain = unicodedata.normalize("NFD", text.lower())
    kept = "".join(c if c.isalnum() else " " for c in plain if not unicodedata.combining(c))
    return " ".join(kept.split())


def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def save_wav(path: Path, audio: np.ndarray) -> None:
    with wave.open(str(path), "wb") as out:
        out.setnchannels(1)
        out.setsampwidth(2)
        out.setframerate(SAMPLE_RATE)
        out.writeframes((np.clip(audio, -1.0, 1.0) * 32767).astype("<i2").tobytes())


def load_wav(path: Path) -> np.ndarray:
    with wave.open(str(path), "rb") as clip:
        frames = clip.readframes(clip.getnframes())
    return np.frombuffer(frames, dtype="<i2").astype(np.float32) / 32768


async def record_one(vad: SileroVad, config: EndpointConfig) -> np.ndarray | None:
    for _ in range(TRIES):
        async with open_microphone() as microphone:
            audio = await capture(microphone, vad, config)
        if audio is not None:
            return audio
        print("   No te oí. Probá de nuevo.", flush=True)
    return None


async def record(folder: Path, takes: int) -> None:
    end_pause = SettingsStore().load().end_pause_ms
    config = EndpointConfig(end_silence_ms=end_pause, start_timeout_ms=WAIT_MS)
    vad = SileroVad()
    phrases = PHRASES * takes
    print(f"Vas a grabar {len(phrases)} frases en {folder}")
    print(f"Decí cada una cuando aparezca; termina con {num(end_pause / 1000, 1)} s de silencio.\n")
    recorded = []
    for index, phrase in enumerate(phrases, start=1):
        print(f"[{index}/{len(phrases)}] Decí: «{phrase}»", flush=True)
        audio = await record_one(vad, config)
        if audio is None:
            print("   Salteada.")
            continue
        name = f"{index:02}.wav"
        save_wav(folder / name, audio)
        recorded.append({"file": name, "expected": phrase})
        print(f"   Grabada ({num(len(audio) / SAMPLE_RATE, 1)} s).")
    (folder / LIST_FILE).write_text(
        json.dumps(recorded, ensure_ascii=False, indent=2), encoding="utf-8"
    )
    print(f"\nListo: {len(recorded)} frases. Ahora: pnpm engine:compare-stt comparar")


@dataclass
class Outcome:
    texts: list[str] = field(default_factory=list)
    seconds: list[float] = field(default_factory=list)
    error: str = ""


def recognizer_for(name: str) -> tuple[str, Stt] | None:
    if name == "parakeet":
        return "Parakeet v3", pipeline.stt_for(pipeline.PARAKEET, "es")
    if name == "elevenlabs":
        key = os.environ.get(KEY_ENV, "")
        if not key:
            print(f"ElevenLabs queda afuera: falta la clave en {KEY_ENV}.")
            return None
        return f"ElevenLabs {MODEL}", ElevenLabsStt(key)
    return f"whisper {name} (es)", pipeline.stt_for(name, "es")


async def run_recognizer(stt: Stt, clips: list[np.ndarray]) -> Outcome:
    outcome = Outcome()
    try:
        # La primera vez carga el modelo o abre la conexión: no se cuenta.
        await stt.transcribe(clips[0])
        for clip in clips:
            start = time.perf_counter()
            outcome.texts.append(await stt.transcribe(clip))
            outcome.seconds.append(time.perf_counter() - start)
    except ElevenLabsError as exc:
        outcome.error = str(exc)
    finally:
        if isinstance(stt, ElevenLabsStt):
            await stt.aclose()
    return outcome


def report(expected: list[str], results: dict[str, Outcome]) -> None:
    names = list(results)
    print("\n| Dijiste | " + " | ".join(names) + " |")
    print("|---" * (len(names) + 1) + "|")
    for row, phrase in enumerate(expected):
        cells = []
        for outcome in results.values():
            text = outcome.texts[row]
            right = normalized(text) == normalized(phrase)
            cells.append(text if right else f"✗ {text or '(nada)'}")
        print(f"| {phrase} | " + " | ".join(cells) + " |")
    print("\n| Reconocedor | Aciertos | Tiempo por frase (mediana) | Máximo |")
    print("|---|---|---|---|")
    for name, outcome in results.items():
        hits = sum(
            normalized(text) == normalized(phrase)
            for text, phrase in zip(outcome.texts, expected, strict=True)
        )
        median, longest = num(statistics.median(outcome.seconds)), num(max(outcome.seconds))
        print(f"| {name} | {hits} de {len(expected)} | {median} s | {longest} s |")


async def compare(folder: Path, chosen: list[str]) -> None:
    listing = folder / LIST_FILE
    if not listing.exists():
        print(f"No hay grabaciones en {folder}. Primero: pnpm engine:compare-stt grabar")
        return
    entries = json.loads(listing.read_text(encoding="utf-8"))
    clips = [load_wav(folder / entry["file"]) for entry in entries]
    expected = [entry["expected"] for entry in entries]
    print(f"Comparando {len(clips)} grabaciones de {folder}…", flush=True)
    results: dict[str, Outcome] = {}
    for name in chosen:
        picked = recognizer_for(name)
        if picked is None:
            continue
        label, stt = picked
        print(f"- {label}…", flush=True)
        outcome = await run_recognizer(stt, clips)
        if outcome.error:
            print(f"  {label} queda afuera: {outcome.error}")
            continue
        results[label] = outcome
    if results:
        report(expected, results)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara reconocedores de voz con tu voz.")
    parser.add_argument("accion", choices=["grabar", "comparar"])
    parser.add_argument("--carpeta", type=Path, default=default_folder())
    parser.add_argument("--tomas", type=int, default=1, help="cuántas veces cada frase (1)")
    parser.add_argument(
        "--reconocedores",
        default=",".join(RECOGNIZERS),
        help="separados por coma: parakeet, elevenlabs o un tamaño de whisper",
    )
    args = parser.parse_args()
    if env_file := project_env_file():
        load_env_file(env_file)
    if args.accion == "grabar":
        args.carpeta.mkdir(parents=True, exist_ok=True)
        asyncio.run(record(args.carpeta, max(1, args.tomas)))
    else:
        # PowerShell convierte "a,b" en "a b": valen la coma y el espacio.
        asyncio.run(compare(args.carpeta, args.reconocedores.replace(",", " ").split()))


if __name__ == "__main__":
    main()
