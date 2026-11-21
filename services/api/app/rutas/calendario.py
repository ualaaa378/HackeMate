"""Exportación a calendario (.ics): un evento (público) y los eventos del usuario (con sesión)."""

from fastapi import APIRouter, Depends, Header
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.errores import ErrorApi
from app.ics import calendario, nombre_fichero
from app.modelos import Evento, Inscripcion, Usuario
from app.rutas.eventos import VISIBLES_EN_FICHA
from app.rutas.publico import es_uuid
from app.seguridad import es_servicio_interno, exigir_usuario

router = APIRouter(prefix="/api/v1", tags=["calendario"])

TIPO_ICS = "text/calendar; charset=utf-8"


def _respuesta_ics(contenido: str, fichero: str) -> Response:
    return Response(
        content=contenido.encode("utf-8"),
        media_type=TIPO_ICS,
        headers={"Content-Disposition": f'attachment; filename="{fichero}"'},
    )


@router.get("/eventos/{id}/ics", response_class=Response)
def ics_evento(id: str, x_internal_token: str | None = Header(None), db: Session = Depends(get_db)):
    evento = db.get(Evento, id, options=[selectinload(Evento.publicador)]) if es_uuid(id) else None
    # Igual que la ficha: lo que no está publicado (o cancelado/finalizado) no existe para el público.
    if evento is None or (evento.estado not in VISIBLES_EN_FICHA and not es_servicio_interno(x_internal_token)):
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return _respuesta_ics(calendario([evento]), nombre_fichero(evento.titulo))


@router.get("/usuarios/me/ics", response_class=Response)
def ics_mis_eventos(usuario: Usuario = Depends(exigir_usuario), db: Session = Depends(get_db)):
    """Eventos con inscripción `confirmada` (openapi: «todos los eventos en los que el usuario está confirmado»)."""
    eventos = db.scalars(
        select(Evento)
        .join(Inscripcion, Inscripcion.evento_id == Evento.id)
        .options(selectinload(Evento.publicador))
        .where(
            Inscripcion.usuario_id == usuario.id,
            Inscripcion.estado == "confirmada",
            Evento.estado.in_(VISIBLES_EN_FICHA),
        )
        .order_by(Evento.fecha_inicio, Evento.id)
    ).all()
    return _respuesta_ics(calendario(list(eventos), nombre="Mis planes en HackeMate"), "mis-eventos.ics")
