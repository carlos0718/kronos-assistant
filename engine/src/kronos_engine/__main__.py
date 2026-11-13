"""Punto de entrada del motor.

Arranque:
1. Lee el token de la variable de entorno KRONOS_TOKEN (la define la app de
   escritorio). Si falta, genera uno y lo informa, para poder probar a mano.
2. Abre un puerto libre en 127.0.0.1.
3. Informa por la salida estándar una línea `KRONOS_READY {json}` con el puerto.

Si KRONOS_PARENT_WATCH=1, el motor termina cuando se cierra su entrada
estándar. La app de escritorio la mantiene abierta mientras vive, así el motor
nunca queda huérfano aunque la app se cierre de golpe.
"""

import json
import os
import secrets
import socket
import sys
import threading

import uvicorn

from kronos_engine import PROTOCOL_VERSION, __version__
from kronos_engine.api.server import create_app

HOST = "127.0.0.1"
READY_PREFIX = "KRONOS_READY"
TOKEN_ENV = "KRONOS_TOKEN"
PARENT_WATCH_ENV = "KRONOS_PARENT_WATCH"


def _exit_when_stdin_closes() -> None:
    try:
        while sys.stdin.buffer.read(1024):
            pass
    finally:
        os._exit(0)


def main() -> None:
    token = os.environ.get(TOKEN_ENV)
    ready: dict[str, object] = {"protocol": PROTOCOL_VERSION, "version": __version__}
    if not token:
        # Modo manual de desarrollo: sin app de escritorio que provea el token.
        token = secrets.token_urlsafe(32)
        ready["dev_token"] = token

    if os.environ.get(PARENT_WATCH_ENV) == "1":
        threading.Thread(target=_exit_when_stdin_closes, daemon=True).start()

    sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    sock.bind((HOST, 0))  # Puerto 0: el sistema elige uno libre.
    # Se empieza a escuchar antes de avisar: las conexiones que lleguen mientras
    # el servidor termina de arrancar quedan en cola en lugar de ser rechazadas.
    sock.listen()
    ready["port"] = sock.getsockname()[1]

    print(f"{READY_PREFIX} {json.dumps(ready)}", flush=True)

    config = uvicorn.Config(create_app(token), log_level="warning", ws="websockets-sansio")
    uvicorn.Server(config).run(sockets=[sock])


if __name__ == "__main__":
    sys.exit(main())
