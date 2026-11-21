"""Bandeja y decisiones del moderador (H2.5).

La IA propone y la moderación automática (app/moderacion.py) decide lo fácil; lo que queda `en_revision`
lo decide aquí una persona. El `{id}` de la decisión es siempre un evento (así lo define el contrato);
los publicadores se aprueban en `POST /publicadores/{id}/aprobar`.
"""

from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, ConfigDict, StringConstraints
from sqlalchemy import select, update
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import Evento, Publicador, Usuario, ahora
from app.moderacion import registrar_aprobacion_en_bd
from app.avisos_planes import avisar_interesados
from app.notificaciones import enviar_en_segundo_plano, notificar, notificar_moderadores, notificar_publicador
from app.paginacion import Pagina, pagina, paginar_lista
from app.rutas.eventos import Quien, _buscar, _ficha, quien_llama
from app.seguridad import REVISOR_INTERNO, es_organizador, exigir_moderador
from app.serializar import eventos_a_dict, publicadores_a_dict

router = APIRouter(prefix="/api/v1", tags=["moderacion"])

PUBLICADORES_POR_APROBAR = ("solicitado", "whatsapp_verificado")
MOTIVO_PUBLICADOR = {
    "solicitado": "Solicitud de alta (WhatsApp sin verificar)",
    "whatsapp_verificado": "Solicitud de alta con WhatsApp verificado",
}

# decision -> (estados desde los que procede, estado final)
TRANSICIONES = {
    "aprobar": (("en_revision",), "publicado"),
    "rechazar": (("en_revision",), "rechazado"),
    # Retirar un evento ya publicado: deja de verse, pero no es una cancelación (no se avisa a los inscritos
    # como si el evento no se celebrara) ni un rechazo de algo que nunca salió.
    "retirar": (("publicado",), "archivado"),
    # Deshacer un rechazo (p. ej. por error o tras corregir el plan): vuelve a la bandeja y se decide de nuevo.
    "restaurar": (("rechazado",), "en_revision"),
}


class Decision(BaseModel):
    """components/schemas/Decision."""

    model_config = ConfigDict(extra="ignore")

    decision: Literal["aprobar", "rechazar", "retirar", "restaurar"]
    motivo: str | None = None


@router.get("/moderacion/pendientes")
def pendientes(p: Pagina = Depends(pagina), revisor: str = Depends(exigir_moderador), db: Session = Depends(get_db)):
    """Eventos en revisión y publicadores por aprobar, mezclados y del más antiguo al más reciente.
    La bandeja es pequeña (unas decenas como mucho): se junta y pagina en memoria.
    `datos_ayuntamiento` solo va con sesión de moderador, no al bot (X-Internal-Token)."""
    eventos = db.scalars(
        select(Evento)
        .options(selectinload(Evento.publicador))
        .where(Evento.estado == "en_revision")
        .order_by(Evento.creado_en, Evento.id)
    ).all()
    publicadores = db.scalars(
        select(Publicador)
        .options(selectinload(Publicador.fuentes))
        .where(Publicador.estado.in_(PUBLICADORES_POR_APROBAR))
        .order_by(Publicador.creado_en, Publicador.id)
    ).all()

    items = [
        (e.creado_en, {"tipo": "evento", "motivo": e.motivo_moderacion or "Pendiente de revisión",
                       "score_spam": e.score_spam, "evento": datos})
        for e, datos in zip(eventos, eventos_a_dict(db, list(eventos), privados=revisor != REVISOR_INTERNO))
    ]
    # `responsable` y `actividad` del publicador, igual: solo con sesión de moderador.
    items += [
        (pub.creado_en, {"tipo": "publicador", "motivo": MOTIVO_PUBLICADOR[pub.estado], "score_spam": None,
                         "publicador": datos})
        for pub, datos in zip(
            publicadores, publicadores_a_dict(db, list(publicadores), privados=revisor != REVISOR_INTERNO)
        )
    ]
    items.sort(key=lambda par: par[0])
    return paginar_lista([item for _, item in items], p)


def _texto_aviso(evento: Evento, decision: str, motivo: str | None) -> str:
    if decision == "aprobar":
        return f"Tu evento «{evento.titulo}» ya está publicado en la agenda."
    accion = "no se ha publicado" if decision == "rechazar" else "se ha retirado de la agenda"
    return f"Tu evento «{evento.titulo}» {accion}." + (f" Motivo: {motivo}" if motivo else "")


MOTIVO_POR_DEFECTO = {
    "aprobar": "Aprobado por el moderador",
    "rechazar": "Rechazado por el moderador",
    "retirar": "Retirado por moderación",
    "restaurar": "Restaurado por moderación: pendiente de revisar de nuevo",
}


