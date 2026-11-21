"""Validación de `imagen_url` (fotos del chat y foto o cartel de un evento).

Se admite una URL `http(s)://` (hasta 2048 caracteres) o una data URL `data:image/(png|jpeg|webp|gif);base64,…`.
Otra cosa da 422 `imagen_invalida`. El tamaño máximo (de imagen ya decodificada) y el error al pasarse los
decide quien llama: el chat responde 413 `imagen_demasiado_grande` y los eventos 422 `imagen_invalida`.
"""

import re

from app.errores import ErrorApi

MAX_URL_IMAGEN = 2048
_URL_HTTP = re.compile(r"https?://[^\s/?#]+[^\s]*", re.IGNORECASE)
_DATA_URL = re.compile(r"data:image/(png|jpeg|webp|gif);base64,([A-Za-z0-9+/]*={0,2})")


def _texto_tamano(max_bytes: int) -> str:
    megas = max_bytes / (1024 * 1024)
    return f"{megas:.1f}".rstrip("0").rstrip(".").replace(".", ",") + " MB"


def validar_imagen(
    imagen_url: str,
    max_bytes: int,
    status_grande: int = 413,
    code_grande: str = "imagen_demasiado_grande",
) -> str:
    """Devuelve la imagen tal cual si vale; si no, lanza ErrorApi."""
    if imagen_url.startswith("data:"):
        coincide = _DATA_URL.fullmatch(imagen_url)
        if coincide is None or not coincide.group(2):
            raise ErrorApi(422, "imagen_invalida", "La foto debe ser una data URL PNG, JPEG, WebP o GIF en base64",
                           {"campo": "imagen_url"})
        datos = coincide.group(2).rstrip("=")
        if len(datos) * 3 // 4 > max_bytes:
            raise ErrorApi(status_grande, code_grande, f"La foto ocupa más de {_texto_tamano(max_bytes)}",
                           {"campo": "imagen_url", "max_bytes": max_bytes})
        return imagen_url
    if len(imagen_url) > MAX_URL_IMAGEN or _URL_HTTP.fullmatch(imagen_url) is None:
        raise ErrorApi(422, "imagen_invalida", "La foto debe ser una URL http(s) o una data URL de imagen",
                       {"campo": "imagen_url"})
    return imagen_url
