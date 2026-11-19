"""Claves guardadas en el Administrador de credenciales de Windows.

Windows las cifra con la cuenta del usuario: otro usuario de la computadora no
las puede leer, y no quedan en ningún archivo de Kronos. Se ven (y se pueden
borrar) en Panel de control → Administrador de credenciales → Credenciales de
Windows, con el nombre «Kronos/…».
"""

import ctypes
import sys

# CRED_TYPE_GENERIC: una clave de una aplicación, no una contraseña de red.
_GENERIC = 1
# CRED_PERSIST_LOCAL_MACHINE: queda guardada en esta computadora, para este usuario.
_PERSIST_LOCAL_MACHINE = 2
_ERROR_NOT_FOUND = 1168


class _FileTime(ctypes.Structure):
    _fields_ = [("low", ctypes.c_uint32), ("high", ctypes.c_uint32)]


class _Credential(ctypes.Structure):
    """La estructura CREDENTIALW de Windows."""

    _fields_ = [
        ("Flags", ctypes.c_uint32),
        ("Type", ctypes.c_uint32),
        ("TargetName", ctypes.c_wchar_p),
        ("Comment", ctypes.c_wchar_p),
        ("LastWritten", _FileTime),
        ("CredentialBlobSize", ctypes.c_uint32),
        ("CredentialBlob", ctypes.POINTER(ctypes.c_ubyte)),
        ("Persist", ctypes.c_uint32),
        ("AttributeCount", ctypes.c_uint32),
        ("Attributes", ctypes.c_void_p),
        ("TargetAlias", ctypes.c_wchar_p),
        ("UserName", ctypes.c_wchar_p),
    ]


class CredentialError(OSError):
    """Windows no dejó guardar, leer o borrar la clave."""


class WindowsCredentials:
    """Implementa `SecretStore` con el Administrador de credenciales."""

    def read(self, name: str) -> str | None:
        if sys.platform != "win32":
            raise CredentialError("El Administrador de credenciales solo existe en Windows.")
        found = ctypes.POINTER(_Credential)()
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        if not advapi.CredReadW(name, _GENERIC, 0, ctypes.byref(found)):
            if ctypes.get_last_error() == _ERROR_NOT_FOUND:
                return None
            raise CredentialError(f"No se pudo leer la clave {name}.")
        try:
            credential = found.contents
            blob = ctypes.string_at(credential.CredentialBlob, credential.CredentialBlobSize)
            # Se guarda en UTF-16, como las demás aplicaciones de Windows.
            return blob.decode("utf-16-le")
        finally:
            advapi.CredFree(found)

    def write(self, name: str, secret: str) -> None:
        if sys.platform != "win32":
            raise CredentialError("El Administrador de credenciales solo existe en Windows.")
        blob = secret.encode("utf-16-le")
        buffer = (ctypes.c_ubyte * len(blob)).from_buffer_copy(blob)
        credential = _Credential(
            Type=_GENERIC,
            TargetName=name,
            CredentialBlobSize=len(blob),
            CredentialBlob=ctypes.cast(buffer, ctypes.POINTER(ctypes.c_ubyte)),
            Persist=_PERSIST_LOCAL_MACHINE,
            UserName="Kronos",
        )
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        if not advapi.CredWriteW(ctypes.byref(credential), 0):
            raise CredentialError(f"No se pudo guardar la clave {name}.")

    def delete(self, name: str) -> None:
        if sys.platform != "win32":
            raise CredentialError("El Administrador de credenciales solo existe en Windows.")
        advapi = ctypes.WinDLL("advapi32", use_last_error=True)
        if (
            not advapi.CredDeleteW(name, _GENERIC, 0)
            and ctypes.get_last_error() != _ERROR_NOT_FOUND
        ):
            raise CredentialError(f"No se pudo borrar la clave {name}.")
