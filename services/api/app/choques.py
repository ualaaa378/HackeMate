"""Choque de fechas (tareas nocturnas 22/11): al confirmar un plan, ¿hay otro ese mismo día cerca?

«Cerca» = pueblo a `CHOQUE_KM` km o menos (el mismo pueblo cuenta). Solo cuentan los planes `publicado`.
Si hay choque, se proponen hasta 3 días libres (mismo tipo de día, laborable o fin de semana, y a la misma hora),
del más cercano al más lejano. La IA del bot elige entre ellos y lo redacta; quien crea el plan decide si lo cambia.
"""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import Evento, Municipio
from app.rutas.publico import distancia_km
from app.serializar import fecha_iso

CHOQUE_KM = 20.0
DIAS_A_MIRAR = 21
MAX_ALTERNATIVAS = 3


def _tz() -> ZoneInfo:
    return ZoneInfo(get_settings().zona_horaria)


def _coordenadas(db: Session) -> dict[str, tuple[float, float]]:
    return {m.nombre: (m.lat, m.lon) for m in db.scalars(select(Municipio)).all()}


def _cerca(coords: dict, a: str, b: str) -> float | None:
    """Distancia entre dos pueblos si están a CHOQUE_KM o menos; None si lejos o sin coordenadas."""
    if a == b:
        return 0.0
    if a not in coords or b not in coords:
        return None
    d = distancia_km(*coords[a], *coords[b])
    return round(d, 1) if d <= CHOQUE_KM else None


def _planes_del_dia(db: Session, dia: date, excluir: str | None) -> list[Evento]:
    tz = _tz()
    inicio = datetime.combine(dia, datetime.min.time(), tz)
    consulta = select(Evento).where(Evento.estado == "publicado", Evento.fecha_inicio >= inicio,
                                    Evento.fecha_inicio < inicio + timedelta(days=1))
    if excluir:
        consulta = consulta.where(Evento.id != excluir)
    return list(db.scalars(consulta.order_by(Evento.fecha_inicio)).all())


def choques(db: Session, fecha: datetime, municipio: str, excluir: str | None = None) -> dict:
    """{choques: [...], alternativas: [fechas ISO]}. Sin choque, las alternativas van vacías."""
    tz, coords = _tz(), _coordenadas(db)
    local = fecha.astimezone(tz)
    encontrados = []
    for e in _planes_del_dia(db, local.date(), excluir):
        d = _cerca(coords, municipio, e.municipio)
        if d is not None:
            encontrados.append({"evento_id": e.id, "titulo": e.titulo, "municipio": e.municipio,
                                "fecha_inicio": fecha_iso(e.fecha_inicio), "distancia_km": d})
    alternativas: list[str] = []
    if encontrados:
        finde = local.weekday() >= 5
        hoy = datetime.now(tz).date()
        candidatos = sorted(
            (local.date() + timedelta(days=n) for n in range(-DIAS_A_MIRAR, DIAS_A_MIRAR + 1) if n),
            key=lambda d: abs((d - local.date()).days),
        )
        for d in candidatos:
            if d <= hoy or (d.weekday() >= 5) != finde:
                continue
            if any(_cerca(coords, municipio, e.municipio) is not None for e in _planes_del_dia(db, d, excluir)):
                continue
            alternativas.append(fecha_iso(datetime.combine(d, local.timetz().replace(tzinfo=None), tz)))
            if len(alternativas) == MAX_ALTERNATIVAS:
                break
    return {"choques": encontrados, "alternativas": alternativas}
