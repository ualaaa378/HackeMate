"""Lectura pública: municipios, lugares y eventos (agenda, mapa y ficha)."""

import math
from datetime import datetime

from fastapi import APIRouter, Query

from app import fixtures
from app.errores import ErrorApi

router = APIRouter(prefix="/api/v1", tags=["eventos"])


def distancia_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    rad = math.radians
    a = math.sin(rad(lat2 - lat1) / 2) ** 2 + math.cos(rad(lat1)) * math.cos(rad(lat2)) * math.sin(
        rad(lon2 - lon1) / 2
    ) ** 2
    return 6371 * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _cerca(items: list[dict], lat: float | None, lon: float | None, radio_km: float | None) -> list[dict]:
    if lat is None or lon is None or not radio_km:
        return items
    return [i for i in items if distancia_km(lat, lon, i["lat"], i["lon"]) <= radio_km]


def _pagina(items: list[dict], page: int, size: int) -> dict:
    return {"items": items[(page - 1) * size : page * size], "total": len(items), "page": page, "size": size}


def _fecha(valor: str) -> datetime:
    return datetime.fromisoformat(valor.replace("Z", "+00:00"))


@router.get("/municipios")
def listar_municipios():
    return fixtures.municipios()


@router.get("/lugares")
def listar_lugares(
    municipio: str | None = None,
    tipo: str | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radio_km: float | None = Query(None, ge=0),
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    items = fixtures.lugares()
    if municipio:
        items = [i for i in items if i["municipio"] == municipio]
    if tipo:
        items = [i for i in items if i["tipo"] == tipo]
    return _pagina(_cerca(items, lat, lon, radio_km), page, size)


@router.get("/lugares/{id}")
def ver_lugar(id: str):
    for i in fixtures.lugares():
        if i["id"] == id:
            return i
    raise ErrorApi(404, "lugar_no_encontrado", "No existe ese lugar")


@router.get("/eventos")
def listar_eventos(
    municipio: str | None = None,
    categoria: str | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radio_km: float | None = Query(None, ge=0),
    q: str | None = None,
    estado: str = "publicado",
    publicador_id: str | None = None,
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
):
    # Sin login todavía: el público solo ve publicados, se ignora otro estado.
    items = [e for e in fixtures.eventos() if e["estado"] == "publicado"]
    if municipio:
        items = [e for e in items if e["municipio"] == municipio]
    if categoria:
        items = [e for e in items if e["categoria"] == categoria]
    if desde:
        items = [e for e in items if _fecha(e["fecha_inicio"]) >= desde]
    if hasta:
        items = [e for e in items if _fecha(e["fecha_inicio"]) <= hasta]
    if q:
        t = q.lower()
        items = [e for e in items if t in e["titulo"].lower() or t in (e.get("descripcion") or "").lower()]
    if publicador_id:
        items = [e for e in items if e.get("publicador_id") == publicador_id]
    items = sorted(_cerca(items, lat, lon, radio_km), key=lambda e: _fecha(e["fecha_inicio"]))
    return _pagina(items, page, size)


@router.get("/eventos/{id}")
def ver_evento(id: str):
    for e in fixtures.eventos():
        if e["id"] == id:
            return e
    raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
