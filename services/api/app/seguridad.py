"""Protección de las rutas que solo usan otros servicios (el bot): cabecera X-Internal-Token."""

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
