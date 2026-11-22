"""Lectura pública de información permanente: municipios y lugares (mapa)."""

import math
import uuid
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy import Select, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import TIPOS_LUGAR, Lugar, Municipio
from app.paginacion import Pagina, pagina, paginar, paginar_lista
from app.serializar import lugar_a_dict, municipio_a_dict

router = APIRouter(prefix="/api/v1", tags=["eventos"])

KM_POR_GRADO = 111.32


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Haversine. Se calcula en Python para que funcione igual en SQLite y PostgreSQL."""
    rad = math.radians
    a = math.sin(rad(lat2 - lat1) / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(
        rad(lon2 - lon1) / 2
    ) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def hay_radio(lat: float | None, lon: float | None, radio_km: float | None) -> bool:
    return lat is not None and lon is not None and radio_km is not None


def en_caja(consulta: Select, modelo, lat: float, lon: float, radio_km: float) -> Select:
    """Prefiltro en SQL con un rectángulo que contiene el círculo; el corte exacto lo hace `dentro_del_radio`."""
    dlat = radio_km / KM_POR_GRADO
    dlon = radio_km / (KM_POR_GRADO * max(math.cos(math.radians(lat)), 0.01))
    return consulta.where(
        modelo.lat.between(lat - dlat, lat + dlat),
        modelo.lon.between(lon - dlon, lon + dlon),
    )


def dentro_del_radio(filas: list, lat: float, lon: float, radio_km: float) -> list:
    return [f for f in filas if distancia_km(lat, lon, f.lat, f.lon) <= radio_km]


def es_uuid(valor: str) -> bool:
    try:
        uuid.UUID(valor)
    except ValueError:
        return False
    return True


@router.get("/municipios")
def listar_municipios(db: Session = Depends(get_db)):
    return [municipio_a_dict(m) for m in db.scalars(select(Municipio).order_by(Municipio.nombre))]


@router.get("/choques")
def ver_choques(
    fecha_inicio: str,
    municipio: str,
    excluir: str | None = None,
    db: Session = Depends(get_db),
):
    """Choque de fechas (app/choques.py): planes publicados ese mismo día a 20 km o menos y hasta 3 días libres.
    Público: solo usa datos que ya salen en la agenda."""
    from datetime import datetime

    from app.choques import choques

    try:
        fecha = datetime.fromisoformat(fecha_inicio)
    except ValueError:
        raise ErrorApi(422, "validacion", "fecha_inicio no es una fecha ISO 8601", {"campo": "fecha_inicio"}) from None
    if fecha.tzinfo is None:
        raise ErrorApi(422, "validacion", "fecha_inicio tiene que llevar zona horaria", {"campo": "fecha_inicio"})
    if db.get(Municipio, municipio) is None:
        raise ErrorApi(422, "municipio_no_encontrado", "Ese municipio no está en la plataforma", {"campo": "municipio"})
    return choques(db, fecha, municipio, excluir if excluir and es_uuid(excluir) else None)


@router.get("/lugares")
def listar_lugares(
    municipio: str | None = None,
    tipo: Literal[TIPOS_LUGAR] | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radio_km: float | None = Query(None, ge=0),
    p: Pagina = Depends(pagina),
    db: Session = Depends(get_db),
):
    consulta = select(Lugar).order_by(Lugar.municipio, Lugar.nombre, Lugar.id)
    if municipio:
        consulta = consulta.where(Lugar.municipio == municipio)
    if tipo:
        consulta = consulta.where(Lugar.tipo == tipo)
    if not hay_radio(lat, lon, radio_km):
        return paginar(db, consulta, p, lugar_a_dict)
    filas = dentro_del_radio(db.scalars(en_caja(consulta, Lugar, lat, lon, radio_km)).all(), lat, lon, radio_km)
    return paginar_lista([lugar_a_dict(f) for f in filas], p)


@router.get("/lugares/{id}")
def ver_lugar(id: str, db: Session = Depends(get_db)):
    lugar = db.get(Lugar, id) if es_uuid(id) else None
    if lugar is None:
        raise ErrorApi(404, "lugar_no_encontrado", "No existe ese lugar")
    return lugar_a_dict(lugar)
