"""Mide la latencia y el consumo del bucle de voz en este equipo.

Uso:  pnpm engine:measure                (cinco rondas)
      pnpm engine:measure --rounds 10

No usa el micrófono ni el altavoz: genera una pregunta con la voz de Kronos y
la pasa por las mismas piezas que una conversación real (transcribir → modelo
→ voz). Lee los mismos ajustes que el motor: `config.toml` y las variables
`KRONOS_*`. Informa la mediana de cada paso en una tabla lista para pegar.
"""

import argparse
import asyncio
import contextlib
import os
import platform
import statistics
import time
from collections.abc import Iterator
from dataclasses import dataclass, field

import httpx
import numpy as np
import psutil

from kronos_engine import pipeline
from kronos_engine.agent.instructions import instructions_for
from kronos_engine.config.elevenlabs_key import saved_or_env
from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.llm import LLMError, Message
from kronos_engine.core.sentences import SentenceSplitter
from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider
from kronos_engine.platform.windows.credentials import WindowsCredentials
from kronos_engine.voice import FRAME_SAMPLES, SAMPLE_RATE
from kronos_engine.voice.assembly import DEFAULT_STT_MODEL, PARAKEET, stt_for, tts_for
from kronos_engine.voice.catalog import DEFAULT_VOICES
from kronos_engine.voice.elevenlabs import KEY_ENV
from kronos_engine.voice.endpointing import EndpointConfig
from kronos_engine.voice.speaker import Speech
from kronos_engine.voice.vad import SileroVad

# Una pregunta que el modelo contesta sin herramientas, en dos o tres frases.
QUESTIONS = {
    "es": "¿Cuál es la capital de Francia y por qué es famosa?",
    "en": "What is the capital of France and why is it famous?",
}
GIB = 1024**3
# Audio con el que se mide el detector de voz.
VAD_SECONDS = 60


@dataclass
class Cost:
    wall: float = 0.0  # Segundos de reloj.
    cpu: float = 0.0  # Segundos de procesador, sumando todos los núcleos.


@contextlib.contextmanager
def measured() -> Iterator[Cost]:
    cost = Cost()
    wall, cpu = time.perf_counter(), time.process_time()
    try:
        yield cost
    finally:
        cost.wall, cost.cpu = time.perf_counter() - wall, time.process_time() - cpu


@dataclass
class Results:
    """Una lista por paso, con un valor por ronda."""

    stt: list[Cost] = field(default_factory=list)
    first_token: list[float] = field(default_factory=list)
    first_sentence: list[float] = field(default_factory=list)
    tts: list[Cost] = field(default_factory=list)
    spoken_seconds: list[float] = field(default_factory=list)


def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def median(values: list[float]) -> float:
    return statistics.median(values)


def to_16k(speech: Speech) -> np.ndarray:
    """Lleva el audio de la voz a los 16 kHz que esperan whisper y el detector."""
    positions = np.arange(0, len(speech.samples), speech.sample_rate / SAMPLE_RATE)
    resampled = np.interp(positions, np.arange(len(speech.samples)), speech.samples)
    return resampled.astype(np.float32)


def cpu_name() -> str:
    if platform.system() == "Windows":
        import winreg

        key = r"HARDWARE\DESCRIPTION\System\CentralProcessor\0"
        with winreg.OpenKey(winreg.HKEY_LOCAL_MACHINE, key) as handle:
            return str(winreg.QueryValueEx(handle, "ProcessorNameString")[0]).strip()
    return platform.processor() or platform.machine()


def vad_share(audio: np.ndarray) -> float:
    """Qué parte de un núcleo usa el detector de voz con el micrófono abierto."""
    vad = SileroVad()
    frames = [audio[i : i + FRAME_SAMPLES] for i in range(0, len(audio), FRAME_SAMPLES)]
    frames = [frame for frame in frames if len(frame) == FRAME_SAMPLES]
    # El reloj de procesador de Windows avanza de a 16 ms: se mide sobre un
    # minuto de audio para que el resultado no quede por debajo de eso.
    frames *= max(1, round(VAD_SECONDS * SAMPLE_RATE / FRAME_SAMPLES / len(frames)))
    with measured() as cost:
        for frame in frames:
            vad.probability(frame)
    return cost.cpu / (len(frames) * FRAME_SAMPLES / SAMPLE_RATE)


async def ask(provider: OllamaProvider, messages: list[Message]) -> tuple[float, float, str]:
    """Devuelve cuánto tardó la primera palabra, cuánto la primera frase, y esa frase."""
    start = time.perf_counter()
    first_token: float | None = None
    first_sentence: tuple[float, str] | None = None
    text, splitter = "", SentenceSplitter()
    async for delta in provider.stream(messages):
        elapsed = time.perf_counter() - start
        first_token = elapsed if first_token is None else first_token
        text += delta
        if first_sentence is None and (complete := splitter.feed(delta)):
            first_sentence = (elapsed, complete[0])
    # Una respuesta sin punto final: la frase es la respuesta entera.
    at, sentence = first_sentence or (time.perf_counter() - start, text.strip())
    return first_token or at, at, sentence


async def ollama_usage(url: str, model: str, messages: list[Message]) -> list[str]:
    """Filas con lo que informa Ollama: velocidad del modelo y memoria que ocupa."""
    request = {
        "model": model,
        "messages": [{"role": m.role, "content": m.content} for m in messages],
        "stream": False,
        "think": False,
    }
    async with httpx.AsyncClient(base_url=url, timeout=120) as client:
        reply = (await client.post("/api/chat", json=request)).json()
        loaded = (await client.get("/api/ps")).json().get("models", [])
    rows = []
    if reply.get("eval_duration"):
        speed = reply["eval_count"] / reply["eval_duration"] * 1e9
        rows.append(f"| Velocidad del modelo | {num(speed, 0)} tokens por segundo |")
    for entry in loaded:
        if entry.get("name") == model and entry.get("size"):
            on_gpu = round(100 * entry.get("size_vram", 0) / entry["size"])
            size = f"{num(entry['size'] / GIB, 1)} GB, {on_gpu} % en la placa de video"
            rows.append(f"| Memoria del modelo en Ollama | {size} |")
    return rows


