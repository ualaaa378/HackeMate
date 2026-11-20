"""Bandeja y decisiones del moderador (H2.5).

La IA propone y la moderación automática (app/moderacion.py) decide lo fácil; lo que queda `en_revision`
lo decide aquí una persona. El `{id}` de la decisión es siempre un evento (así lo define el contrato);
los publicadores se aprueban en `POST /publicadores/{id}/aprobar`.
"""

from typing import Literal

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import Evento, Publicador
from app.moderacion import registrar_aprobacion
from app.notificaciones import notificar_publicador
from app.paginacion import Pagina, pagina, paginar_lista
from app.rutas.eventos import _buscar, _ficha
from app.seguridad import exigir_moderador
from app.serializar import eventos_a_dict, publicador_a_dict

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
}


class Decision(BaseModel):
    """components/schemas/Decision."""

    model_config = ConfigDict(extra="ignore")

    decision: Literal["aprobar", "rechazar", "retirar"]
    motivo: str | None = None


@router.get("/moderacion/pendientes")
def pendientes(p: Pagina = Depends(pagina), _: str = Depends(exigir_moderador), db: Session = Depends(get_db)):
    """Eventos en revisión y publicadores por aprobar, mezclados y del más antiguo al más reciente.
    La bandeja es pequeña (unas decenas como mucho): se junta y pagina en memoria."""
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
        for e, datos in zip(eventos, eventos_a_dict(db, list(eventos)))
    ]
    items += [
        (pub.creado_en, {"tipo": "publicador", "motivo": MOTIVO_PUBLICADOR[pub.estado], "score_spam": None,
                         "publicador": publicador_a_dict(pub)})
        for pub in publicadores
    ]
    items.sort(key=lambda par: par[0])
    return paginar_lista([item for _, item in items], p)


def _texto_aviso(evento: Evento, decision: str, motivo: str | None, subio_nivel: bool) -> str:
    if decision == "aprobar":
        texto = f"Tu evento «{evento.titulo}» ya está publicado en la agenda."
        if subio_nivel and evento.publicador is not None:
            texto += (
                f" Has subido a nivel de confianza {evento.publicador.nivel_confianza}:"
                " tus próximas publicaciones habituales saldrán sin esperar revisión."
            )
        return texto
    accion = "no se ha publicado" if decision == "rechazar" else "se ha retirado de la agenda"
    return f"Tu evento «{evento.titulo}» {accion}." + (f" Motivo: {motivo}" if motivo else "")


@router.post("/moderacion/{id}/decision")
def decidir(id: str, datos: Decision, revisor: str = Depends(exigir_moderador), db: Session = Depends(get_db)):
    evento = _buscar(db, id)
    origenes, destino = TRANSICIONES[datos.decision]
    if evento.estado not in origenes:
        raise ErrorApi(
            409,
            "estado_invalido",
            f"No se puede {datos.decision} un evento en estado {evento.estado}",
            {"estado": evento.estado, "decision": datos.decision},
        )
    motivo = (datos.motivo or "").strip() or None
    if datos.decision == "retirar" and motivo is None:
        raise ErrorApi(422, "validacion", "Para retirar un evento hace falta el motivo", {"campo": "motivo"})

    evento.estado = destino
    evento.revisado_por = revisor
    evento.motivo_moderacion = motivo or ("Aprobado por el moderador" if datos.decision == "aprobar" else
                                          "Rechazado por el moderador")
    subio_nivel = False
    publicador = evento.publicador
    if datos.decision == "aprobar" and publicador is not None:
        # Al quedar publicado, su categoría cuenta ya como «lo habitual» para el nivel 1 (decidir_estado).
        subio_nivel = registrar_aprobacion(publicador)
    if publicador is not None:
        notificar_publicador(
            db, publicador, "moderacion", _texto_aviso(evento, datos.decision, motivo, subio_nivel), evento_id=evento.id
        )
    db.commit()
    return _ficha(db, _buscar(db, evento.id))
