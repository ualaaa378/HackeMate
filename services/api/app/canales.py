"""Canales de mensajeria por los que el bot habla con la gente (WhatsApp, Telegram…).

Cada canal identifica a una persona con una direccion de contacto (components/schemas/Contacto):
- WhatsApp: el telefono E.164 (`+34600000000`), guardado en la columna `telefono`.
- Telegram: `tg:<chat_id>` (Telegram no da el telefono), guardado en `telegram_id` sin el prefijo.

Añadir un canal = una entrada en CANALES_MENSAJERIA + su columna en usuarios y publicadores (con migracion).
Las rutas no preguntan por el canal: usan las funciones de este modulo.
"""

import re
from collections.abc import Callable
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errores import ErrorApi
from app.modelos import Publicador, Usuario
from app.telefonos import normalizar_telefono


@dataclass(frozen=True)
class Canal:
    nombre: str  # valor del enum `canal`
    prefijo: str  # con el que empieza la direccion de contacto
    campo: str  # columna de usuarios y publicadores donde se guarda el valor
    normalizar: Callable[[str], str | None]  # direccion de contacto -> valor guardado (None si no encaja)
    formatear: Callable[[str], str]  # valor guardado -> direccion de contacto


_PATRON_TELEGRAM = re.compile(r"^-?[0-9]{1,20}$")
PREFIJO_TELEGRAM = "tg:"


def _normalizar_telegram(texto: str) -> str | None:
    texto = texto.strip()
    if texto[: len(PREFIJO_TELEGRAM)].lower() != PREFIJO_TELEGRAM:
        return None
    valor = texto[len(PREFIJO_TELEGRAM):].strip()
    return valor if _PATRON_TELEGRAM.match(valor) else None


CANALES_MENSAJERIA: dict[str, Canal] = {
    "whatsapp": Canal(
        nombre="whatsapp", prefijo="+", campo="telefono", normalizar=normalizar_telefono, formatear=lambda v: v
    ),
    "telegram": Canal(
        nombre="telegram",
        prefijo=PREFIJO_TELEGRAM,
        campo="telegram_id",
        normalizar=_normalizar_telegram,
        formatear=lambda v: PREFIJO_TELEGRAM + v,
    ),
}


def reconocer_contacto(texto: str) -> tuple[Canal, str] | None:
    """(canal, valor guardado) o None si no es la direccion de ningun canal."""
    if not isinstance(texto, str):
        return None
    for canal in CANALES_MENSAJERIA.values():
        valor = canal.normalizar(texto)
        if valor is not None:
            return canal, valor
    return None


def parsear_contacto(texto: str, campo: str = "contacto") -> tuple[Canal, str]:
    """Como reconocer_contacto, pero 422 `contacto_invalido` si no encaja en ningun canal."""
    reconocido = reconocer_contacto(texto)
    if reconocido is None:
        raise ErrorApi(
            422,
            "contacto_invalido",
            "El contacto debe ser un teléfono E.164 (+34600000000) o tg:<chat_id> de Telegram",
            {"campo": campo},
        )
    return reconocido


def validar_contacto(texto: str) -> str:
    """Para `field_validator` de pydantic: devuelve el contacto normalizado o ValueError (-> 422)."""
    reconocido = reconocer_contacto(texto)
    if reconocido is None:
        raise ValueError("El contacto debe ser un teléfono E.164 (+34600000000) o tg:<chat_id> de Telegram")
    return contacto_de(*reconocido)


def contacto_de(canal: Canal | str, valor: str) -> str:
    """Inverso de parsear_contacto: (telegram, "123") -> "tg:123"; (whatsapp, "+34…") -> "+34…"."""
    if isinstance(canal, str):
        canal = CANALES_MENSAJERIA[canal]
    return canal.formatear(valor)


def _como_par(contacto: str | tuple[Canal, str]) -> tuple[Canal, str]:
    return contacto if isinstance(contacto, tuple) else parsear_contacto(contacto)


def buscar_usuario_por_contacto(db: Session, contacto: str | tuple[Canal, str]) -> Usuario | None:
    canal, valor = _como_par(contacto)
    return db.scalar(select(Usuario).where(getattr(Usuario, canal.campo) == valor))


def buscar_publicador_por_contacto(db: Session, contacto: str | tuple[Canal, str]) -> Publicador | None:
    """Por la columna del canal. Si no hay, por el telefono del usuario vinculado a ese contacto (POST
    /usuarios/vincular) y, al final, por la entidad del usuario (`usuarios.publicador_id`)."""
    canal, valor = _como_par(contacto)
    publicador = db.scalar(
        select(Publicador).where(getattr(Publicador, canal.campo) == valor).order_by(Publicador.creado_en)
    )
    if publicador is None:
        usuario = buscar_usuario_por_contacto(db, (canal, valor))
        if usuario is not None and usuario.telefono and canal.campo != "telefono":
            publicador = db.scalar(
                select(Publicador).where(Publicador.telefono == usuario.telefono).order_by(Publicador.creado_en)
            )
        # La persona que publica en nombre de una entidad con otro teléfono (p. ej. la concejala del ayuntamiento)
        if publicador is None and usuario is not None and usuario.publicador_id:
            publicador = db.get(Publicador, usuario.publicador_id)
    return publicador
