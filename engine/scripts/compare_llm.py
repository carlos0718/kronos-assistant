"""Compara modelos de lenguaje locales con los pedidos reales de Kronos.

Uso:  pnpm engine:compare-llm                                  (los tres modelos, tres rondas)
      pnpm engine:compare-llm --modelos qwen3:8b,gemma4:12b
      pnpm engine:compare-llm --rondas 5 --respuestas

Cada pedido pasa por la misma pieza que en una conversación (`AgentResponder`),
con las mismas instrucciones y las descripciones reales de las acciones. Las
acciones no se ejecutan: el script anota cuál pidió el modelo y le devuelve un
resultado simulado, así no se abre ni se cierra nada en la pantalla.

Informa, por modelo, cuántas veces eligió bien la acción (o ninguna, cuando no
correspondía), cuántas respuestas traen algo que no se puede decir en voz alta
(Markdown, emojis, listas) y cuánto tardó en empezar a contestar. Los modelos
tienen que estar descargados en Ollama (`ollama pull <modelo>`); los que falten
se saltean. Necesita Ollama abierto.
"""

import argparse
import asyncio
import os
import statistics
import time
from collections.abc import Sequence
from dataclasses import dataclass, field

import httpx
from llm_cases import CASES, Case, SimulatedTools, Turn

from kronos_engine import pipeline
from kronos_engine.agent.instructions import instructions_for
from kronos_engine.agent.responder import AgentResponder
from kronos_engine.config.folder_access import StoredFolderAccess
from kronos_engine.config.settings import SettingsStore
from kronos_engine.core.llm import LLMError
from kronos_engine.core.tools import ToolSpec
from kronos_engine.llm.ollama import DEFAULT_URL, OllamaProvider

MODELS = ["qwen3:8b", "qwen3.5:9b", "gemma4:12b"]
GIB = 1024**3
# Si un pedido tarda más que esto, se da por fallado y se sigue con el próximo.
TURN_TIMEOUT = 60


async def run_case(provider: OllamaProvider, specs: Sequence[ToolSpec], case: Case) -> Turn:
    tools = SimulatedTools(specs, "jueves 19 de noviembre de 2026, 15:42")
    responder = AgentResponder(provider, lambda: instructions_for("", ""), tools=tools)
    turn = Turn()
    start = time.perf_counter()

    async def answer() -> None:
        async for piece in responder.respond(case.said):
            if turn.first_word is None and piece.strip():
                turn.first_word = time.perf_counter() - start
            turn.reply += piece

    try:
        await asyncio.wait_for(answer(), TURN_TIMEOUT)
    except LLMError as exc:
        turn.error = str(exc)
    except TimeoutError:
        turn.error = f"tardó más de {TURN_TIMEOUT} s"
    turn.total = time.perf_counter() - start
    turn.calls = tools.calls
    return turn


@dataclass
class Usage:
    tokens_per_second: float | None = None
    memory_gib: float | None = None
    on_gpu: int | None = None


async def installed(url: str) -> set[str]:
    async with httpx.AsyncClient(base_url=url, timeout=10) as client:
        tags = (await client.get("/api/tags")).json().get("models", [])
    return {entry["name"] for entry in tags}


async def usage(url: str, model: str) -> Usage:
    """La velocidad del modelo y cuánto ocupa, según Ollama."""
    request = {
        "model": model,
        "messages": [{"role": "user", "content": "Contame en dos frases qué es un volcán."}],
        "stream": False,
        "think": False,
    }
    found = Usage()
    async with httpx.AsyncClient(base_url=url, timeout=120) as client:
        reply = (await client.post("/api/chat", json=request)).json()
        loaded = (await client.get("/api/ps")).json().get("models", [])
    if reply.get("eval_duration"):
        found.tokens_per_second = reply["eval_count"] / reply["eval_duration"] * 1e9
    for entry in loaded:
        if entry.get("name") == model and entry.get("size"):
            found.memory_gib = entry["size"] / GIB
            found.on_gpu = round(100 * entry.get("size_vram", 0) / entry["size"])
    return found


async def unload(url: str, model: str) -> None:
    """Saca el modelo de la memoria: si no, el siguiente no entra entero en la placa."""
    async with httpx.AsyncClient(base_url=url, timeout=60) as client:
        await client.post("/api/generate", json={"model": model, "keep_alive": 0})


def num(value: float, digits: int = 2) -> str:
    return f"{value:.{digits}f}".replace(".", ",")


def seconds(values: list[float]) -> str:
    return f"{num(statistics.median(values))} s" if values else "—"


@dataclass
class ModelResult:
    turns: dict[str, list[Turn]] = field(default_factory=dict)
    usage: Usage = field(default_factory=Usage)
    load_seconds: float = 0.0


