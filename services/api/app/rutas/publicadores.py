"""Publicadores: lista, ficha, solicitud de alta (E1.5) y, del moderador, aprobar, pausar y fuentes (H2.5-H2.6)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import ESTADOS_PUBLICADOR, TIPOS_PUBLICADOR, Fuente, Municipio, Publicador, Usuario
from app.notificaciones import notificar_moderadores, notificar_publicador
from app.paginacion import Pagina, pagina, paginar
from app.rutas.publico import es_uuid
from app.seguridad import es_servicio_interno, exigir_moderador, exigir_token_interno
from app.serializar import publicador_a_dict
from app.telefonos import validar_telefono

router = APIRouter(prefix="/api/v1", tags=["publicadores"])

# Lo que ve el público: en la lista, solo los aprobados; la ficha, también si está pausado
# (sus eventos ya publicados siguen apuntando a él).
VISIBLES_EN_LISTA = ("aprobado",)
VISIBLES_EN_FICHA = ("aprobado", "pausado")
PATRON_EMAIL = r"^[^@\s]+@[^@\s]+\.[^@\s]+$"


class PublicadorCrear(BaseModel):
    """components/schemas/PublicadorCrear de openapi.yaml."""

    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(min_length=2, max_length=160)]
    tipo: Literal[TIPOS_PUBLICADOR]
    municipio: str
    descripcion: str | None = None
    telefono: str
    email: Annotated[str, Field(pattern=PATRON_EMAIL, max_length=254)] | None = None

    _telefono = field_validator("telefono")(validar_telefono)


def _buscar(db: Session, id: str) -> Publicador:
    publicador = db.get(Publicador, id, options=[selectinload(Publicador.fuentes)]) if es_uuid(id) else None
    if publicador is None:
        raise ErrorApi(404, "publicador_no_encontrado", "No existe ese publicador")
    return publicador


@router.get("/publicadores")
def listar_publicadores(
    estado: Literal[ESTADOS_PUBLICADOR] | None = None,
    municipio: str | None = None,
    p: Pagina = Depends(pagina),
    x_internal_token: str | None = Header(None),
    db: Session = Depends(get_db),
):
    interno = es_servicio_interno(x_internal_token)
    consulta = (
        select(Publicador).options(selectinload(Publicador.fuentes)).order_by(Publicador.nombre, Publicador.id)
    )
    if estado:
        consulta = consulta.where(Publicador.estado == estado)
    if not interno:
        # H3: el moderador (JWT) verá todos los estados. El público, solo los aprobados.
        consulta = consulta.where(Publicador.estado.in_(VISIBLES_EN_LISTA))
    if municipio:
        consulta = consulta.where(Publicador.municipio == municipio)
    return paginar(db, consulta, p, lambda pub: publicador_a_dict(pub, con_contacto=interno))


@router.get("/publicadores/{id}")
def ver_publicador(id: str, x_internal_token: str | None = Header(None), db: Session = Depends(get_db)):
    publicador = _buscar(db, id)
    interno = es_servicio_interno(x_internal_token)
    if not interno and publicador.estado not in VISIBLES_EN_FICHA:
        raise ErrorApi(404, "publicador_no_encontrado", "No existe ese publicador")
    return publicador_a_dict(publicador, con_contacto=interno)


@router.post("/publicadores", status_code=201, dependencies=[Depends(exigir_token_interno)])
def crear_publicador(datos: PublicadorCrear, db: Session = Depends(get_db)):
    # H3: con el JWT también podrá solicitarlo el propio usuario desde la app.
    if db.get(Municipio, datos.municipio) is None:
        raise ErrorApi(
            422, "municipio_no_encontrado", "Ese municipio no está en la plataforma", {"campo": "municipio"}
        )
    existente = db.scalar(select(Publicador).where(Publicador.telefono == datos.telefono))
    if existente is not None:
        raise ErrorApi(
            409, "publicador_ya_existe", "Ya hay un publicador con ese teléfono", {"publicador_id": existente.id}
        )
    # Si quien lo pide ya es usuario (el bot lo da de alta al primer mensaje), queda como responsable.
    usuario = db.scalar(select(Usuario).where(Usuario.telefono == datos.telefono))
    publicador = Publicador(
        **datos.model_dump(),
        estado="solicitado",  # hasta verificar el WhatsApp y que lo apruebe el moderador (H2)
        nivel_confianza=0,
        usuario_id=usuario.id if usuario else None,
    )
    db.add(publicador)
    db.flush()
    notificar_moderadores(
        db, "moderacion", f"Nueva solicitud de publicador: {publicador.nombre} ({publicador.municipio}). "
        "Revísala en la bandeja de moderación."
    )
    db.commit()
    return publicador_a_dict(_buscar(db, publicador.id))


# --- Moderador: aprobar y pausar (H2.5, H2.6) ---------------------------------------------------


class AprobarPublicador(BaseModel):
    model_config = ConfigDict(extra="ignore")

    aprobar: bool = True
    nivel_confianza: Literal[0, 1, 2] = 0
    motivo: str | None = None


class PausarPublicador(BaseModel):
    model_config = ConfigDict(extra="ignore")

    que: Literal["publicador", "automatizaciones"]
    pausado: bool


POR_APROBAR = ("solicitado", "whatsapp_verificado")


@router.post("/publicadores/{id}/aprobar")
def aprobar_publicador(
    id: str,
    datos: AprobarPublicador | None = None,
    _: str = Depends(exigir_moderador),
    db: Session = Depends(get_db),
):
    datos = datos or AprobarPublicador()
    publicador = _buscar(db, id)
    if publicador.estado not in POR_APROBAR:
        raise ErrorApi(
            409, "estado_invalido", "El publicador no está pendiente de aprobación", {"estado": publicador.estado}
        )
    # Se admite aprobar desde `solicitado` (sin verificar el WhatsApp): mientras no exista
    # /auth/whatsapp/verificar (H3) es la única forma de completar el alta; el moderador asume la verificación.
    motivo = (datos.motivo or "").strip() or None
    if datos.aprobar:
        publicador.estado = "aprobado"
        publicador.nivel_confianza = datos.nivel_confianza
        texto = (
            f"¡Bienvenido! {publicador.nombre} ya puede publicar en HackeMate (nivel de confianza "
            f"{datos.nivel_confianza}). Mándanos el cartel, el post o un audio y lo preparamos."
        )
    else:
        publicador.estado = "rechazado"
        texto = f"Tu solicitud para publicar como {publicador.nombre} no se ha aprobado." + (
            f" Motivo: {motivo}" if motivo else ""
        )
    notificar_publicador(db, publicador, "moderacion", texto)
    db.commit()
    return publicador_a_dict(_buscar(db, publicador.id))


@router.post("/publicadores/{id}/pausar")
def pausar_publicador(
    id: str, datos: PausarPublicador, _: str = Depends(exigir_moderador), db: Session = Depends(get_db)
):
    publicador = _buscar(db, id)
    if datos.que == "automatizaciones":
        # Lo que el bot importa solo (fuentes vigiladas) irá a revisión; lo que manda la persona, no.
        publicador.automatizaciones_pausadas = datos.pausado
        texto = (
            "Hemos pausado la importación automática de tus fuentes: lo que publiquemos pasará por revisión."
            if datos.pausado
            else "Hemos reactivado la importación automática de tus fuentes."
        )
    else:
        validos = ("aprobado", "pausado")
        if publicador.estado not in validos:
            raise ErrorApi(
                409, "estado_invalido", "Solo se pausa o reactiva un publicador aprobado", {"estado": publicador.estado}
            )
        nuevo = "pausado" if datos.pausado else "aprobado"
        if publicador.estado == nuevo:
            return publicador_a_dict(publicador)
        publicador.estado = nuevo
        texto = (
            f"{publicador.nombre} queda en pausa: de momento no puedes publicar eventos nuevos."
            if datos.pausado
            else f"{publicador.nombre} vuelve a estar activo: ya puedes publicar."
        )
    notificar_publicador(db, publicador, "moderacion", texto)
    db.commit()
    return publicador_a_dict(_buscar(db, publicador.id))


# --- Fuentes que vigila el bot (H2.6) -----------------------------------------------------------


class FuenteCrear(BaseModel):
    model_config = ConfigDict(extra="ignore")

    canal: Literal["facebook", "instagram", "web_externa"]
    url: Annotated[str, Field(min_length=4, max_length=500, pattern=r"^\s*\S+\s*$")]


@router.post("/publicadores/{id}/fuentes", status_code=201, dependencies=[Depends(exigir_token_interno)])
def anadir_fuente(id: str, datos: FuenteCrear, db: Session = Depends(get_db)):
    # Lo llama el bot cuando el publicador conecta su página. H3: también el moderador con su JWT.
    publicador = _buscar(db, id)
    if publicador.estado == "rechazado":
        raise ErrorApi(409, "estado_invalido", "El publicador está rechazado", {"estado": publicador.estado})
    url = datos.url.strip().rstrip("/")
    if "://" not in url:
        url = "https://" + url  # «facebook.com/pagina»: los posts importados llegan con la URL completa
    existentes = db.scalars(select(Fuente)).all()
    repetida = next((f for f in existentes if f.url.rstrip("/") == url), None)
    if repetida is not None:
        raise ErrorApi(
            409, "fuente_ya_existe", "Esa fuente ya está conectada", {"publicador_id": repetida.publicador_id}
        )
    publicador.fuentes.append(Fuente(canal=datos.canal, url=url, activa=True))
    db.commit()
    return publicador_a_dict(_buscar(db, publicador.id))
