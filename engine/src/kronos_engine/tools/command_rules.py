"""Qué nivel de permiso exige un comando de terminal.

Son reglas sobre el texto del comando, no un modelo: el modelo propone el
comando, este código decide cuánto cuesta ejecutarlo. Una lista de prohibidos
nunca es completa, así que lo que no se reconoce no se ejecuta solo: pide
confirmación (nivel 2), y lo que no se puede leer (comandos codificados u
ofuscados) pide la clave secreta (nivel 3). Ver «Niveles de permiso» en el README.
"""

import re
from dataclasses import dataclass

from kronos_engine.core.tools import PermissionLevel

# Los verbos de borrado de cmd y de PowerShell (con sus alias).
_DELETE = r"(?:rd|rmdir|del|erase|rm|ri|remove-item)"
# Rutas del sistema: borrar algo adentro es romper Windows.
_SYSTEM_DIR = (
    r"(?:%systemroot%|%windir%|%programfiles%|%programdata%"
    r"|\$env:(?:systemroot|windir|programfiles|programdata)"
    r"|[a-z]:[\\/](?:windows|programdata|program files)\b)"
)
# Una carpeta que no se borra entera: la raíz de un disco o la del usuario.
_ROOT = (
    r"(?:(?<![\w.\\/-])[a-z]:[\\/]?|(?<=\s)[\\/]"
    r"|%userprofile%|\$env:userprofile|\$home|(?<=\s)~"
    r"|[a-z]:[\\/]users(?:[\\/][^\\/\s]+)?)"
)
_WHOLE_ROOT = rf"{_ROOT}[\\/]?\*?(?:\.\*)?(?=\s|$)"

# Cada regla: (patrón, motivo). El motivo no cita el comando, que puede tener datos privados.
_Rule = tuple[re.Pattern[str], str]


def _rules(*pairs: tuple[str, str]) -> list[_Rule]:
    return [(re.compile(pattern), reason) for pattern, reason in pairs]


_FORBIDDEN = _rules(
    (r"\bformat-volume\b|\bformat(?![-\w])\s+(?:[a-z]:|/)", "formatea un disco"),
    (r"\b(?:diskpart|clear-disk|remove-partition|initialize-disk|mkfs)\b", "modifica discos"),
    (r"\bcipher\b.*\s/w\b", "borra el espacio libre del disco"),
    (rf"\b{_DELETE}\b.*{_SYSTEM_DIR}", "borra carpetas del sistema"),
    (rf"\b{_DELETE}\b.*{_WHOLE_ROOT}", "borra un disco o la carpeta del usuario"),
    (
        r"\b(?:cmdkey\s+/list|vaultcmd|get-storedcredential|passwordvault|credentialmanager"
        r"|mimikatz|lsass|ntds\.dit)\b",
        "lee las credenciales guardadas",
    ),
    (r"[\\/]\.ssh\b|\bid_(?:rsa|ed25519|ecdsa|dsa)\b", "toca las claves SSH"),
    (r"\breg(?:\.exe)?\s+save\b.*\b(?:sam|security|system)\b", "copia las claves de Windows"),
    (
        r"microsoft[\\/](?:credentials|protect|vault)\b|\bsecret-key\b|kronos[\\/](?:anthropic|openai)",
        "toca las claves guardadas",
    ),
)

