"""Publicadores: lista, ficha y solicitud de alta. Aprobar, pausar y fuentes llegan en H2."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Header
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import ESTADOS_PUBLICADOR, TIPOS_PUBLICADOR, Municipio, Publicador, Usuario
from app.paginacion import Pagina, pagina, paginar
from app.rutas.publico import es_uuid
from app.seguridad import es_servicio_interno, exigir_token_interno
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
    db.commit()
    return publicador_a_dict(_buscar(db, publicador.id))
