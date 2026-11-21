"""Fechas y zonas horarias escritas como se dicen en voz alta."""

from datetime import date, datetime

# Escritos a mano para no depender del idioma en que esté configurado el sistema.
_DAYS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
_MONTHS = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def spoken_date(day: date) -> str:
    """«jueves 19 de noviembre de 2026»."""
    return f"{_DAYS[day.weekday()]} {day.day} de {_MONTHS[day.month - 1]} de {day.year}"


def spoken_zone(moment: datetime) -> str:
    """«UTC-3, Hora estándar de Argentina», o "" si `moment` no tiene zona."""
    offset = moment.utcoffset()
    if offset is None:
        return ""
    minutes = int(offset.total_seconds()) // 60
    sign = "-" if minutes < 0 else "+"
    hours, rest = divmod(abs(minutes), 60)
    zone = f"UTC{sign}{hours}" + (f":{rest:02d}" if rest else "")
    # Windows le da a la zona un nombre en el idioma del sistema; otros, solo «-03».
    name = moment.tzname() or ""
    if any(char.isalpha() for char in name) and not name.startswith("UTC"):
        zone += f", {name}"
    return zone
