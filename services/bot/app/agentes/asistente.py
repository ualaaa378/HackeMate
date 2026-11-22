"""Asistente del evento (POST /ai/responder-ficha): responde SOLO con lo que pone la ficha.
Si no está en la ficha, lo dice (puede_responder = False) y la pregunta se deriva al organizador."""

import re
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.agentes import extractor
from app.llm import router


class RespuestaFicha(BaseModel):
    puede_responder: bool
    respuesta: Optional[str] = None
    proveedor_ia: str = "reglas"


class _RespLLM(BaseModel):
    puede_responder: bool = Field(description="False si la respuesta no está en la ficha")
    respuesta: Optional[str] = Field(None, description="1-2 frases, en español, tono cercano")


SYSTEM = """Eres el asistente de un evento de un pueblo. Responde a la pregunta del vecino usando EXCLUSIVAMENTE
los datos de la ficha que te doy. Si la ficha no contiene la respuesta, pon puede_responder=false y respuesta=null:
no supongas, no inventes horarios, precios ni lugares. Respuestas cortas y claras, pensadas para personas mayores."""

CAMPOS = ["titulo", "descripcion", "categoria", "municipio", "lugar", "fecha_inicio", "fecha_fin",
          "precio_eur", "es_gratuito", "plazas_totales", "plazas_libres", "etiquetas"]


def _ficha_texto(evento: dict) -> str:
    return "\n".join(f"{c}: {evento[c]}" for c in CAMPOS if evento.get(c) not in (None, "", []))


def _hora(valor: str | None) -> str | None:
    try:
        return datetime.fromisoformat(valor).strftime("%d/%m a las %H:%M") if valor else None
    except ValueError:
        return None


def _por_reglas(evento: dict, pregunta: str) -> RespuestaFicha:
    """Solo las preguntas típicas con dato exacto en la ficha. Lo demás, al organizador."""
    t = extractor._normalizar(pregunta)
    r: str | None = None
    if re.search(r"\b(hora|cuando|que dia|empieza|comienza)\b", t) and (h := _hora(evento.get("fecha_inicio"))):
        r = f"Empieza el {h}."
    elif re.search(r"\b(precio|cuesta|cuanto|vale|pagar|gratis|entrada)\b", t):
        if evento.get("es_gratuito"):
            r = "Es gratis."
        elif evento.get("precio_eur") is not None:
            r = f"Cuesta {evento['precio_eur']:g} €."
    elif re.search(r"\b(donde|lugar|sitio|salida|quedamos)\b", t) and (evento.get("lugar") or evento.get("municipio")):
        r = f"Es en {', '.join(x for x in (evento.get('lugar'), evento.get('municipio')) if x)}."
    elif re.search(r"\b(plazas|sitio libre|quedan|hay sitio|aforo)\b", t) and evento.get("plazas_libres") is not None:
        r = f"Quedan {evento['plazas_libres']} plazas."
    return RespuestaFicha(puede_responder=r is not None, respuesta=r)


def responder(evento: dict, pregunta: str) -> RespuestaFicha:
    base = _por_reglas(evento, pregunta)
    if base.puede_responder:
        return base  # dato exacto: sin tokens
    res = router.estructurado(
        tarea="responder_ficha", system=SYSTEM,
        texto=f"FICHA:\n{_ficha_texto(evento)}\n\nPREGUNTA: {pregunta}",
        salida=_RespLLM,
        reglas=lambda _t: _RespLLM(puede_responder=False, respuesta=None),
    )
    ia = res.salida
    if not ia.puede_responder or not (ia.respuesta or "").strip():
        return RespuestaFicha(puede_responder=False, proveedor_ia=res.proveedor)
    return RespuestaFicha(puede_responder=True, respuesta=ia.respuesta.strip(), proveedor_ia=res.proveedor)
