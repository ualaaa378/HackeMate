"""Usuarios: alta, búsqueda por teléfono o por contacto de cualquier canal (WhatsApp, Telegram…) y
vinculación de un canal con el teléfono y edición de preferencias (PATCH /usuarios/{id}), para el bot (token
interno). Y `/usuarios/me` (sesión del usuario)."""

from typing import Annotated, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.canales import buscar_usuario_por_contacto, parsear_contacto
from app.db import get_db
from app.errores import ErrorApi
from app.modelos import CATEGORIAS, FORMATOS_AVISO, Municipio, Publicador, Usuario
from app.rutas.publico import es_uuid
from app.seguridad import exigir_token_interno, exigir_usuario
from app.serializar import usuario_a_dict
from app.telefonos import normalizar_telefono, validar_telefono

# Rutas solo para servicios internos (openapi: security interno).
router = APIRouter(prefix="/api/v1", tags=["usuarios"], dependencies=[Depends(exigir_token_interno)])
# Rutas del propio usuario (openapi: security bearer).
router_me = APIRouter(prefix="/api/v1", tags=["usuarios"])

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


def _municipio(db: Session, nombre: str | None) -> Municipio | None:
    if nombre is None:
        return None
    municipio = db.get(Municipio, nombre)
    if municipio is None:
        raise ErrorApi(422, "municipio_no_encontrado", "Ese municipio no está en la plataforma", {"campo": "municipio"})
    return municipio


def _nuevo_usuario(telefono: str, nombre: str | None, municipio: Municipio | None) -> Usuario:
    return Usuario(
        nombre=(nombre or "").strip() or NOMBRE_POR_DEFECTO,
        rol="vecino",
        telefono=telefono,
        municipio=municipio.nombre if municipio else None,
        # Sin más datos, su ubicación es la de su pueblo (la usa el recomendador).
        lat=municipio.lat if municipio else None,
        lon=municipio.lon if municipio else None,
    )


@router.post("/usuarios", status_code=201)
def crear_usuario(datos: UsuarioCrear, db: Session = Depends(get_db)):
    municipio = _municipio(db, datos.municipio)
    existente = _por_telefono(db, datos.telefono)
    if existente is not None:
        raise _ya_existe(existente.id)

    usuario = _nuevo_usuario(datos.telefono, datos.nombre, municipio)
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


@router.get("/usuarios/by-contacto/{contacto}")
def usuario_por_contacto(contacto: str, db: Session = Depends(get_db)):
    """Como by-phone, pero con la dirección de cualquier canal: `+34…` (WhatsApp) o `tg:<chat_id>` (Telegram)."""
    usuario = buscar_usuario_por_contacto(db, parsear_contacto(contacto))
    if usuario is None:
        raise ErrorApi(404, "usuario_no_encontrado", "No hay ningún usuario con ese contacto")
    return usuario_a_dict(usuario)


class UsuarioVincular(BaseModel):
    """components/schemas/UsuarioVincular de openapi.yaml."""

    model_config = ConfigDict(extra="forbid")

    telefono: str
    contacto: str  # se valida en la ruta para responder `contacto_invalido`
    nombre: Annotated[str, Field(max_length=120)] | None = None
    municipio: str | None = None

    _telefono = field_validator("telefono")(validar_telefono)


def _contacto_en_uso(dueno: str, id_: str) -> ErrorApi:
    return ErrorApi(409, "contacto_en_uso", "Ese contacto ya está vinculado a otra persona", {dueno: id_})


@router.post("/usuarios/vincular", responses={200: {"description": "Usuario existente vinculado"}})
def vincular_usuario(datos: UsuarioVincular, db: Session = Depends(get_db)):
    """Asocia el contacto de un canal (p. ej. tg:<chat_id>, tras «Compartir mi número») al teléfono.
    Crea el usuario si no existe (201) y vincula también al publicador con ese teléfono."""
    canal, valor = parsear_contacto(datos.contacto)
    if canal.campo == "telefono" and valor != datos.telefono:
        raise ErrorApi(
            422, "contacto_invalido", "Un contacto de WhatsApp es el propio teléfono", {"campo": "contacto"}
        )
    municipio = _municipio(db, datos.municipio)

    usuario = _por_telefono(db, datos.telefono)
    otro = buscar_usuario_por_contacto(db, (canal, valor))
    if otro is not None and (usuario is None or otro.id != usuario.id):
        raise _contacto_en_uso("usuario_id", otro.id)

    publicador = db.scalar(
        select(Publicador).where(Publicador.telefono == datos.telefono).order_by(Publicador.creado_en)
    )
    if publicador is not None:
        otro_pub = db.scalar(select(Publicador).where(getattr(Publicador, canal.campo) == valor))
        if otro_pub is not None and otro_pub.id != publicador.id:
            raise _contacto_en_uso("publicador_id", otro_pub.id)
        setattr(publicador, canal.campo, valor)

    creado = usuario is None
    if creado:
        usuario = _nuevo_usuario(datos.telefono, datos.nombre, municipio)
        db.add(usuario)
    setattr(usuario, canal.campo, valor)
    try:
        db.commit()
    except IntegrityError:
        # Dos vinculaciones a la vez con el mismo contacto o teléfono: la segunda choca con el UNIQUE.
        db.rollback()
        raise ErrorApi(409, "contacto_en_uso", "Ese contacto ya está vinculado a otra persona")
    return JSONResponse(usuario_a_dict(usuario), status_code=201 if creado else 200)


