"""Login: código de un solo uso por WhatsApp/Telegram (H2.6), Google (H3.1) y modo demo.

Todas devuelven components/schemas/Token: `{access_token, token_type: "bearer", usuario}`.

Código: 6 dígitos (`secrets`), caduca a los CODIGO_VALIDEZ_MIN, como mucho CODIGOS_POR_HORA por teléfono y
CODIGO_MAX_INTENTOS fallos antes de anularlo. Se guarda solo su HMAC (clave JWT_SECRET). El aviso lo manda el
bot (`notificar`): si la persona tiene Telegram vinculado le llega por ahí; si no, por WhatsApp.
"""

import hashlib
import hmac
import logging
import secrets
from datetime import timedelta
from typing import Annotated, Literal

import httpx
from fastapi import APIRouter, BackgroundTasks, Depends
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import func, select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errores import ErrorApi
from app.modelos import ROLES, CodigoVerificacion, Publicador, Usuario, ahora
from app.notificaciones import enviar_en_segundo_plano, notificar
from app.rutas.publico import es_uuid
from app.rutas.usuarios import NOMBRE_POR_DEFECTO, _nuevo_usuario
from app.seguridad import respuesta_token
from app.serializar import fecha_iso
from app.telefonos import validar_telefono

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])

CODIGO_VALIDEZ_MIN = 10
CODIGOS_POR_HORA = 3
CODIGO_MAX_INTENTOS = 5
EMISORES_GOOGLE = ("accounts.google.com", "https://accounts.google.com")

# Transporte de httpx para Google. None = red real; los tests ponen un httpx.MockTransport.
_transporte: httpx.BaseTransport | None = None


def generar_codigo() -> str:
    return f"{secrets.randbelow(10**6):06d}"


def _hash_codigo(telefono: str, codigo: str) -> str:
    clave = get_settings().jwt_secret.encode()
    return hmac.new(clave, f"{telefono}:{codigo}".encode(), hashlib.sha256).hexdigest()


def _por_telefono(db: Session, telefono: str) -> Usuario | None:
    return db.scalar(select(Usuario).where(Usuario.telefono == telefono))


# --- Código por WhatsApp / Telegram -------------------------------------------------------------


class PedirCodigo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telefono: str

    _telefono = field_validator("telefono")(validar_telefono)


class VerificarCodigo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    telefono: str
    codigo: Annotated[str, Field(pattern=r"^[0-9]{6}$")]

    _telefono = field_validator("telefono")(validar_telefono)


@router.post("/whatsapp/codigo")
def pedir_codigo(datos: PedirCodigo, background_tasks: BackgroundTasks, db: Session = Depends(get_db)):
    """El aviso con el código se guarda en la misma transacción y sale hacia el bot después de responder.
    `enviado` = el aviso tiene destino y está en camino (en cola si el bot está caído); false si no hay a dónde
    mandarlo."""
    momento = ahora()
    recientes = db.scalar(
        select(func.count())
        .select_from(CodigoVerificacion)
        .where(CodigoVerificacion.telefono == datos.telefono, CodigoVerificacion.creado_en > momento - timedelta(hours=1))
    )
    if recientes >= CODIGOS_POR_HORA:
        raise ErrorApi(
            429, "demasiados_codigos", "Has pedido demasiados códigos: espera un rato antes de pedir otro",
            {"maximo_por_hora": CODIGOS_POR_HORA},
        )

    # Solo vale el último código pedido.
    anteriores = db.scalars(
        select(CodigoVerificacion).where(CodigoVerificacion.telefono == datos.telefono, CodigoVerificacion.usado.is_(False))
    ).all()
    for anterior in anteriores:
        anterior.usado = True

    codigo = generar_codigo()
    registro = CodigoVerificacion(
        telefono=datos.telefono,
        codigo_hash=_hash_codigo(datos.telefono, codigo),
        expira_en=momento + timedelta(minutes=CODIGO_VALIDEZ_MIN),
        intentos=0,
        usado=False,
        creado_en=momento,
    )
    db.add(registro)
    db.flush()

    texto = (
        f"Tu código de HackeMate es {codigo}. Caduca en {CODIGO_VALIDEZ_MIN} minutos. "
        "No se lo des a nadie: nunca te lo pediremos."
    )
    usuario = _por_telefono(db, datos.telefono)
    if usuario is not None:
        aviso = notificar(db, tipo="confirmacion", texto=texto, usuario=usuario, formato="texto", enviar=False)
    else:
        # Un publicador que pidió el alta y ya habla con el bot por Telegram recibe el código por ahí.
        publicador = db.scalar(
            select(Publicador).where(Publicador.telefono == datos.telefono).order_by(Publicador.creado_en)
        )
        contacto = f"tg:{publicador.telegram_id}" if publicador is not None and publicador.telegram_id else None
        aviso = notificar(
            db, tipo="confirmacion", texto=texto, telefono=datos.telefono, contacto=contacto, enviar=False
        )
    db.commit()
    enviar_en_segundo_plano(background_tasks, db, [aviso])
    return {"enviado": aviso.estado_envio != "fallida", "expira_en": fecha_iso(registro.expira_en)}


