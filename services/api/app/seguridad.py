"""Protección de rutas: servicios internos (el bot, cabecera X-Internal-Token) y usuarios (Authorization: Bearer).

Sesiones: JWT HS256 propio, firmado con JWT_SECRET, con `sub` (usuario_id), `rol`, `iat` y `exp`. Se implementa
a mano con hmac/hashlib/base64 para no añadir dependencias. El rol que manda es el de la base de datos (si a
alguien le quitan el rol de moderador, su sesión deja de valer para moderar aunque el token diga otra cosa).

Dependencias de FastAPI:
- `usuario_actual`: el usuario de la sesión o None si no hay cabecera (401 si la hay pero no vale).
- `exigir_usuario`: 401 `no_autenticado` si no hay sesión.
- `exigir_rol(*roles)`: además, 403 `rol_insuficiente` si el rol no está en la lista.
- `exigir_moderador`: X-Internal-Token (el bot, en nombre del moderador) o Bearer de un moderador.
"""

import base64
import binascii
import hashlib
import hmac
import json
import secrets
import time

from fastapi import Depends, Header
from sqlalchemy.orm import Session

from app.config import get_settings
from app.db import get_db
from app.errores import ErrorApi
from app.modelos import ROLES, Usuario
from app.serializar import usuario_a_dict

ALGORITMO = "HS256"


def exigir_token_interno(x_internal_token: str | None = Header(None)) -> None:
    """Dependencia: `dependencies=[Depends(exigir_token_interno)]`. 401 si falta o no coincide."""
    esperado = get_settings().internal_token
    if not x_internal_token or not secrets.compare_digest(x_internal_token.encode(), esperado.encode()):
        raise ErrorApi(401, "token_interno_invalido", "Falta la cabecera X-Internal-Token o no es correcta")


def es_servicio_interno(x_internal_token: str | None) -> bool:
    """Para rutas públicas que devuelven más datos (p. ej. teléfonos) si quien llama es el bot."""
    esperado = get_settings().internal_token
    return bool(x_internal_token) and secrets.compare_digest(x_internal_token.encode(), esperado.encode())


# --- JWT ------------------------------------------------------------------------------------------


def _b64(datos: bytes) -> str:
    return base64.urlsafe_b64encode(datos).rstrip(b"=").decode("ascii")


def _b64_leer(texto: str) -> bytes:
    return base64.urlsafe_b64decode(texto + "=" * (-len(texto) % 4))


def _firma(mensaje: bytes) -> str:
    return _b64(hmac.new(get_settings().jwt_secret.encode(), mensaje, hashlib.sha256).digest())


def emitir_jwt(usuario_id: str, rol: str, expira_min: int | None = None, ahora: float | None = None) -> str:
    """JWT firmado para el usuario. `expira_min` por defecto: JWT_EXPIRA_MIN."""
    ahora = int(time.time() if ahora is None else ahora)
    minutos = get_settings().jwt_expira_min if expira_min is None else expira_min
    cabecera = _b64(json.dumps({"alg": ALGORITMO, "typ": "JWT"}, separators=(",", ":")).encode())
    carga = _b64(
        json.dumps(
            {"sub": usuario_id, "rol": rol, "iat": ahora, "exp": ahora + int(minutos) * 60}, separators=(",", ":")
        ).encode()
    )
    mensaje = f"{cabecera}.{carga}"
    return f"{mensaje}.{_firma(mensaje.encode())}"


def _token_invalido(motivo: str = "La sesión no es válida") -> ErrorApi:
    return ErrorApi(401, "token_invalido", motivo)


def leer_jwt(token: str) -> dict:
    """Comprueba firma, algoritmo y caducidad. Devuelve los claims o lanza 401 (`token_invalido`/`token_caducado`)."""
    partes = token.split(".")
    if len(partes) != 3 or not all(partes):
        raise _token_invalido()
    cabecera_b64, carga_b64, firma = partes
    try:
        cabecera = json.loads(_b64_leer(cabecera_b64))
        carga = json.loads(_b64_leer(carga_b64))
    except (ValueError, binascii.Error):
        raise _token_invalido() from None
    # Solo HS256: así nadie cuela un token con alg "none" o con otro algoritmo.
    if not isinstance(cabecera, dict) or cabecera.get("alg") != ALGORITMO:
        raise _token_invalido()
    if not hmac.compare_digest(firma.encode(), _firma(f"{cabecera_b64}.{carga_b64}".encode()).encode()):
        raise _token_invalido()
    if not isinstance(carga, dict) or not isinstance(carga.get("sub"), str):
        raise _token_invalido()
    exp = carga.get("exp")
    if not isinstance(exp, (int, float)) or isinstance(exp, bool):
        raise _token_invalido()
    if exp <= time.time():
        raise ErrorApi(401, "token_caducado", "La sesión ha caducado: vuelve a entrar")
    return carga