# --- /usuarios/me (sesión del usuario) -----------------------------------------------------------


class UsuarioEditar(BaseModel):
    """components/schemas/UsuarioEditar de openapi.yaml. Solo se cambia lo que viene en el cuerpo.

    Los campos que no admiten null en el schema (nombre, gustos…) tienen None solo como «no enviado»:
    pydantic no valida el valor por defecto, pero un null explícito sí da 422.
    """

    model_config = ConfigDict(extra="forbid")

    nombre: Annotated[str, Field(min_length=1, max_length=120)] = None
    municipio: str | None = None
    lat: Annotated[float, Field(ge=-90, le=90)] | None = None
    lon: Annotated[float, Field(ge=-180, le=180)] | None = None
    gustos: Annotated[list[Literal[CATEGORIAS]], Field(max_length=len(CATEGORIAS))] = None
    etiquetas_interes: Annotated[list[Annotated[str, Field(min_length=1, max_length=60)]], Field(max_length=30)] = None
    formato_aviso: Literal[FORMATOS_AVISO] = None
    acepta_avisos: bool = None
    radio_km: Annotated[float, Field(ge=0, le=500)] | None = None
    telefono: str = None

    _telefono = field_validator("telefono")(validar_telefono)


def _sin_repetidos(valores: list[str]) -> list[str]:
    return list(dict.fromkeys(valores))


@router_me.get("/usuarios/me")
def mi_perfil(usuario: Usuario = Depends(exigir_usuario)):
    return usuario_a_dict(usuario)


@router_me.patch("/usuarios/me")
def editar_mi_perfil(datos: UsuarioEditar, usuario: Usuario = Depends(exigir_usuario), db: Session = Depends(get_db)):
    return _editar_usuario(db, usuario, datos)


# Va en router_me (después de /usuarios/me) para que PATCH /usuarios/me no caiga aquí: el router de servicios
# internos se registra antes y exigiría el token interno a la propia sesión.
@router_me.patch("/usuarios/{id}", dependencies=[Depends(exigir_token_interno)])
def editar_usuario(id: str, datos: UsuarioEditar, db: Session = Depends(get_db)):
    """El bot guarda lo que la vecina le dice por chat (gustos, pueblo, formato de aviso…). Igual que /usuarios/me."""
    usuario = db.get(Usuario, id) if es_uuid(id) else None
    if usuario is None:
        raise ErrorApi(404, "usuario_no_encontrado", "No existe ese usuario")
    return _editar_usuario(db, usuario, datos)


def _editar_usuario(db: Session, usuario: Usuario, datos: UsuarioEditar) -> dict:
    """Aplica solo los campos enviados. 422 `validacion`/`municipio_no_encontrado`, 409 `telefono_en_uso`."""
    cambios = datos.model_dump(exclude_unset=True)

    if "nombre" in cambios:
        nombre = cambios.pop("nombre").strip()
        if not nombre:
            raise ErrorApi(422, "validacion", "El nombre no puede estar vacío", {"campo": "nombre"})
        usuario.nombre = nombre
    if "municipio" in cambios:
        municipio = _municipio(db, cambios.pop("municipio"))
        usuario.municipio = municipio.nombre if municipio else None
        # Al cambiar de pueblo, su ubicación pasa a ser la del pueblo salvo que mande otra.
        if municipio is not None:
            usuario.lat = cambios.pop("lat", municipio.lat)
            usuario.lon = cambios.pop("lon", municipio.lon)
    if "gustos" in cambios:
        usuario.gustos = _sin_repetidos(cambios.pop("gustos"))
    if "etiquetas_interes" in cambios:
        usuario.etiquetas_interes = _sin_repetidos([e.strip().lower() for e in cambios.pop("etiquetas_interes")])
    if "telefono" in cambios:
        telefono = cambios.pop("telefono")
        if telefono != usuario.telefono:
            otro = _por_telefono(db, telefono)
            if otro is not None:
                raise ErrorApi(409, "telefono_en_uso", "Ese teléfono ya es de otro usuario", {"campo": "telefono"})
            usuario.telefono = telefono
            # El número nuevo no está verificado hasta que confirme el código (/auth/whatsapp/verificar).
            usuario.whatsapp_verificado = False
    # lat, lon, formato_aviso, acepta_avisos, radio_km: tal cual
    for campo, valor in cambios.items():
        setattr(usuario, campo, valor)

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise ErrorApi(409, "telefono_en_uso", "Ese teléfono ya es de otro usuario", {"campo": "telefono"})
    return usuario_a_dict(usuario)
