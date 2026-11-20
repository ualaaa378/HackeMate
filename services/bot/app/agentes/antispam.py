"""Antispam (POST /ai/spam). Reglas baratas primero; la IA solo cuando las reglas dudan.
El bot solo puntúa: la API decide con su umbral (MODERACION_UMBRAL_SPAM) y el moderador ve el motivo."""

import re
import unicodedata
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.llm import router

DUDA_MIN, DUDA_MAX = 0.3, 0.7  # entre estos valores, se pregunta a la IA


class ResultadoSpam(BaseModel):
    score_spam: float = Field(ge=0, le=1)
    es_spam: bool
    motivo: Optional[str] = None
    proveedor_ia: str = "reglas"


class _SpamLLM(BaseModel):
    es_spam: bool
    score_spam: float = Field(ge=0, le=1, description="0 = contenido legítimo del pueblo, 1 = spam seguro")
    motivo: str = Field(description="Una frase en español para el moderador")


SYSTEM = """Eres el filtro antispam de una agenda de actividades de pueblos de Almería.
Es legítimo: eventos, ofertas de negocios locales, avisos del ayuntamiento, preguntas sobre un evento.
Es spam: publicidad ajena a los pueblos, estafas, cripto, apuestas, enlaces sospechosos, cadenas, insultos,
contenido sexual o mensajes repetidos sin relación. Devuelve score_spam (0-1), es_spam y un motivo breve."""

_ACORTADORES = r"\b(bit\.ly|tinyurl|goo\.gl|t\.co|cutt\.ly|is\.gd|shorturl)\b"
_PALABRAS = ["cripto", "bitcoin", "inversion garantizada", "gana dinero", "casino", "apuestas", "prestamo rapido",
             "haz clic", "click aqui", "premio", "has ganado", "sorteo exclusivo", "viagra", "contactame por privado",
             "trabaja desde casa", "forex", "onlyfans"]
_PUEBLO = ["lucainena", "senes", "velefique", "uleila", "tahal", "plaza", "ayuntamiento", "asociacion", "fiesta",
           "ruta", "vecinos", "iglesia", "polideportivo"]


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def puntuar_con_reglas(texto: str) -> ResultadoSpam:
    t = _normalizar(texto)
    puntos, motivos = 0.0, []
    if re.search(_ACORTADORES, t):
        puntos += 0.4
        motivos.append("enlace acortado")
    enlaces = len(re.findall(r"https?://", t))
    if enlaces >= 3:
        puntos += 0.3
        motivos.append(f"{enlaces} enlaces")
    if palabras := [p for p in _PALABRAS if p in t]:
        puntos += min(0.6, 0.3 * len(palabras))
        motivos.append("palabras típicas de spam: " + ", ".join(palabras[:3]))
    letras = [c for c in texto if c.isalpha()]
    if len(letras) > 20 and sum(c.isupper() for c in letras) / len(letras) > 0.7:
        puntos += 0.2
        motivos.append("casi todo en mayúsculas")
    if re.search(r"(.)\1{6,}", t) or texto.count("!") > 8:
        puntos += 0.1
        motivos.append("caracteres repetidos")
    if re.search(r"\b\d{9,}\b", t) and "whatsapp" in t:
        puntos += 0.1
        motivos.append("pide escribir a otro número")
    if any(p in t for p in _PUEBLO):
        puntos -= 0.2  # habla de los pueblos: menos probable que sea spam
    score = round(max(0.0, min(1.0, puntos)), 2)
    return ResultadoSpam(score_spam=score, es_spam=score >= DUDA_MAX,
                         motivo="; ".join(motivos) if motivos else "sin señales de spam")


def puntuar(texto: str, contexto: Literal["evento", "mensaje"] = "evento") -> ResultadoSpam:
    base = puntuar_con_reglas(texto)
    if not DUDA_MIN <= base.score_spam < DUDA_MAX:
        return base  # las reglas están seguras: no gastamos tokens
    res = router.estructurado(
        tarea="antispam",
        system=SYSTEM,
        texto=f"Contexto: {contexto}\n\n{texto}",
        salida=_SpamLLM,
        reglas=lambda _t: _SpamLLM(es_spam=base.es_spam, score_spam=base.score_spam, motivo=base.motivo or ""),
    )
    if res.proveedor == "reglas":
        return base
    ia = res.salida
    return ResultadoSpam(score_spam=round(ia.score_spam, 2), es_spam=ia.es_spam,
                         motivo=f"{ia.motivo} (reglas: {base.motivo})", proveedor_ia=res.proveedor)
