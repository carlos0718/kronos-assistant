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
    # Kronos pide que el usuario apruebe una acción delicada; después avisa cómo terminó.
    CONFIRMATION_REQUEST = "confirmation_request"
    CONFIRMATION_RESOLVED = "confirmation_resolved"
    # Kronos pide la clave secreta, que se escribe en pantalla; después avisa que se cerró.
    SECRET_REQUEST = "secret_request"
    SECRET_RESOLVED = "secret_resolved"
    ERROR = "error"


class ClientMessage(StrEnum):
    """Mensajes de la interfaz al motor."""

    ACTIVATE = "activate"
    CANCEL = "cancel"
    # El usuario contestó una confirmación con un clic.
    CONFIRM = "confirm"
    DENY = "deny"
    # El usuario escribió la clave secreta (`value`) o canceló el pedido.
    SECRET = "secret"
    SECRET_CANCEL = "secret_cancel"
