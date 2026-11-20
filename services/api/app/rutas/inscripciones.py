"""Inscripciones (H3.2): apuntarse, cancelar (con lista de espera), lista de inscritos y asistencia.

Quién puede: el vecino con su sesión (Bearer); el bot con X-Internal-Token en nombre de un vecino
(`usuario_id` en el cuerpo); el organizador (usuario del publicador del evento) y el moderador para ver la
lista, cancelar y marcar asistencia.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Body, Depends
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.errores import ErrorApi
from app.inscripciones import (
    devolver_plazas,
    inscripcion_a_dict,
    promocionar,
    renumerar_espera,
    siguiente_posicion,
    tomar_plazas,
)
from app.modelos import Evento, Inscripcion, Usuario, ahora
from app.notificaciones import enviar_en_segundo_plano
from app.rutas.eventos import VISIBLES_EN_FICHA
from app.rutas.publico import es_uuid
from app.seguridad import Quien, puede_gestionar, quien_llama

router = APIRouter(prefix="/api/v1", tags=["inscripciones"])


class InscripcionCrear(BaseModel):
    """components/schemas/InscripcionCrear de openapi.yaml."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: str | None = None
    plazas: Annotated[int, Field(ge=1)] = 1
    canal: Literal["whatsapp", "web", "telegram"] | None = None


class Asistencia(BaseModel):
    model_config = ConfigDict(extra="forbid")

    estado: Literal["asistio", "no_asistio"]


def _prohibido(mensaje: str) -> ErrorApi:
    return ErrorApi(403, "prohibido", mensaje)


def _evento(db: Session, id: str) -> Evento:
    evento = db.get(Evento, id, options=[selectinload(Evento.publicador)]) if es_uuid(id) else None
    if evento is None:
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return evento


def _inscripcion(db: Session, evento: Evento, insc_id: str) -> Inscripcion:
    inscripcion = db.get(Inscripcion, insc_id) if es_uuid(insc_id) else None
    if inscripcion is None or inscripcion.evento_id != evento.id:
        raise ErrorApi(404, "inscripcion_no_encontrada", "No existe esa inscripción en este evento")
    return inscripcion


def _respuesta(db: Session, inscripcion: Inscripcion) -> dict:
    return inscripcion_a_dict(inscripcion, db.get(Usuario, inscripcion.usuario_id))


@router.get("/eventos/{id}/inscripciones")
def listar_inscripciones(id: str, quien: Quien = Depends(quien_llama), db: Session = Depends(get_db)):
    evento = _evento(db, id)
    if not puede_gestionar(quien, evento):
        raise _prohibido("Solo el organizador del evento o un moderador ven la lista de inscritos")
    filas = db.execute(
        select(Inscripcion, Usuario)
        .join(Usuario, Usuario.id == Inscripcion.usuario_id)
        .where(Inscripcion.evento_id == evento.id)
        .order_by(Inscripcion.estado == "cancelada", Inscripcion.creado_en)
    ).all()
    return [inscripcion_a_dict(i, u) for i, u in filas]


