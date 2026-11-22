"""«Me gusta» en los planes: cualquiera ve cuántos hay; solo quien tiene cuenta puede darlo o quitarlo."""

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import Evento, MeGusta, Usuario
from app.rutas.eventos import VISIBLES_EN_FICHA
from app.rutas.publico import es_uuid
from app.seguridad import exigir_usuario, usuario_actual

router = APIRouter(prefix="/api/v1", tags=["eventos"])


def _evento_visible(db: Session, id: str) -> Evento:
    evento = db.get(Evento, id) if es_uuid(id) else None
    if evento is None or evento.estado not in VISIBLES_EN_FICHA:
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return evento


def _estado(db: Session, evento_id: str, usuario: Usuario | None) -> dict:
    total = db.scalar(select(func.count()).select_from(MeGusta).where(MeGusta.evento_id == evento_id)) or 0
    mio = usuario is not None and db.get(MeGusta, (evento_id, usuario.id)) is not None
    return {"total": total, "mio": mio}


@router.get("/eventos/{id}/me-gusta")
def ver_me_gusta(id: str, usuario: Usuario | None = Depends(usuario_actual), db: Session = Depends(get_db)):
    evento = _evento_visible(db, id)
    return _estado(db, evento.id, usuario)


@router.put("/eventos/{id}/me-gusta")
def dar_me_gusta(id: str, usuario: Usuario = Depends(exigir_usuario), db: Session = Depends(get_db)):
    evento = _evento_visible(db, id)
    if db.get(MeGusta, (evento.id, usuario.id)) is None:
        db.add(MeGusta(evento_id=evento.id, usuario_id=usuario.id))
        db.commit()
    return _estado(db, evento.id, usuario)


@router.delete("/eventos/{id}/me-gusta")
def quitar_me_gusta(id: str, usuario: Usuario = Depends(exigir_usuario), db: Session = Depends(get_db)):
    evento = _evento_visible(db, id)
    marca = db.get(MeGusta, (evento.id, usuario.id))
    if marca is not None:
        db.delete(marca)
        db.commit()
    return _estado(db, evento.id, usuario)
