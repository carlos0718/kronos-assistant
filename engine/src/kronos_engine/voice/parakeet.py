"""Voz a texto con Parakeet v3 (ONNX).

Es mucho más rápido que whisper en el procesador: tarda según lo que dura la
frase, en lugar de procesar siempre una ventana de 30 segundos. Reconoce solo
el idioma, entre 25 europeos: no se le puede fijar el español, y con una
palabra suelta a veces contesta en otro (ver docs/MEDICIONES.md).
"""

import asyncio
import threading
from collections.abc import Callable

import numpy as np

from kronos_engine.voice import SAMPLE_RATE

MODEL = "nemo-parakeet-tdt-0.6b-v3"
# Con más hilos no tarda menos y gasta el doble de procesador.
_THREADS = 4

# Recibe audio de 16 kHz y devuelve el texto.
Recognize = Callable[[np.ndarray], str]


def _load_parakeet() -> Recognize:
    # Se importan acá porque tardan: así no demoran el arranque del motor.
    import onnx_asr
    import onnxruntime

    options = onnxruntime.SessionOptions()
    options.intra_op_num_threads = _THREADS
    options.log_severity_level = 4
    # int8 en CPU: la opción liviana que funciona en cualquier equipo.
    model = onnx_asr.load_model(
        MODEL, quantization="int8", sess_options=options, providers=["CPUExecutionProvider"]
    )

    def recognize(audio: np.ndarray) -> str:
        return model.recognize(audio, sample_rate=SAMPLE_RATE)

    return recognize


class ParakeetStt:
    """Transcribe audio de 16 kHz.

    El modelo se descarga la primera vez (unos 640 MB) y se carga una sola
    vez. `preload` permite hacerlo al arrancar, sin esperar a que el usuario
    hable.
    """

    def __init__(self, load: Callable[[], Recognize] = _load_parakeet) -> None:
        self._load = load
        self._recognize: Recognize | None = None
        self._lock = threading.Lock()

    def preload(self) -> None:
        threading.Thread(target=self._loaded, daemon=True).start()

    def _loaded(self) -> Recognize:
        with self._lock:
            if self._recognize is None:
                self._recognize = self._load()
            return self._recognize

    def _transcribe(self, audio: np.ndarray) -> str:
        return self._loaded()(audio.astype(np.float32, copy=False)).strip()

    async def transcribe(self, audio: np.ndarray) -> str:
        return await asyncio.to_thread(self._transcribe, audio)