@router.post("/eventos/{id}/inscripciones", status_code=201)
def inscribirse(
    id: str,
    datos: InscripcionCrear | None = Body(None),
    quien: Quien = Depends(quien_llama),
    db: Session = Depends(get_db),
):
    datos = datos or InscripcionCrear()
    if quien.usuario is not None and not quien.interno:
        usuario = quien.usuario
        if datos.usuario_id is not None and datos.usuario_id != usuario.id:
            raise _prohibido("Solo puedes inscribirte a ti mismo")
        canal = datos.canal or "web"
    else:
        if datos.usuario_id is None:
            raise ErrorApi(422, "falta_usuario_id", "Con X-Internal-Token hay que indicar usuario_id", {"campo": "usuario_id"})
        usuario = db.get(Usuario, datos.usuario_id) if es_uuid(datos.usuario_id) else None
        if usuario is None:
            raise ErrorApi(404, "usuario_no_encontrado", "No existe ese usuario")
        canal = datos.canal or "whatsapp"

    evento = _evento(db, id)
    if evento.estado not in VISIBLES_EN_FICHA:
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    if evento.estado != "publicado":
        raise ErrorApi(409, "evento_no_inscribible", f"El evento está {evento.estado}: ya no admite inscripciones",
                       {"estado": evento.estado})
    final = evento.fecha_fin or evento.fecha_inicio
    if final <= ahora():
        raise ErrorApi(409, "evento_terminado", "El evento ya ha terminado: no admite inscripciones")

    inscripcion = db.scalar(
        select(Inscripcion).where(Inscripcion.evento_id == evento.id, Inscripcion.usuario_id == usuario.id)
    )
    if inscripcion is not None and inscripcion.estado != "cancelada":
        raise ErrorApi(409, "ya_inscrito", "Ya estás apuntado a este evento",
                       {"inscripcion_id": inscripcion.id, "estado": inscripcion.estado})
    if tomar_plazas(db, evento, datos.plazas):
        estado, posicion = "confirmada", None
    else:
        estado, posicion = "lista_espera", siguiente_posicion(db, evento.id)
    if inscripcion is None:
        inscripcion = Inscripcion(evento_id=evento.id, usuario_id=usuario.id)
        db.add(inscripcion)
    inscripcion.estado, inscripcion.posicion_espera = estado, posicion
    inscripcion.plazas, inscripcion.canal = datos.plazas, canal
    try:
        db.commit()
    except IntegrityError:
        # Dos peticiones a la vez del mismo vecino: la segunda se deshace entera (también su plaza).
        db.rollback()
        raise ErrorApi(409, "ya_inscrito", "Ya estás apuntado a este evento") from None
    return _respuesta(db, inscripcion)


@router.delete("/eventos/{id}/inscripciones/{insc_id}")
def cancelar_inscripcion(
    id: str,
    insc_id: str,
    background_tasks: BackgroundTasks,
    quien: Quien = Depends(quien_llama),
    db: Session = Depends(get_db),
):
    evento = _evento(db, id)
    inscripcion = _inscripcion(db, evento, insc_id)
    propia = quien.usuario is not None and quien.usuario.id == inscripcion.usuario_id
    if not propia and not puede_gestionar(quien, evento):
        raise _prohibido("Solo puede cancelarla quien se apuntó, el organizador o un moderador")
    if inscripcion.estado == "cancelada":
        return _respuesta(db, inscripcion)
    if inscripcion.estado not in ("confirmada", "lista_espera"):
        raise ErrorApi(409, "inscripcion_cerrada", "Ya se ha marcado la asistencia: no se puede cancelar",
                       {"estado": inscripcion.estado})

    tenia_plaza = inscripcion.estado == "confirmada"
    inscripcion.estado, inscripcion.posicion_espera = "cancelada", None
    db.flush()
    avisos = []
    if tenia_plaza:
        devolver_plazas(db, evento, inscripcion.plazas)
        avisos = promocionar(db, evento)
    else:
        renumerar_espera(db, evento.id)
    db.commit()
    enviar_en_segundo_plano(background_tasks, db, avisos)
    return _respuesta(db, inscripcion)


@router.patch("/eventos/{id}/inscripciones/{insc_id}")
def marcar_asistencia(
    id: str, insc_id: str, datos: Asistencia, quien: Quien = Depends(quien_llama), db: Session = Depends(get_db)
):
    evento = _evento(db, id)
    if not puede_gestionar(quien, evento):
        raise _prohibido("Solo el organizador del evento o un moderador marcan la asistencia")
    inscripcion = _inscripcion(db, evento, insc_id)
    if inscripcion.estado not in ("confirmada", "asistio", "no_asistio"):
        raise ErrorApi(409, "inscripcion_sin_plaza", "Solo se marca la asistencia de quien tenía plaza",
                       {"estado": inscripcion.estado})
    inscripcion.estado = datos.estado
    db.commit()
    return _respuesta(db, inscripcion)
