"""Arranque del motor como proceso, tal como lo lanza la app de escritorio."""

import json
import os
import subprocess
import sys

import httpx

TOKEN = "token-de-prueba"


def test_responde_con_la_entrada_vigilada_y_termina_cuando_la_app_la_cierra() -> None:
    env = dict(
        os.environ,
        KRONOS_TOKEN=TOKEN,
        KRONOS_PARENT_WATCH="1",
        KRONOS_PIPELINE="demo",  # Sin micrófono ni modelos.
        PYTHONUNBUFFERED="1",
    )
    engine = subprocess.Popen(
        [sys.executable, "-m", "kronos_engine"],
        stdin=subprocess.PIPE,
        stdout=subprocess.PIPE,
        env=env,
        text=True,
    )
    try:
        prefix, _, ready = engine.stdout.readline().partition(" ")
        assert prefix == "KRONOS_READY"
        port = json.loads(ready)["port"]

        response = httpx.get(
            f"http://127.0.0.1:{port}/health",
            headers={"Authorization": f"Bearer {TOKEN}"},
            timeout=20,
        )
        assert response.status_code == 200

        engine.stdin.close()  # La app se cerró.
        assert engine.wait(timeout=10) == 0
    finally:
        engine.kill()
        engine.stdout.close()
