"""Cómo se le pide al usuario que apruebe una acción delicada.

El control de permisos pregunta a través de `ApprovalDesk`; quien conversa
con el usuario (el orquestador) contesta.
"""

import re
import unicodedata
from dataclasses import dataclass
from typing import Protocol


@dataclass(frozen=True)
class ApprovalRequest:
    action: str  # Nombre de la acción.
    summary: str  # Qué se va a hacer, en infinitivo: «cerrar Spotify».
    detail: str = ""  # El comando exacto, si lo hay.


class Approver(Protocol):
    async def confirm(self, request: ApprovalRequest) -> bool:
        """Le pregunta al usuario. Solo un sí claro aprueba."""
        ...


class SecretAsker(Protocol):
    async def ask_secret(self, request: ApprovalRequest) -> str | None:
        """Le pide al usuario que escriba la clave secreta. `None` si cancela o no contesta."""
        ...


class ApprovalDesk:
    """El lugar fijo donde se piden las confirmaciones.

    Las piezas del motor se arman antes de que exista la conversación: el
    control de permisos recibe este objeto y la conversación se conecta después.
    """

    def __init__(self) -> None:
        self._approver: Approver | None = None
        self._secret_asker: SecretAsker | None = None

    def connect(self, approver: Approver, secret_asker: SecretAsker | None = None) -> None:
        self._approver = approver
        self._secret_asker = secret_asker

    async def confirm(self, request: ApprovalRequest) -> bool:
        # Sin nadie a quien preguntarle, la respuesta es no.
        if self._approver is None:
            return False
        return await self._approver.confirm(request)

    async def ask_secret(self, request: ApprovalRequest) -> str | None:
        if self._secret_asker is None:
            return None
        return await self._secret_asker.ask_secret(request)


# El reconocedor de voz a veces transcribe un «no» corto como «yeah» o «north»
# (ver docs/MEDICIONES.md). Por eso la lista de síes es corta y «yeah» no está.
_YES = {"si", "dale", "confirmo", "confirmado", "hacelo", "adelante", "ok", "okay", "yes"}
# Así transcribió un «sí» suelto en las pruebas con micrófono. Ningún «no» salió así.
_YES |= {"c", "see"}
_NO = {"no", "cancela", "cancelar", "cancelalo", "para", "nunca", "tampoco", "nop"}


def parse_answer(text: str) -> bool | None:
    """Lo que el usuario contestó: sí, no, o `None` si no quedó claro.

    Ante la duda gana el no: una negación en la frase rechaza aunque también haya un sí.
    """
    plain = unicodedata.normalize("NFKD", text.casefold())
    plain = "".join(char for char in plain if not unicodedata.combining(char))
    words = set(re.findall(r"[a-z]+", plain))
    if words & _NO:
        return False
    if words & _YES:
        return True
    return None
