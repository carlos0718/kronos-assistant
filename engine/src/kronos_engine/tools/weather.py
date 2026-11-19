"""Acción: el clima de una ciudad o localidad, ahora y en los próximos días.

Lo consulta en Open-Meteo (https://open-meteo.com), gratis y sin clave: anda con
cualquier modelo, local o en la nube. Lo único que sale de la computadora es el
nombre del lugar.
"""

import logging
from collections.abc import Mapping
from datetime import date
from typing import Any

import httpx

from kronos_engine.core.spoken_time import spoken_date
from kronos_engine.core.tools import PermissionLevel, ToolError, ToolSpec
from kronos_engine.tools.apps import normalize

log = logging.getLogger(__name__)

_GEOCODING = "https://geocoding-api.open-meteo.com/v1/search"
_FORECAST = "https://api.open-meteo.com/v1/forecast"
_TIMEOUT = httpx.Timeout(10, connect=5)
# Open-Meteo da el pronóstico de hasta siete días, contando hoy.
_DAYS = 7
# Entre cuántos lugares con el mismo nombre se busca el de la provincia o el país dicho.
_SAME_NAME = 10

# Los códigos del tiempo de la Organización Meteorológica Mundial (WMO), que usa Open-Meteo.
_SKY = {
    0: "despejado",
    1: "mayormente despejado",
    2: "parcialmente nublado",
    3: "nublado",
    45: "con niebla",
    48: "con niebla y escarcha",
    51: "con llovizna leve",
    53: "con llovizna",
    55: "con llovizna intensa",
    56: "con llovizna helada",
    57: "con llovizna helada intensa",
    61: "con lluvia leve",
    63: "con lluvia",
    65: "con lluvia intensa",
    66: "con lluvia helada",
    67: "con lluvia helada intensa",
    71: "con nevadas leves",
    73: "con nevadas",
    75: "con nevadas intensas",
    77: "con granizo fino",
    80: "con chaparrones leves",
    81: "con chaparrones",
    82: "con chaparrones fuertes",
    85: "con chaparrones de nieve",
    86: "con chaparrones de nieve fuertes",
    95: "con tormenta",
    96: "con tormenta y granizo",
    99: "con tormenta y granizo fuerte",
}


def _sky(code: object) -> str:
    return _SKY.get(code if isinstance(code, int) else -1, "con tiempo variable")


def _degrees(value: object) -> str:
    return f"{round(float(value))} grados" if isinstance(value, int | float) else "sin dato"


def _label(place: Mapping[str, Any]) -> str:
    """«Rosario, Santa Fe, Argentina», sin repetir partes iguales."""
    parts = [place.get(key) for key in ("name", "admin1", "country")]
    return ", ".join(dict.fromkeys(str(part) for part in parts if part))


def _pick(places: list[dict[str, Any]], hints: list[str]) -> dict[str, Any]:
    """De los lugares con ese nombre, el de la provincia o el país dicho; si no, el más conocido."""
    for place in places:
        where = normalize(f"{place.get('admin1', '')} {place.get('country', '')}")
        if hints and all(normalize(hint) in where for hint in hints):
            return place
    return places[0]