async def run(rounds: int) -> None:
    language = os.environ.get(pipeline.LANGUAGE_ENV, "es")
    settings = SettingsStore().load()
    voice = settings.voice or os.environ.get(pipeline.VOICE_ENV) or DEFAULT_VOICES[language]
    stt_model = os.environ.get(pipeline.STT_MODEL_ENV, DEFAULT_STT_MODEL)
    key = saved_or_env(WindowsCredentials(), os.environ.get(KEY_ENV, ""))
    llm_model = os.environ.get(pipeline.MODEL_ENV, pipeline.DEFAULT_MODEL)
    url = os.environ.get(pipeline.OLLAMA_URL_ENV, DEFAULT_URL)
    process = psutil.Process()

    print(f"Midiendo {rounds} rondas; tarda alrededor de un minuto…\n", flush=True)
    # Con una voz de ElevenLabs también mide la voz en la nube.
    tts = tts_for(voice, lambda: key)
    with measured() as tts_load:
        question = to_16k(await tts.synthesize(QUESTIONS[language]))
    stt = stt_for(stt_model, language, lambda: key)
    with measured() as stt_load:
        text = await stt.transcribe(question)
    provider = OllamaProvider(llm_model, base_url=url)
    with measured() as llm_load:
        await provider.load()
    system = instructions_for(settings.user_name or "", settings.user_about or "")
    messages = [Message("system", system), Message("user", text)]

    results, llm_error = Results(), ""
    for _ in range(rounds):
        with measured() as cost:
            await stt.transcribe(question)
        results.stt.append(cost)
        sentence = "París es la capital de Francia."
        if not llm_error:
            try:
                first_token, first_sentence, sentence = await ask(provider, messages)
                results.first_token.append(first_token)
                results.first_sentence.append(first_sentence)
            except LLMError as exc:
                llm_error = str(exc)
        with measured() as cost:
            speech = await tts.synthesize(sentence)
        results.tts.append(cost)
        results.spoken_seconds.append(len(speech.samples) / speech.sample_rate)

    memory = process.memory_info()
    usage = [] if llm_error else await ollama_usage(url, llm_model, messages)
    cores, threads = psutil.cpu_count(logical=False), psutil.cpu_count()
    ram = psutil.virtual_memory().total / GIB
    question_seconds = len(question) / SAMPLE_RATE
    stt_wall = median([cost.wall for cost in results.stt])
    stt_cpu = median([cost.cpu for cost in results.stt])
    tts_wall = median([cost.wall for cost in results.tts])
    tts_cpu = median([cost.cpu for cost in results.tts])
    silence = EndpointConfig().end_silence_ms / 1000

    print(f"Equipo: {cpu_name()} · {cores} núcleos ({threads} hilos) · {num(ram, 0)} GB de memoria")
    print(f"Sistema: {platform.system()} {platform.release()}")
    stt_name = stt_model if stt_model == PARAKEET else f"whisper {stt_model}"
    print(f"Piezas: {stt_name} · {llm_model} en Ollama · voz {voice}")
    print(f"Mediana de {rounds} rondas.\n")
    print("| Paso | Tiempo | Procesador del motor |")
    print("|---|---|---|")
    print(
        f"| Transcribir una frase de {num(question_seconds, 1)} s "
        f"| {num(stt_wall)} s | {num(stt_cpu)} s |"
    )
    total = stt_wall + tts_wall
    if llm_error:
        print(f"| Modelo | sin medir: {llm_error} | |")
    else:
        total += median(results.first_sentence)
        print(f"| Modelo: primera palabra | {num(median(results.first_token))} s | usa Ollama |")
        print(f"| Modelo: primera frase | {num(median(results.first_sentence))} s | usa Ollama |")
    print(
        f"| Voz: primera frase ({num(median(results.spoken_seconds), 1)} s de audio) "
        f"| {num(tts_wall)} s | {num(tts_cpu)} s |"
    )
    label = "Total hasta que empieza a hablar" + (" (sin el modelo)" if llm_error else "")
    print(f"| **{label}** | **{num(total)} s** | |")
    print(f"\nA ese total se suman los {num(silence, 1)} s de silencio que Kronos espera")
    print("para dar la frase por terminada.\n")
    print("| Consumo | Valor |")
    print("|---|---|")
    print(f"| Memoria del motor con todo cargado | {num(memory.rss / 1024**2, 0)} MB |")
    vad = num(100 * vad_share(question), 1)
    print(f"| Detector de voz con el micrófono abierto | {vad} % de un núcleo |")
    print(f"| Cada frase que se transcribe en reposo | {num(stt_cpu)} s de procesador |")
    for row in usage:
        print(row)
    print(
        f"| Primera vez (carga de cada pieza) | transcripción {num(stt_load.wall, 1)} s · "
        f"voz {num(tts_load.wall, 1)} s · modelo {num(llm_load.wall, 1)} s |"
    )


def main() -> None:
    parser = argparse.ArgumentParser(description="Mide la latencia y el consumo del bucle de voz.")
    parser.add_argument("--rounds", type=int, default=5, help="cuántas veces repetir (5)")
    asyncio.run(run(max(1, parser.parse_args().rounds)))


if __name__ == "__main__":
    main()