async def run_model(url: str, model: str, specs: Sequence[ToolSpec], rounds: int) -> ModelResult:
    provider = OllamaProvider(model, base_url=url)
    result = ModelResult()
    start = time.perf_counter()
    await provider.load()
    result.load_seconds = time.perf_counter() - start
    for case in CASES:
        result.turns[case.said] = []
    for number in range(1, rounds + 1):
        print(f"  ronda {number} de {rounds}…", flush=True)
        for case in CASES:
            result.turns[case.said].append(await run_case(provider, specs, case))
    result.usage = await usage(url, model)
    return result


def describe(turn: Turn) -> str:
    if turn.error:
        return f"error: {turn.error}"
    calls = ", ".join(
        f"{call.name}({', '.join(f'{k}={v!r}' for k, v in call.arguments.items())})"
        for call in turn.calls
    )
    reply = " ".join(turn.reply.split()) or "(no dijo nada)"
    return f"[{calls or 'sin acción'}] {reply}"


def report(results: dict[str, ModelResult], rounds: int, show_replies: bool) -> None:
    total = len(CASES) * rounds
    print("\n| Pedido | " + " | ".join(results) + " |")
    print("|---" * (len(results) + 1) + "|")
    for case in CASES:
        cells = []
        for result in results.values():
            turns = result.turns[case.said]
            hits = sum(turn.right_action(case) and turn.right_reply(case) for turn in turns)
            cells.append(f"{hits}/{rounds}" if hits == rounds else f"✗ {hits}/{rounds}")
        expected = case.tool or "sin acción"
        print(f"| {case.said} ({expected}) | " + " | ".join(cells) + " |")

    print(
        "\n| Modelo | Aciertos | Se puede decir en voz alta | Primera palabra sin acción "
        "| Primera palabra con acción | Turno más lento | Velocidad | Memoria | Carga |"
    )
    print("|---|---|---|---|---|---|---|---|---|")
    for model, result in results.items():
        pairs = [(case, turn) for case in CASES for turn in result.turns[case.said]]
        hits = sum(turn.right_action(case) and turn.right_reply(case) for case, turn in pairs)
        spoken = sum(turn.speakable() for _, turn in pairs)
        plain_first = [t.first_word for c, t in pairs if not c.tool and t.first_word is not None]
        tool_first = [t.first_word for c, t in pairs if c.tool and t.first_word is not None]
        slowest = max(turn.total for _, turn in pairs)
        found = result.usage
        speed = f"{num(found.tokens_per_second, 0)} tokens/s" if found.tokens_per_second else "—"
        memory = (
            f"{num(found.memory_gib, 1)} GB, {found.on_gpu} % en la placa"
            if found.memory_gib is not None
            else "—"
        )
        print(
            f"| {model} | {hits} de {total} | {spoken} de {total} | {seconds(plain_first)} "
            f"| {seconds(tool_first)} | {num(slowest)} s | {speed} | {memory} "
            f"| {num(result.load_seconds, 1)} s |"
        )

    for model, result in results.items():
        print(f"\nErrores de {model}:" if not show_replies else f"\nRespuestas de {model}:")
        shown = False
        for case in CASES:
            for turn in result.turns[case.said]:
                good = turn.right_action(case) and turn.right_reply(case) and turn.speakable()
                if show_replies or not good:
                    print(f"- «{case.said}» → {describe(turn)}")
                    shown = True
        if not shown:
            print("- ninguno")


async def run(models: list[str], rounds: int, show_replies: bool) -> None:
    url = os.environ.get(pipeline.OLLAMA_URL_ENV, DEFAULT_URL)
    try:
        available = await installed(url)
    except httpx.HTTPError:
        print("No se pudo conectar con Ollama. Abrilo (o corré `ollama serve`) y probá de nuevo.")
        return
    access = StoredFolderAccess(SettingsStore())
    specs = [tool.spec for tool in pipeline.available_tools(access.get)]
    results: dict[str, ModelResult] = {}
    for model in models:
        if model not in available:
            print(f"{model} queda afuera: no está descargado (ollama pull {model}).")
            continue
        print(f"- {model}…", flush=True)
        results[model] = await run_model(url, model, specs, rounds)
        await unload(url, model)
    if results:
        report(results, rounds, show_replies)


def main() -> None:
    parser = argparse.ArgumentParser(description="Compara modelos de lenguaje locales.")
    parser.add_argument(
        "--modelos", default=",".join(MODELS), help="separados por coma (los tres de siempre)"
    )
    parser.add_argument("--rondas", type=int, default=3, help="cuántas veces cada pedido (3)")
    parser.add_argument("--respuestas", action="store_true", help="mostrar todas las respuestas")
    args = parser.parse_args()
    # PowerShell convierte "a,b" en "a b": valen la coma y el espacio.
    models = args.modelos.replace(",", " ").split()
    asyncio.run(run(models, max(1, args.rondas), args.respuestas))


if __name__ == "__main__":
    main()
