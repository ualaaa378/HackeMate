"""Usuarios: alta y búsqueda por teléfono, para el bot. `/usuarios/me` llega en H3 con el login."""

from typing import Annotated

from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import Municipio, Usuario
from app.seguridad import exigir_token_interno
from app.serializar import usuario_a_dict
from app.telefonos import normalizar_telefono, validar_telefono

# Las dos rutas son solo para servicios internos (openapi: security interno).
router = APIRouter(prefix="/api/v1", tags=["usuarios"], dependencies=[Depends(exigir_token_interno)])

# El contrato no exige nombre en el alta, pero el usuario siempre tiene uno (minLength 1).
NOMBRE_POR_DEFECTO = "Vecino"


class UsuarioCrear(BaseModel):
    """components/schemas/UsuarioCrear de openapi.yaml."""

    model_config = ConfigDict(extra="forbid")

    telefono: str
    nombre: Annotated[str, Field(max_length=120)] | None = None
    municipio: str | None = None

    _telefono = field_validator("telefono")(validar_telefono)


def _ya_existe(usuario_id: str) -> ErrorApi:
    return ErrorApi(409, "usuario_ya_existe", "Ya hay un usuario con ese teléfono", {"usuario_id": usuario_id})


def _por_telefono(db: Session, telefono: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.telefono == telefono))


@router.post("/usuarios", status_code=201)
def crear_usuario(datos: UsuarioCrear, db: Session = Depends(get_db)):
    municipio = None
    if datos.municipio is not None:
        municipio = db.get(Municipio, datos.municipio)
        if municipio is None:
            raise ErrorApi(
                422, "municipio_no_encontrado", "Ese municipio no está en la plataforma", {"campo": "municipio"}
            )
    existente = _por_telefono(db, datos.telefono)
    if existente is not None:
        raise _ya_existe(existente.id)

    usuario = Usuario(
        nombre=(datos.nombre or "").strip() or NOMBRE_POR_DEFECTO,
        rol="vecino",
        telefono=datos.telefono,
        municipio=datos.municipio,
        # Sin más datos, su ubicación es la de su pueblo (la usa el recomendador).
        lat=municipio.lat if municipio else None,
        lon=municipio.lon if municipio else None,
    )
    db.add(usuario)
    try:
        db.commit()
    except IntegrityError:
        # Dos altas a la vez con el mismo teléfono: la segunda choca con el UNIQUE.
        db.rollback()
        raise _ya_existe(_por_telefono(db, datos.telefono).id)
    return usuario_a_dict(usuario)


@router.get("/usuarios/by-phone/{e164}")
def usuario_por_telefono(e164: str, db: Session = Depends(get_db)):
    # La ruta llega ya decodificada: +34600000201 y %2B34600000201 son lo mismo.
    telefono = normalizar_telefono(e164)
    if telefono is None:
        raise ErrorApi(
            422, "telefono_invalido", "El teléfono debe ir en formato E.164, p. ej. +34600000000", {"campo": "e164"}
        )
    usuario = _por_telefono(db, telefono)
    if usuario is None:
        raise ErrorApi(404, "usuario_no_encontrado", "No hay ningún usuario con ese teléfono")
    return usuario_a_dict(usuario)
