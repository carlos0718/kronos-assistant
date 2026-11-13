"""Detección de voz con Silero (ONNX), cuadro por cuadro.

Usa el modelo que ya viene dentro de faster-whisper, así no hay que descargar
ni empaquetar otro archivo. faster-whisper solo lo aplica a audios completos;
acá se conserva el estado entre cuadros para usarlo en vivo.
"""

from importlib.util import find_spec
from pathlib import Path

import numpy as np

from kronos_engine.voice import FRAME_SAMPLES

# Muestras del cuadro anterior que el modelo recibe como contexto.
_CONTEXT_SAMPLES = 64


def _model_path() -> Path:
    # Se ubica el paquete sin importarlo, porque importarlo tarda.
    spec = find_spec("faster_whisper")
    if spec is None or spec.origin is None:
        raise RuntimeError("Falta faster-whisper, que trae el modelo de detección de voz.")
    return Path(spec.origin).parent / "assets" / "silero_vad_v6.onnx"


class SileroVad:
    def __init__(self) -> None:
        import onnxruntime

        options = onnxruntime.SessionOptions()
        options.inter_op_num_threads = 1
        options.intra_op_num_threads = 1
        options.log_severity_level = 4
        self._session = onnxruntime.InferenceSession(
            str(_model_path()), providers=["CPUExecutionProvider"], sess_options=options
        )
        self.reset()

    def reset(self) -> None:
        """Olvida lo escuchado. Se llama al empezar cada escucha."""
        self._h = np.zeros((1, 1, 128), dtype=np.float32)
        self._c = np.zeros((1, 1, 128), dtype=np.float32)
        self._context = np.zeros(_CONTEXT_SAMPLES, dtype=np.float32)

    def probability(self, frame: np.ndarray) -> float:
        """Probabilidad (0 a 1) de que el cuadro contenga voz."""
        if frame.shape != (FRAME_SAMPLES,):
            raise ValueError(f"El cuadro debe tener {FRAME_SAMPLES} muestras, no {frame.shape}")
        frame = frame.astype(np.float32, copy=False)
        batch = np.concatenate([self._context, frame])[np.newaxis, :]
        output, self._h, self._c = self._session.run(
            None, {"input": batch, "h": self._h, "c": self._c}
        )
        self._context = frame[-_CONTEXT_SAMPLES:].copy()
        return float(np.asarray(output).reshape(-1)[0])
