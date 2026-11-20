"""iCalendar (RFC 5545) generado a mano, sin dependencias.

- Fechas en UTC con `Z` (Google Calendar, Outlook y Apple las convierten a la zona de quien lo abre).
- Eventos con la etiqueta `sin_hora`: de día completo (`VALUE=DATE`, en la fecha de Madrid), porque la hora
  guardada no es real.
- Sin `fecha_fin`: dura 2 horas.
- Textos escapados (`\\ ; , salto de línea`) y líneas plegadas a 75 octetos con CRLF.
"""

import re
import unicodedata
from datetime import date, datetime, timedelta, timezone
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.modelos import Evento

CRLF = "\r\n"
MAX_OCTETOS = 75
DURACION_POR_DEFECTO = timedelta(hours=2)
PRODID = "-//HackeMate//Reactiva tu pueblo//ES"
DOMINIO_UID = "hackemate"
ESTADOS_ICS = {"cancelado": "CANCELLED"}


def escapar(texto: str) -> str:
    """TEXT de RFC 5545 §3.3.11."""
    texto = texto.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return texto.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def plegar(linea: str) -> str:
    """Parte la línea en trozos de como mucho 75 octetos (sin cortar un carácter UTF-8); las
    continuaciones empiezan por un espacio, que también cuenta."""
    trozos, actual, octetos = [], "", 0
    limite = MAX_OCTETOS
    for caracter in linea:
        n = len(caracter.encode("utf-8"))
        if octetos + n > limite:
            trozos.append(actual)
            actual, octetos, limite = " ", 1, MAX_OCTETOS
        actual += caracter
        octetos += n
    trozos.append(actual)
    return CRLF.join(trozos)


def _utc(valor: datetime) -> str:
    return valor.astimezone(timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _dia(valor: date) -> str:
    return valor.strftime("%Y%m%d")


def _zona() -> ZoneInfo:
    return ZoneInfo(get_settings().zona_horaria)


def es_dia_completo(evento: Evento) -> bool:
    return "sin_hora" in (evento.etiquetas or [])


def _fechas(evento: Evento) -> list[str]:
    if es_dia_completo(evento):
        inicio = evento.fecha_inicio.astimezone(_zona()).date()
        fin = evento.fecha_fin.astimezone(_zona()).date() if evento.fecha_fin else inicio
        # DTEND de un evento de día completo es exclusivo: el día siguiente al último.
        fin = max(fin, inicio) + timedelta(days=1)
        return [f"DTSTART;VALUE=DATE:{_dia(inicio)}", f"DTEND;VALUE=DATE:{_dia(fin)}"]
    fin = evento.fecha_fin or evento.fecha_inicio + DURACION_POR_DEFECTO
    return [f"DTSTART:{_utc(evento.fecha_inicio)}", f"DTEND:{_utc(fin)}"]


def _descripcion(evento: Evento) -> str:
    partes = []
    if evento.descripcion:
        partes.append(evento.descripcion.strip())
    if evento.es_gratuito:
        partes.append("Gratuito")
    elif evento.precio_eur is not None:
        partes.append(f"Precio: {evento.precio_eur:g} €")
    if evento.publicador is not None:
        partes.append(f"Organiza: {evento.publicador.nombre}")
    return "\n\n".join(partes)


def vevento(evento: Evento, dtstamp: datetime) -> list[str]:
    lugar = ", ".join(p for p in (evento.lugar, evento.municipio) if p)
    lineas = [
        "BEGIN:VEVENT",
        f"UID:{evento.id}@{DOMINIO_UID}",
        f"DTSTAMP:{_utc(dtstamp)}",
        *_fechas(evento),
        f"SUMMARY:{escapar(evento.titulo)}",
        f"LOCATION:{escapar(lugar)}",
        f"GEO:{evento.lat:.6f};{evento.lon:.6f}",
        f"STATUS:{ESTADOS_ICS.get(evento.estado, 'CONFIRMED')}",
        f"CATEGORIES:{escapar(evento.categoria)}",
    ]
    descripcion = _descripcion(evento)
    if descripcion:
        lineas.append(f"DESCRIPTION:{escapar(descripcion)}")
    if evento.origen_url:
        lineas.append(f"URL:{evento.origen_url}")
    if evento.actualizado_en:
        lineas.append(f"LAST-MODIFIED:{_utc(evento.actualizado_en)}")
    lineas.append("END:VEVENT")
    return lineas


def calendario(eventos: list[Evento], nombre: str | None = None, dtstamp: datetime | None = None) -> str:
    """El .ics completo. `dtstamp` (por defecto, ahora) se fija en los tests."""
    dtstamp = dtstamp or datetime.now(timezone.utc)
    lineas = ["BEGIN:VCALENDAR", f"PRODID:{PRODID}", "VERSION:2.0", "CALSCALE:GREGORIAN", "METHOD:PUBLISH"]
    if nombre:
        lineas.append(f"X-WR-CALNAME:{escapar(nombre)}")
    for evento in eventos:
        lineas.extend(vevento(evento, dtstamp))
    lineas.append("END:VCALENDAR")
    return CRLF.join(plegar(linea) for linea in lineas) + CRLF


def nombre_fichero(titulo: str) -> str:
    """Nombre ASCII para Content-Disposition: «II Ruta Solidaria» -> ii-ruta-solidaria.ics."""
    ascii_ = unicodedata.normalize("NFKD", titulo).encode("ascii", "ignore").decode("ascii").lower()
    slug = re.sub(r"[^a-z0-9]+", "-", ascii_).strip("-")[:60].strip("-")
    return f"{slug or 'evento'}.ics"