def _codigo_invalido() -> ErrorApi:
    return ErrorApi(401, "codigo_invalido", "El código no es correcto o ha caducado: pide otro")


def _verificar_telefono(db: Session, telefono: str) -> Usuario:
    """El teléfono queda verificado: usuario (se crea como vecino si no existe) y publicadores en `solicitado`."""
    usuario = _por_telefono(db, telefono)
    if usuario is None:
        usuario = _nuevo_usuario(telefono, None, None)
        db.add(usuario)
        db.flush()
    usuario.whatsapp_verificado = True

    publicadores = db.scalars(
        select(Publicador).where(Publicador.telefono == telefono).order_by(Publicador.creado_en)
    ).all()
    for publicador in publicadores:
        if publicador.estado == "solicitado":
            publicador.estado = "whatsapp_verificado"
        if publicador.usuario_id is None:
            publicador.usuario_id = usuario.id
        if usuario.publicador_id is None:
            usuario.publicador_id = publicador.id
    return usuario


@router.post("/whatsapp/verificar")
def verificar_codigo(datos: VerificarCodigo, db: Session = Depends(get_db)):
    registro = db.scalar(
        select(CodigoVerificacion)
        .where(CodigoVerificacion.telefono == datos.telefono, CodigoVerificacion.usado.is_(False))
        .order_by(CodigoVerificacion.creado_en.desc())
    )
    if registro is None or registro.expira_en <= ahora():
        raise _codigo_invalido()
    if not hmac.compare_digest(registro.codigo_hash, _hash_codigo(datos.telefono, datos.codigo)):
        registro.intentos += 1
        if registro.intentos >= CODIGO_MAX_INTENTOS:
            registro.usado = True
        db.commit()
        raise _codigo_invalido()

    registro.usado = True
    usuario = _verificar_telefono(db, datos.telefono)
    try:
        db.commit()
    except IntegrityError:
        # Otra petición ha dado de alta el mismo teléfono a la vez: se repite sobre el usuario que ya existe.
        db.rollback()
        registro = db.get(CodigoVerificacion, registro.id)
        registro.usado = True
        usuario = _verificar_telefono(db, datos.telefono)
        db.commit()
    return respuesta_token(usuario)


# --- Google ---------------------------------------------------------------------------------------


class LoginGoogle(BaseModel):
    model_config = ConfigDict(extra="forbid")

    id_token: Annotated[str, Field(min_length=1, max_length=4096)]


def _token_google_invalido() -> ErrorApi:
    return ErrorApi(401, "token_google_invalido", "Google no ha validado la sesión: vuelve a intentarlo")


def _consultar_google(id_token: str) -> dict:
    """Valida el id_token con el endpoint tokeninfo de Google (comprueba firma y caducidad)."""
    ajustes = get_settings()
    try:
        with httpx.Client(transport=_transporte, timeout=ajustes.google_timeout_s) as cliente:
            r = cliente.get(ajustes.google_tokeninfo_url, params={"id_token": id_token})
    except httpx.HTTPError as e:
        log.warning("Google tokeninfo no responde: %s", e)
        raise ErrorApi(503, "google_no_disponible", "No se puede contactar con Google ahora mismo") from None
    if r.status_code >= 500:
        raise ErrorApi(503, "google_no_disponible", "No se puede contactar con Google ahora mismo")
    if r.status_code != 200:
        raise _token_google_invalido()
    try:
        datos = r.json()
    except ValueError:
        raise _token_google_invalido() from None
    if not isinstance(datos, dict):
        raise _token_google_invalido()
    return datos


def _verdadero(valor) -> bool:
    return valor is True or (isinstance(valor, str) and valor.lower() == "true")


