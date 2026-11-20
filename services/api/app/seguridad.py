"""Protección de rutas: servicios internos (el bot, cabecera X-Internal-Token) y moderador."""

import secrets

from fastapi import Header

from app.config import get_settings
from app.errores import ErrorApi


def exigir_token_interno(x_internal_token: str | None = Header(None)) -> None:
    """Dependencia: `dependencies=[Depends(exigir_token_interno)]`. 401 si falta o no coincide."""
    esperado = get_settings().internal_token
    if not x_internal_token or not secrets.compare_digest(x_internal_token.encode(), esperado.encode()):
        raise ErrorApi(401, "token_interno_invalido", "Falta la cabecera X-Internal-Token o no es correcta")


def es_servicio_interno(x_internal_token: str | None) -> bool:
    """Para rutas públicas que devuelven más datos (p. ej. teléfonos) si quien llama es el bot."""
    esperado = get_settings().internal_token
    return bool(x_internal_token) and secrets.compare_digest(x_internal_token.encode(), esperado.encode())


# Quién figura en `evento.moderacion.revisado_por` cuando decide un servicio interno (el bot en nombre del
# moderador que escribe por WhatsApp/Telegram, o el panel mientras no haya login).
REVISOR_INTERNO = "moderador (servicio interno)"


def exigir_moderador(x_internal_token: str | None = Header(None)) -> str:
    """Dependencia única de las rutas de moderador: `revisor: str = Depends(exigir_moderador)`.

    Devuelve el nombre de quien decide (para `revisado_por`). Hoy solo acepta X-Internal-Token (401 si falta).
    H3: aceptar también `Authorization: Bearer <jwt>` con `rol == "moderador"` (403 `rol_insuficiente` si el
    rol es otro) y devolver el nombre del usuario; las rutas no cambian.
    """
    if es_servicio_interno(x_internal_token):
        return REVISOR_INTERNO
    raise ErrorApi(401, "no_autenticado", "Hace falta ser moderador (cabecera X-Internal-Token)")
