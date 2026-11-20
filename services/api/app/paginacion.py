"""Paginación común: ?page=1&size=20 → {"items": [...], "total": 123, "page": 1, "size": 20}."""

from collections.abc import Callable
from dataclasses import dataclass
from typing import Any

from fastapi import Query
from sqlalchemy import Select, func, select
from sqlalchemy.orm import Session


@dataclass
class Pagina:
    page: int
    size: int

    @property
    def desde(self) -> int:
        return (self.page - 1) * self.size


def pagina(page: int = Query(1, ge=1), size: int = Query(20, ge=1, le=100)) -> Pagina:
    """Dependencia: `p: Pagina = Depends(pagina)`."""
    return Pagina(page, size)


def respuesta(items: list, total: int, p: Pagina) -> dict:
    return {"items": items, "total": total, "page": p.page, "size": p.size}


def paginar(db: Session, consulta: Select, p: Pagina, a_json: Callable[[Any], dict]) -> dict:
    """Ejecuta la consulta con LIMIT/OFFSET y cuenta el total sin traer todas las filas."""
    total = db.scalar(select(func.count()).select_from(consulta.order_by(None).subquery())) or 0
    filas = db.scalars(consulta.limit(p.size).offset(p.desde)).all()
    return respuesta([a_json(f) for f in filas], total, p)


def paginar_lista(items: list, p: Pagina) -> dict:
    """Para listas ya filtradas en memoria (p. ej. filtro por radio, que se calcula en Python)."""
    return respuesta(items[p.desde : p.desde + p.size], len(items), p)
