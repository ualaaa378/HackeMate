"""Modelo -> JSON de la API, con la forma exacta de contracts/schemas/*.json.

Las fechas se guardan en UTC (FechaUTC) y se devuelven en ISO 8601 con la zona de Madrid
(p. ej. 2026-11-29T09:00:00+01:00), igual que en los fixtures.
"""

from collections.abc import Iterable
from datetime import datetime
from functools import lru_cache
from zoneinfo import ZoneInfo

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import Evento, Inscripcion, Lugar, Municipio


@lru_cache
def _zona() -> ZoneInfo:
    return ZoneInfo(get_settings().zona_horaria)


def fecha_iso(valor: datetime | None) -> str | None:
    return valor.astimezone(_zona()).isoformat() if valor else None


def municipio_a_dict(m: Municipio) -> dict:
    return {"nombre": m.nombre, "lat": m.lat, "lon": m.lon}


def lugar_a_dict(lugar: Lugar) -> dict:
    return {
        "id": lugar.id,
        "nombre": lugar.nombre,
        "tipo": lugar.tipo,
        "municipio": lugar.municipio,
        "descripcion": lugar.descripcion,
        "direccion": lugar.direccion,
        "telefono": lugar.telefono,
        "web": lugar.web,
        "lat": lugar.lat,
        "lon": lugar.lon,
        "coordenadas_exactas": lugar.coordenadas_exactas,
        "ruta": lugar.ruta,
        "fuentes": list(lugar.fuentes or []),
    }


def inscritos_por_evento(db: Session, ids: Iterable[str]) -> dict[str, int]:
    """Personas apuntadas (suma de plazas de las inscripciones confirmadas) de cada evento."""
    ids = list(ids)
    if not ids:
        return {}
    filas = db.execute(
        select(Inscripcion.evento_id, func.coalesce(func.sum(Inscripcion.plazas), 0))
        .where(Inscripcion.evento_id.in_(ids), Inscripcion.estado == "confirmada")
        .group_by(Inscripcion.evento_id)
    ).all()
    return {evento_id: int(total) for evento_id, total in filas}


def evento_a_dict(e: Evento, inscritos: int = 0) -> dict:
    datos = {
        "id": e.id,
        "titulo": e.titulo,
        "categoria": e.categoria,
        "etiquetas": list(e.etiquetas or []),
        "municipio": e.municipio,
        "lugar": e.lugar,
        "lat": e.lat,
        "lon": e.lon,
        "fecha_inicio": fecha_iso(e.fecha_inicio),
        "fecha_fin": fecha_iso(e.fecha_fin),
        "precio_eur": e.precio_eur,
        "es_gratuito": e.es_gratuito,
        "plazas_totales": e.plazas_totales,
        "plazas_libres": e.plazas_libres,
        "inscritos": inscritos,
        "estado": e.estado,
        "publicador_id": e.publicador_id,
        "publicador_nombre": e.publicador.nombre if e.publicador else None,
        "imagen_url": e.imagen_url,
        "origen": {"canal": e.origen_canal, "url": e.origen_url, "importado_auto": e.importado_auto},
        "moderacion": {"motivo": e.motivo_moderacion, "score_spam": e.score_spam, "revisado_por": e.revisado_por},
        "creado_en": fecha_iso(e.creado_en),
        "actualizado_en": fecha_iso(e.actualizado_en),
    }
    # En el schema `descripcion` es string (no admite null): si no hay, no se envia.
    if e.descripcion is not None:
        datos["descripcion"] = e.descripcion
    return datos


def eventos_a_dict(db: Session, eventos: list[Evento]) -> list[dict]:
    inscritos = inscritos_por_evento(db, (e.id for e in eventos))
    return [evento_a_dict(e, inscritos.get(e.id, 0)) for e in eventos]
