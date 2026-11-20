"""Visitantes que escriben en otro idioma. Se detecta con palabras frecuentes (sin tokens); su
mensaje se traduce al español para que el bot lo entienda igual, y la respuesta se traduce de vuelta.
Si la IA no está, se responde en español: mejor eso que nada."""

import json
import re

from pydantic import BaseModel

from app.llm import router

NOMBRES = {"es": "español", "en": "inglés", "fr": "francés", "de": "alemán", "it": "italiano", "pt": "portugués"}

_PALABRAS = {
    "es": "el la los las que de y en un una hay para por con es este esta qué cuándo dónde hola gracias quiero me".split(),
    "en": "the and is are what where when there this weekend near me any events hello hi thanks please i want can how".split(),
    "fr": "le la les et est sont quoi où quand il y a ce week-end près de moi bonjour merci je veux des".split(),
    "de": "der die das und ist sind was wo wann gibt es dieses wochenende in der nähe hallo danke ich möchte".split(),
    "it": "il lo la gli le e è sono cosa dove quando c'è questo fine settimana vicino ciao grazie voglio".split(),
    "pt": "o a os as e é são que onde quando há este fim de semana perto olá obrigado quero tem".split(),
}


def detectar(texto: str) -> str | None:
    """Código del idioma, o None si el texto es demasiado corto para saberlo."""
    palabras = re.findall(r"[a-záéíóúàèìòùâêîôûäöüçñß'-]+", texto.lower())
    if len(palabras) < 2:
        return None
    puntos = {idioma: sum(p in lista for p in palabras) for idioma, lista in _PALABRAS.items()}
    mejor = max(puntos, key=puntos.get)
    if puntos[mejor] < 2 or puntos[mejor] <= puntos["es"] and mejor != "es":
        return "es" if puntos["es"] >= 2 else None
    return mejor


class _Traduccion(BaseModel):
    textos: list[str]


SYSTEM = """Traduce cada texto de la lista al idioma indicado. Devuelve la misma cantidad de textos y en el mismo
orden. Conserva tal cual los emojis, los asteriscos de negrita (*así*), los enlaces, las fechas y los números, y
los nombres de pueblos y de eventos. Tono cercano y sencillo."""


def traducir(textos: list[str], idioma: str, origen: str = "es") -> list[str]:
    """Traduce de `origen` a `idioma`. Por defecto, las respuestas del bot (en español) al del visitante."""
    if idioma == origen or not textos:
        return textos
    destino = NOMBRES.get(idioma, idioma)
    res = router.estructurado(
        tarea="traducir", system=SYSTEM,
        texto=f"Traduce al {destino} estos {len(textos)} textos (JSON):\n{json.dumps(textos, ensure_ascii=False)}",
        salida=_Traduccion, reglas=lambda _t: _Traduccion(textos=textos),
    )
    traducidos = res.salida.textos
    return traducidos if len(traducidos) == len(textos) else textos
