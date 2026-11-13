"""Vocabulario del protocolo motor ↔ interfaz: estados y tipos de mensaje.

La interfaz tiene su copia en `apps/desktop/src/engine/protocol.ts`. Cambiar
una obliga a cambiar la otra: lo verifica `tests/test_protocol.py`.
"""

from enum import StrEnum


class AssistantState(StrEnum):
    IDLE = "idle"
    LISTENING = "listening"
    THINKING = "thinking"
    SPEAKING = "speaking"


class ServerMessage(StrEnum):
    """Mensajes del motor a la interfaz."""

    HELLO = "hello"
    STATE_CHANGED = "state_changed"
    TRANSCRIPT_FINAL = "transcript_final"
    ASSISTANT_DELTA = "assistant_delta"
    ERROR = "error"


class ClientMessage(StrEnum):
    """Mensajes de la interfaz al motor."""

    ACTIVATE = "activate"
    CANCEL = "cancel"
