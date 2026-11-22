"""Teléfonos en E.164 (+34600000000), el formato del contrato (components/schemas/Telefono)."""

import re

PATRON_E164 = re.compile(r"^\+[1-9][0-9]{6,14}$")
_SEPARADORES = re.compile(r"[\s\-.()/]")


def normalizar_telefono(valor: str) -> str | None:
    """Devuelve el teléfono en E.164 o None si no lo es.

    Admite separadores (espacios, guiones, puntos, paréntesis) y el prefijo 00 en vez de +.
    Un `+` que llega convertido en espacio (codificación de formulario en la URL) se recupera.
    """
    if not isinstance(valor, str):
        return None
    perdio_el_mas = valor[:1] == " " and valor.strip()[:1].isdigit()
    limpio = _SEPARADORES.sub("", valor)
    if limpio.startswith("00"):
        limpio = "+" + limpio[2:]
    elif perdio_el_mas:
        limpio = "+" + limpio
    return limpio if PATRON_E164.match(limpio) else None


def validar_telefono(valor: str) -> str:
    """Para `field_validator` de pydantic: ValueError (-> 422) si no es E.164."""
    normalizado = normalizar_telefono(valor)
    if normalizado is None:
        raise ValueError("El teléfono debe ir en formato E.164, p. ej. +34600000000")
    return normalizado