def respuesta_token(usuario: Usuario) -> dict:
    """components/schemas/Token de openapi.yaml."""
    return {
        "access_token": emitir_jwt(usuario.id, usuario.rol),
        "token_type": "bearer",
        "usuario": usuario_a_dict(usuario),
    }


# --- Dependencias -------------------------------------------------------------------------------


def _bearer(authorization: str | None) -> str | None:
    if not authorization:
        return None
    esquema, _, token = authorization.strip().partition(" ")
    if esquema.lower() != "bearer" or not token.strip():
        raise _token_invalido("La cabecera Authorization debe ser «Bearer <token>»")
    return token.strip()


def _usuario_de_cabecera(authorization: str | None, db: Session) -> Usuario | None:
    token = _bearer(authorization)
    if token is None:
        return None
    claims = leer_jwt(token)
    usuario = db.get(Usuario, claims["sub"])
    if usuario is None:
        raise _token_invalido("El usuario de la sesión ya no existe")
    return usuario


def usuario_actual(authorization: str | None = Header(None), db: Session = Depends(get_db)) -> Usuario | None:
    """Usuario de la sesión o None si no hay cabecera Authorization. Una sesión mal formada, mal firmada o
    caducada da 401 (no se trata como anónima, para que la app sepa que tiene que volver a entrar)."""
    return _usuario_de_cabecera(authorization, db)


def _no_autenticado(mensaje: str = "Hace falta iniciar sesión") -> ErrorApi:
    return ErrorApi(401, "no_autenticado", mensaje)


def exigir_usuario(usuario: Usuario | None = Depends(usuario_actual)) -> Usuario:
    if usuario is None:
        raise _no_autenticado()
    return usuario


def _rol_insuficiente(roles: tuple[str, ...]) -> ErrorApi:
    return ErrorApi(403, "rol_insuficiente", "Tu usuario no tiene permiso para esto", {"roles": list(roles)})


def exigir_rol(*roles: str):
    """Dependencia: `usuario: Usuario = Depends(exigir_rol("moderador"))`. 401 sin sesión, 403 si el rol no vale."""
    desconocidos = set(roles) - set(ROLES)
    if not roles or desconocidos:
        raise ValueError(f"Roles no válidos: {sorted(desconocidos) or 'ninguno'}")

    def _dependencia(usuario: Usuario = Depends(exigir_usuario)) -> Usuario:
        if usuario.rol not in roles:
            raise _rol_insuficiente(roles)
        return usuario

    return _dependencia


# Quién figura en `evento.moderacion.revisado_por` cuando decide un servicio interno (el bot en nombre del
# moderador que escribe por WhatsApp/Telegram).
REVISOR_INTERNO = "moderador (servicio interno)"


def exigir_moderador(
    x_internal_token: str | None = Header(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> str:
    """Dependencia única de las rutas de moderador: `revisor: str = Depends(exigir_moderador)`.

    Acepta X-Internal-Token (el bot) o `Authorization: Bearer <jwt>` de un usuario con rol `moderador`.
    Devuelve el nombre de quien decide (para `revisado_por`). 401 sin credenciales; 403 `rol_insuficiente` si
    la sesión es de otro rol.
    """
    if es_servicio_interno(x_internal_token):
        return REVISOR_INTERNO
    usuario = _usuario_de_cabecera(authorization, db)
    if usuario is None:
        raise _no_autenticado("Hace falta ser moderador (sesión de moderador o cabecera X-Internal-Token)")
    if usuario.rol != "moderador":
        raise _rol_insuficiente(("moderador",))
    return usuario.nombre
