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

from app import coche
from app.db import get_db
from app.errores import ErrorApi
from app.inscripciones import (
    ACTIVAS,
    cambiar_estado,
    cancelar,
    inscripcion_a_dict,
    plan_terminado,
    reactivar,
    siguiente_posicion,
    tomar_plazas,
)
from app.modelos import Evento, Inscripcion, Usuario
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
    if plan_terminado(evento):
        raise ErrorApi(409, "evento_finalizado", "Este plan ya ha terminado: no admite inscripciones",
                       {"estado": evento.estado})
    if evento.estado != "publicado":
        raise ErrorApi(409, "evento_no_inscribible", f"El evento está {evento.estado}: ya no admite inscripciones",
                       {"estado": evento.estado})

    inscripcion = db.scalar(
        select(Inscripcion).where(Inscripcion.evento_id == evento.id, Inscripcion.usuario_id == usuario.id)
    )
    if inscripcion is not None:
        # Vuelve a apuntarse tras cancelar: cambio condicional, así dos peticiones a la vez no toman dos plazas.
        if inscripcion.estado != "cancelada" or not reactivar(db, evento, inscripcion, datos.plazas, canal):
            raise ErrorApi(409, "ya_inscrito", "Ya estás apuntado a este evento",
                           {"inscripcion_id": inscripcion.id, "estado": inscripcion.estado})
    else:
        if tomar_plazas(db, evento, datos.plazas):
            estado, posicion = "confirmada", None
        else:
            estado, posicion = "lista_espera", siguiente_posicion(db, evento.id)
        inscripcion = Inscripcion(evento_id=evento.id, usuario_id=usuario.id, estado=estado,
                                  posicion_espera=posicion, plazas=datos.plazas, canal=canal)
        db.add(inscripcion)
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
    # Si otra petición se adelanta y la cancela, `cancelar` no toca plazas y se responde con el estado actual.
    _, avisos = cancelar(db, evento, inscripcion)
    if inscripcion.estado not in ("cancelada", *ACTIVAS):
        db.rollback()
        raise ErrorApi(409, "inscripcion_cerrada", "Ya se ha marcado la asistencia: no se puede cancelar",
                       {"estado": inscripcion.estado})
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
    for _ in range(3):  # condicional: si a la vez la cancelan, no se marca la asistencia de una plaza devuelta
        leido = inscripcion.estado
        if leido not in ("confirmada", "asistio", "no_asistio"):
            raise ErrorApi(409, "inscripcion_sin_plaza", "Solo se marca la asistencia de quien tenía plaza",
                           {"estado": leido})
        if cambiar_estado(db, inscripcion, leido, estado=datos.estado):
            break
    else:
        raise ErrorApi(409, "inscripcion_sin_plaza", "La inscripción ha cambiado a la vez: vuelve a intentarlo")
    db.commit()
    return _respuesta(db, inscripcion)


class CocheRespuesta(BaseModel):
    """components/schemas/CocheRespuesta de openapi.yaml."""

    model_config = ConfigDict(extra="forbid")

    usuario_id: str | None = None
    acepta: bool


@router.post("/eventos/{id}/coche")
def responder_coche(
    id: str,
    datos: CocheRespuesta,
    background_tasks: BackgroundTasks,
    quien: Quien = Depends(quien_llama),
    db: Session = Depends(get_db),
):
    """Compartir coche (app/coche.py): el vecino dice si quiere ir juntos con los de su pueblo."""
    if quien.usuario is not None and not quien.interno:
        usuario = quien.usuario
        if datos.usuario_id is not None and datos.usuario_id != usuario.id:
            raise _prohibido("Solo puedes responder por ti")
    else:
        if datos.usuario_id is None:
            raise ErrorApi(422, "falta_usuario_id", "Con X-Internal-Token hay que indicar usuario_id", {"campo": "usuario_id"})
        usuario = db.get(Usuario, datos.usuario_id) if es_uuid(datos.usuario_id) else None
        if usuario is None:
            raise ErrorApi(404, "usuario_no_encontrado", "No existe ese usuario")
    evento = _evento(db, id)
    if evento.estado != "publicado" or plan_terminado(evento):
        raise ErrorApi(409, "coche_no_disponible", "Este plan ya no admite compartir coche")
    try:
        cuerpo, avisos = coche.responder(db, evento, usuario, datos.acepta)
    except coche.CocheNoDisponible:
        raise ErrorApi(409, "coche_no_disponible",
                       "Solo para quien está apuntado con plaza y vive en otro pueblo distinto al del plan") from None
    db.commit()
    enviar_en_segundo_plano(background_tasks, db, avisos)
    return cuerpo
