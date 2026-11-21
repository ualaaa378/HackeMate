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
from app.modelos import Evento, Inscripcion, Lugar, Municipio, Publicador, Usuario


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


def evento_a_dict(e: Evento, inscritos: int = 0, privados: bool = False) -> dict:
    """`privados=True` solo para el organizador del evento o un moderador con sesión (bearer): añade
    `datos_ayuntamiento`. Nunca en rutas públicas, hacia el bot (X-Internal-Token) ni hacia la IA."""
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
        "frase_portada": e.frase_portada,
        "origen": {"canal": e.origen_canal, "url": e.origen_url, "importado_auto": e.importado_auto},
        "moderacion": {"motivo": e.motivo_moderacion, "score_spam": e.score_spam, "revisado_por": e.revisado_por},
        "creado_en": fecha_iso(e.creado_en),
        "actualizado_en": fecha_iso(e.actualizado_en),
    }
    # En el schema `descripcion` es string (no admite null): si no hay, no se envia.
    if e.descripcion is not None:
        datos["descripcion"] = e.descripcion
    if privados:
        datos["datos_ayuntamiento"] = e.datos_ayuntamiento
    return datos


def eventos_a_dict(db: Session, eventos: list[Evento], privados: bool = False) -> list[dict]:
    inscritos = inscritos_por_evento(db, (e.id for e in eventos))
    return [evento_a_dict(e, inscritos.get(e.id, 0), privados) for e in eventos]


def publicador_a_dict(p: Publicador, con_contacto: bool = True) -> dict:
    """`con_contacto=False` para el público: sin teléfono, email ni telegram_id (el schema no los exige)."""
    datos = {
        "id": p.id,
        "nombre": p.nombre,
        "tipo": p.tipo,
        "municipio": p.municipio,
        "descripcion": p.descripcion,
        "estado": p.estado,
        "nivel_confianza": p.nivel_confianza,
        "aprobaciones": p.aprobaciones,
        "automatizaciones_pausadas": p.automatizaciones_pausadas,
        "categorias_habituales": list(p.categorias_habituales or []),
        "fuentes": [{"id": f.id, "canal": f.canal, "url": f.url, "activa": f.activa} for f in p.fuentes],
        "usuario_id": p.usuario_id,
        "creado_en": fecha_iso(p.creado_en),
    }
    if con_contacto:
        datos["telefono"] = p.telefono
        datos["email"] = p.email
        datos["telegram_id"] = p.telegram_id
    return datos


def usuario_a_dict(u: Usuario) -> dict:
    """Completo, con teléfono y telegram_id: solo para el propio usuario y los servicios internos."""
    return {
        "id": u.id,
        "nombre": u.nombre,
        "rol": u.rol,
        "telefono": u.telefono,
        "whatsapp_verificado": u.whatsapp_verificado,
        "email": u.email,
        "telegram_id": u.telegram_id,
        "municipio": u.municipio,
        "lat": u.lat,
        "lon": u.lon,
        "gustos": list(u.gustos or []),
        "etiquetas_interes": list(u.etiquetas_interes or []),
        "formato_aviso": u.formato_aviso,
        "acepta_avisos": u.acepta_avisos,
        "radio_km": u.radio_km,
        "publicador_id": u.publicador_id,
        "creado_en": fecha_iso(u.creado_en),
    }