@router.post("/moderacion/{id}/decision")
def decidir(
    id: str,
    datos: Decision,
    background_tasks: BackgroundTasks,
    revisor: str = Depends(exigir_moderador),
    db: Session = Depends(get_db),
):
    evento = _buscar(db, id)
    origenes, destino = TRANSICIONES[datos.decision]
    motivo = (datos.motivo or "").strip() or None

    # Transición atómica: si otro moderador ha decidido a la vez, solo una de las dos peticiones cambia la
    # fila; la otra recibe 409 y no suma otra aprobación ni manda otro aviso.
    cambiadas = db.execute(
        update(Evento)
        .where(Evento.id == evento.id, Evento.estado.in_(origenes))
        .values(estado=destino, revisado_por=revisor, motivo_moderacion=motivo or MOTIVO_POR_DEFECTO[datos.decision])
        .execution_options(synchronize_session=False)
    ).rowcount
    if cambiadas == 0:
        db.rollback()
        db.refresh(evento)
        raise ErrorApi(
            409,
            "estado_invalido",
            f"No se puede {datos.decision} un evento en estado {evento.estado}",
            {"estado": evento.estado, "decision": datos.decision},
        )
    db.refresh(evento)

    publicador = evento.publicador
    if datos.decision == "aprobar" and publicador is not None:
        registrar_aprobacion_en_bd(db, publicador.id)
    aviso = None
    # Restaurar no es una decisión final: el publicador recibe el aviso cuando se apruebe o rechace otra vez.
    if publicador is not None and datos.decision != "restaurar":
        aviso = notificar_publicador(
            db, publicador, "moderacion", _texto_aviso(evento, datos.decision, motivo),
            evento_id=evento.id, enviar=False,
        )
    elif evento.propuesto_por_id and datos.decision != "restaurar":
        # Vecino sin asociación (P5a): también se entera, con el evento_id para que el bot ponga [Apelar] (P3a).
        quien_propuso = db.get(Usuario, evento.propuesto_por_id)
        if quien_propuso is not None:
            aviso = notificar(db, tipo="moderacion", texto=_texto_aviso(evento, datos.decision, motivo),
                              usuario=quien_propuso, evento_id=evento.id, enviar=False)
    interesados = avisar_interesados(db, evento) if destino == "publicado" else []  # A10
    db.commit()
    enviar_en_segundo_plano(background_tasks, db, [aviso, *interesados])
    return _ficha(db, _buscar(db, evento.id), privados=revisor != REVISOR_INTERNO)


# --- P3a: apelaciones -------------------------------------------------------------------------------

MotivoApelacion = Annotated[str, StringConstraints(strip_whitespace=True, min_length=10, max_length=500)]


class Apelacion(BaseModel):
    """Cuerpo de POST /eventos/{id}/apelacion."""

    model_config = ConfigDict(extra="forbid")

    motivo: MotivoApelacion
    usuario_id: str | None = None  # obligatorio con X-Internal-Token (el bot apela en nombre de alguien)


@router.post("/eventos/{id}/apelacion")
def apelar(id: str, datos: Apelacion, background_tasks: BackgroundTasks, quien: Quien = Depends(quien_llama),
           db: Session = Depends(get_db)):
    """Quien propuso un plan rechazado pide que se revise otra vez, una sola vez: vuelve a la bandeja con el motivo
    «Apelación: …». El moderador decide con los botones de siempre; un segundo rechazo es definitivo."""
    evento = _buscar(db, id)
    usuario = quien.usuario
    if quien.interno and usuario is None:
        if not datos.usuario_id:
            raise ErrorApi(422, "validacion", "Falta usuario_id: quién apela", {"campos": ["usuario_id"]})
        usuario = db.get(Usuario, datos.usuario_id)
    if not es_organizador(usuario, evento):
        raise ErrorApi(403, "prohibido", "Solo quien propuso el plan puede apelar")
    if evento.apelacion_en is not None:
        raise ErrorApi(409, "apelacion_usada", "Este plan ya se apeló una vez: la segunda decisión es definitiva",
                       {"apelacion_en": evento.apelacion_en.isoformat()})
    if evento.estado != "rechazado":
        raise ErrorApi(409, "estado_invalido", "Solo se puede apelar un plan rechazado", {"estado": evento.estado})

    motivo = f"Apelación: {datos.motivo}"
    # Atómico: dos apelaciones a la vez no pasan las dos.
    cambiadas = db.execute(
        update(Evento)
        .where(Evento.id == evento.id, Evento.estado == "rechazado", Evento.apelacion_en.is_(None))
        .values(estado="en_revision", apelacion_motivo=datos.motivo, apelacion_en=ahora(),
                motivo_moderacion=motivo, revisado_por=None)
        .execution_options(synchronize_session=False)
    ).rowcount
    if cambiadas == 0:
        db.rollback()
        raise ErrorApi(409, "apelacion_usada", "Este plan ya se ha apelado")
    db.refresh(evento)
    avisos = notificar_moderadores(db, "moderacion", f"Apelación de «{evento.titulo}»: {datos.motivo}",
                                   evento_id=evento.id, enviar=False)
    db.commit()
    enviar_en_segundo_plano(background_tasks, db, avisos)
    return _ficha(db, _buscar(db, evento.id), privados=True)