@router.post("/google")
def login_google(datos: LoginGoogle, db: Session = Depends(get_db)):
    client_id = get_settings().google_client_id
    if not client_id:
        raise ErrorApi(503, "google_no_configurado", "El login con Google no está configurado (GOOGLE_CLIENT_ID)")
    info = _consultar_google(datos.id_token)

    email = info.get("email")
    sub = info.get("sub")
    if info.get("aud") != client_id or info.get("iss") not in EMISORES_GOOGLE:
        raise _token_google_invalido()
    try:
        caducado = int(info.get("exp", 0)) <= int(ahora().timestamp())
    except (TypeError, ValueError):
        caducado = True
    if caducado or not isinstance(sub, str) or not sub or not isinstance(email, str) or "@" not in email:
        raise _token_google_invalido()
    if not _verdadero(info.get("email_verified")):
        raise ErrorApi(401, "email_no_verificado", "Tu cuenta de Google no tiene el email verificado")
    email = email.strip().lower()[:254]

    usuario = db.scalar(select(Usuario).where(Usuario.google_sub == sub))
    if usuario is None:
        usuario = db.scalar(select(Usuario).where(func.lower(Usuario.email) == email))
        if usuario is None:
            nombre = (info.get("name") or info.get("given_name") or email.split("@")[0] or NOMBRE_POR_DEFECTO)
            usuario = Usuario(nombre=str(nombre).strip()[:120] or NOMBRE_POR_DEFECTO, rol="vecino", email=email)
            db.add(usuario)
        if usuario.google_sub is None:
            usuario.google_sub = sub[:64]
    try:
        db.commit()
    except IntegrityError:
        # Dos logins a la vez con la misma cuenta: el segundo usa el usuario que ha creado el primero.
        db.rollback()
        usuario = db.scalar(select(Usuario).where(Usuario.google_sub == sub)) or db.scalar(
            select(Usuario).where(func.lower(Usuario.email) == email)
        )
        if usuario is None:
            raise
    return respuesta_token(usuario)


# --- Acceso de la moderación del ayuntamiento ------------------------------------------------------


class LoginAdmin(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario: str = Field(min_length=1, max_length=100)
    contrasena: str = Field(min_length=1, max_length=200)


def _igual(a: str, b: str) -> bool:
    return hmac.compare_digest(a.encode("utf-8"), b.encode("utf-8"))


@router.post("/admin")
def login_admin(datos: LoginAdmin, db: Session = Depends(get_db)):
    """Usuario y contraseña de la moderación (ADMIN_USUARIO / ADMIN_CONTRASENA) → sesión del moderador más antiguo.
    Funciona con y sin DEMO_MODE. Comparación en tiempo constante; el error no dice cuál de los dos falla."""
    ajustes = get_settings()
    usuario_ok = _igual(datos.usuario.strip(), ajustes.admin_usuario)
    contrasena_ok = bool(ajustes.admin_contrasena) and _igual(datos.contrasena, ajustes.admin_contrasena)
    if not (usuario_ok and contrasena_ok):
        log.info("acceso de moderación rechazado")
        raise ErrorApi(401, "credenciales_invalidas", "Usuario o contraseña incorrectos")
    moderador = db.scalar(
        select(Usuario).where(Usuario.rol == "moderador").order_by(Usuario.creado_en, Usuario.id).limit(1)
    )
    if moderador is None:
        raise ErrorApi(503, "sin_moderador", "No hay ningún usuario moderador en la base de datos")
    return respuesta_token(moderador)


# --- Modo demo ------------------------------------------------------------------------------------


class LoginDemo(BaseModel):
    model_config = ConfigDict(extra="forbid")

    usuario_id: str | None = None
    rol: Literal[ROLES] | None = None


@router.post("/demo")
def login_demo(datos: LoginDemo, db: Session = Depends(get_db)):
    """Solo con DEMO_MODE=true: sesión como un usuario concreto o como el primero (más antiguo) con ese rol."""
    if not get_settings().demo_mode:
        raise ErrorApi(404, "no_encontrado", "Not Found")
    if datos.usuario_id is not None:
        usuario = db.get(Usuario, datos.usuario_id) if es_uuid(datos.usuario_id) else None
    elif datos.rol is not None:
        usuario = db.scalar(
            select(Usuario).where(Usuario.rol == datos.rol).order_by(Usuario.creado_en, Usuario.id).limit(1)
        )
    else:
        raise ErrorApi(422, "validacion", "Indica usuario_id o rol", {"campos": ["usuario_id", "rol"]})
    if usuario is None:
        raise ErrorApi(404, "usuario_no_encontrado", "No hay ningún usuario así")
    return respuesta_token(usuario)