class WeatherTool:
    spec = ToolSpec(
        "weather",
        "Da el clima de una ciudad o localidad: ahora y el pronóstico de hoy y de los próximos "
        "seis días, consultando internet. Si el usuario no dijo de qué lugar, no la uses: "
        "preguntale primero de qué ciudad o localidad quiere saber el clima.",
        {
            "type": "object",
            "required": ["place"],
            "properties": {
                "place": {
                    "type": "string",
                    "description": (
                        "La ciudad o localidad, como la dijo el usuario; si dijo la provincia o "
                        "el país, van después de una coma. Ejemplos: Córdoba; Rosario, Santa Fe; "
                        "Madrid, España."
                    ),
                },
                "day": {
                    "type": "integer",
                    "description": "Qué día: 0 es hoy, 1 mañana, hasta 6. Sin dato, hoy.",
                },
            },
        },
    )
    level = PermissionLevel.NORMAL

    def __init__(self, transport: httpx.AsyncBaseTransport | None = None) -> None:
        # Los tests pasan un Open-Meteo simulado.
        self._transport = transport

    async def describe(self, arguments: Mapping[str, Any]) -> str:
        return f"consultar el clima de {arguments.get('place') or 'un lugar'}"

    async def run(self, arguments: Mapping[str, Any]) -> str:
        name, *hints = [part.strip() for part in str(arguments.get("place") or "").split(",")]
        if not name:
            raise ToolError("Falta el lugar. Preguntale al usuario de qué ciudad o localidad.")
        day = arguments.get("day")
        day = min(max(day, 0), _DAYS - 1) if isinstance(day, int) else 0
        try:
            async with httpx.AsyncClient(timeout=_TIMEOUT, transport=self._transport) as client:
                place = await self._place(client, name, [hint for hint in hints if hint])
                forecast = await self._forecast(client, place)
        except httpx.HTTPError as exc:
            log.warning("No se pudo consultar el clima: %s", exc)
            raise ToolError("No se pudo consultar el clima. ¿Hay internet?") from exc
        # Sin el lugar: el registro no guarda dónde está el usuario.
        log.info("Se consultó el clima.")
        return _report(_label(place), forecast, day)

    async def _place(
        self, client: httpx.AsyncClient, name: str, hints: list[str]
    ) -> dict[str, Any]:
        params: dict[str, str | int] = {
            "name": name,
            "count": _SAME_NAME,
            "language": "es",
            "format": "json",
        }
        response = await client.get(_GEOCODING, params=params)
        response.raise_for_status()
        places = response.json().get("results") or []
        if not places:
            raise ToolError(
                f"No encontré ningún lugar que se llame «{name}». "
                "Preguntale al usuario de qué ciudad o localidad habla."
            )
        return _pick(places, hints)

    async def _forecast(self, client: httpx.AsyncClient, place: Mapping[str, Any]) -> Any:
        params = {
            "latitude": place["latitude"],
            "longitude": place["longitude"],
            "current": "temperature_2m,apparent_temperature,relative_humidity_2m,"
            "weather_code,wind_speed_10m",
            "daily": "weather_code,temperature_2m_max,temperature_2m_min,"
            "precipitation_probability_max",
            "timezone": "auto",
            "forecast_days": _DAYS,
        }
        response = await client.get(_FORECAST, params=params)
        response.raise_for_status()
        return response.json()


def _report(label: str, forecast: Mapping[str, Any], day: int) -> str:
    daily = forecast.get("daily") or {}
    days = daily.get("time") or []
    index = min(day, len(days) - 1) if days else 0

    def at(key: str) -> object:
        values = daily.get(key) or []
        return values[index] if index < len(values) else None

    rain = at("precipitation_probability_max")
    outlook = (
        f"{_sky(at('weather_code'))}, mínima de {_degrees(at('temperature_2m_min'))} y máxima "
        f"de {_degrees(at('temperature_2m_max'))}, probabilidad de lluvia "
        f"{rain if rain is not None else 'sin dato'} %"
    )
    if index > 0 and days:
        when = spoken_date(date.fromisoformat(days[index]))
        return f"Pronóstico en {label} para el {when}: {outlook}."
    now = forecast.get("current") or {}
    return (
        f"Clima en {label} ahora: {_degrees(now.get('temperature_2m'))} (sensación térmica de "
        f"{_degrees(now.get('apparent_temperature'))}), {_sky(now.get('weather_code'))}, "
        f"humedad {now.get('relative_humidity_2m', 'sin dato')} %, viento de "
        f"{round(float(now.get('wind_speed_10m') or 0))} km/h. Hoy: {outlook}."
    )