_CRITICAL = _rules(
    # No se puede leer qué hace: el texto no lo dice.
    (r"-e(?:nc?|ncodedcommand)?\b\s+[a-z0-9+/=]{4,}", "es un comando codificado"),
    (r"\b(?:invoke-expression|iex)\b|frombase64string|\[char\]|\)\s*\.\s*invoke\(", "es ilegible"),
    (r"""["']\s*\+\s*["']|&\s*\(|\.\s*\(\s*["']""", "arma el comando con texto"),
    # Antivirus, firewall y protecciones.
    (
        r"\b(?:set|add|remove)-mppreference\b|disablerealtimemonitoring|tamperprotection"
        r"|mpcmdrun.*-removedefinitions",
        "cambia el antivirus",
    ),
    (
        r"\bnetsh\b.*\b(?:advfirewall|firewall)\b|\b(?:set|new|remove|disable|enable)-netfirewall"
        r"|\b(?:set|new)-netipsec",
        "cambia el firewall",
    ),
    (
        r"\b(?:stop-service|set-service|sc(?:\.exe)?\s+(?:stop|config|delete|create))\b"
        r".*\b(?:windefend|mpssvc|wscsvc|sense|wdfilter)\b",
        "apaga un servicio de seguridad",
    ),
    # Arranque y registro.
    (r"\b(?:bcdedit|bcdboot|bootcfg|regedit|regini)\b", "cambia el arranque o el registro"),
    (
        r"\breg(?:\.exe)?\s+(?:add|delete|import|load|unload|restore|copy)\b",
        "cambia el registro",
    ),
    (
        r"\b(?:set|new|remove|clear|rename|copy|move)-item(?:property)?\b"
        r".*(?:\bhk(?:lm|cu|cr|u|cc|pd):|registry::)",
        "cambia el registro",
    ),
    (
        r"\b(?:schtasks(?:\.exe)?\s+/(?:create|change)|register-scheduledtask|new-scheduledtask"
        r"|new-service|sc(?:\.exe)?\s+(?:create|config))\b|shell:(?:common )?startup"
        r"|start menu[\\/]programs[\\/]startup",
        "programa algo para que corra solo",
    ),
    (r"\bset-executionpolicy\b", "cambia las políticas de ejecución"),
    # Descargar y ejecutar.
    (
        r"\b(?:invoke-webrequest|iwr|invoke-restmethod|irm|curl|wget|start-bitstransfer|bitsadmin"
        r"|certutil)\b"
        r".*(?:\|\s*(?:powershell|pwsh|cmd|sh|bash)\b|\.(?:exe|msi|bat|cmd|ps1|vbs|js|dll|scr)\b"
        r"|;\s*(?:start-process|start|&)|&&|-urlcache)",
        "descarga y ejecuta un programa",
    ),
    (r"\b(?:downloadstring|downloadfile|downloaddata)\b|net\.webclient", "descarga desde código"),
    (
        r"\b(?:mshta|msiexec|regsvr32|rundll32|wscript|cscript|installutil|msbuild)\b",
        "ejecuta código con una herramienta del sistema",
    ),
    # Usuarios, contraseñas y permisos de administrador.
    (
        r"\bnet1?\s+(?:user|localgroup|accounts)\b|\b(?:new|set|remove|enable|disable)-localuser\b"
        r"|\b(?:add|remove)-localgroupmember\b|\bwmic\s+useraccount\b|\bpasswd\b",
        "cambia usuarios o contraseñas",
    ),
    (
        r"-verb\s+runas|\brunas\b|\b(?:sudo|gsudo|psexec|takeown|icacls|cacls)\b",
        "pide permisos de administrador",
    ),
    # Esconder lo que pasó o borrar las copias de seguridad.
    (
        r"\bwevtutil\b.*\bcl\b|\bclear-eventlog\b|\bauditpol\b|\bvssadmin\b.*\bdelete\b"
        r"|\bwbadmin\b.*\bdelete\b",
        "borra registros o copias de seguridad",
    ),
)

# Los separadores de comandos: «;», «|», «&», «&&», «||» y el salto de línea.
_SEPARATORS = re.compile(r"[;&|\r\n]+")
# Los escapes de PowerShell (`) y de cmd (^) parten una palabra sin cambiar lo que hace.
_ESCAPES = re.compile(r"[`^]")
_QUOTES = re.compile(r"[\"']")


@dataclass(frozen=True)
class Verdict:
    level: PermissionLevel
    # Por qué sube de nivel, sin citar el comando. Vacío en el nivel 2 común.
    reason: str = ""


def classify(command: str) -> Verdict:
    """El nivel de un comando. Nunca baja de 2: ninguno corre sin confirmación."""
    flat = _ESCAPES.sub("", command).casefold()
    # Con comillas se ven las ofuscaciones («"Remove"+"-Item"»); sin ellas, las rutas y flags.
    plain = _QUOTES.sub("", flat)
    pieces = [piece.strip() for piece in _SEPARATORS.split(plain) if piece.strip()]
    for level, rules in (
        (PermissionLevel.FORBIDDEN, _FORBIDDEN),
        (PermissionLevel.CRITICAL, _CRITICAL),
    ):
        for pattern, reason in rules:
            if any(pattern.search(text) for text in (flat, plain, *pieces)):
                return Verdict(level, reason)
    return Verdict(PermissionLevel.SENSITIVE)
