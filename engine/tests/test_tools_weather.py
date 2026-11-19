import asyncio
from typing import Any

import httpx
import pytest

from kronos_engine.core.tools import PermissionLevel, ToolError
from kronos_engine.tools.weather import WeatherTool

ROSARIO_SANTA_FE = {
    "name": "Rosario",
    "latitude": -32.95,
    "longitude": -60.64,
    "admin1": "Santa Fe",
    "country": "Argentina",
}
ROSARIO_URUGUAY = {
    "name": "Rosario",
    "latitude": -34.31,
    "longitude": -57.35,
    "admin1": "Colonia",
    "country": "Uruguay",
}
FORECAST = {
    "current": {
        "temperature_2m": 22.4,
        "apparent_temperature": 21.6,
        "relative_humidity_2m": 61,
        "weather_code": 2,
        "wind_speed_10m": 14.8,
    },
    "daily": {
        "time": ["2026-11-19", "2026-11-20"],
        "weather_code": [2, 61],
        "temperature_2m_max": [25.1, 19.6],
        "temperature_2m_min": [15.2, 13.9],
        "precipitation_probability_max": [10, 80],
    },
}


class OpenMeteo:
    """Responde como Open-Meteo y anota qué se le pidió."""

    def __init__(self, places: list[dict[str, Any]], fail: bool = False) -> None:
        self._places = places
        self._fail = fail
        self.requests: list[httpx.Request] = []

    def __call__(self, request: httpx.Request) -> httpx.Response:
        self.requests.append(request)
        if self._fail:
            raise httpx.ConnectError("sin internet", request=request)
        if request.url.host == "geocoding-api.open-meteo.com":
            return httpx.Response(200, json={"results": self._places} if self._places else {})
        return httpx.Response(200, json=FORECAST)


def run(service: OpenMeteo, **arguments: Any) -> str:
    tool = WeatherTool(transport=httpx.MockTransport(service))
    return asyncio.run(tool.run(arguments))


def test_es_una_accion_normal() -> None:
    assert WeatherTool().level == PermissionLevel.NORMAL


def test_pide_que_si_no_dijo_el_lugar_le_pregunte() -> None:
    assert "preguntale" in WeatherTool().spec.description.lower()


def test_dice_el_clima_de_ahora_y_el_de_hoy() -> None:
    result = run(OpenMeteo([ROSARIO_SANTA_FE]), place="Rosario")

    assert "Rosario, Santa Fe, Argentina" in result
    assert "22 grados" in result
    assert "parcialmente nublado" in result
    assert "mínima de 15" in result
    assert "máxima de 25" in result


def test_el_pronostico_de_manana() -> None:
    result = run(OpenMeteo([ROSARIO_SANTA_FE]), place="Rosario", day=1)

    assert "viernes 20 de noviembre" in result
    assert "lluvia" in result
    assert "80 %" in result
    # El de mañana no dice la temperatura de ahora.
    assert "22 grados" not in result


def test_con_la_provincia_elige_el_lugar_correcto() -> None:
    service = OpenMeteo([ROSARIO_URUGUAY, ROSARIO_SANTA_FE])

    result = run(service, place="Rosario, Santa Fe")

    assert "Santa Fe" in result
    forecast = service.requests[-1]
    assert forecast.url.params["latitude"] == "-32.95"
    # A Open-Meteo se le pide el nombre solo, sin la provincia.
    assert service.requests[0].url.params["name"] == "Rosario"


def test_si_no_existe_el_lugar_pide_preguntar() -> None:
    with pytest.raises(ToolError, match="Preguntale"):
        run(OpenMeteo([]), place="Narnia")


def test_sin_internet_lo_dice() -> None:
    with pytest.raises(ToolError, match="internet"):
        run(OpenMeteo([ROSARIO_SANTA_FE], fail=True), place="Rosario")


def test_sin_lugar_no_consulta_nada() -> None:
    service = OpenMeteo([ROSARIO_SANTA_FE])

    with pytest.raises(ToolError, match="Preguntale"):
        run(service, place=" ")

    assert service.requests == []


def test_no_pasa_de_la_semana() -> None:
    result = run(OpenMeteo([ROSARIO_SANTA_FE]), place="Rosario", day=30)

    # Open-Meteo da siete días: se pide el último que hay.
    assert "viernes 20 de noviembre" in result
