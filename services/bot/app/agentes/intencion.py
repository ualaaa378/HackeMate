"""¿Qué quiere la persona? Reglas baratas (sin tokens): publicar un evento, buscar qué hacer,
decir sus gustos, apuntarse o preguntar por el evento que está mirando."""

import re
from dataclasses import dataclass
from typing import Literal

from app.agentes.extractor import _normalizar

Tipo = Literal["publicar", "buscar", "gustos", "inscribir", "pregunta_evento"]

_GUSTOS = r"\bme (gusta|gustan|encanta|encantan|interesa|interesan|chifla|chiflan)\b|\bmis gustos\b|\bme van\b"
_INSCRIBIR = r"\b(apuntame|apuntarme|me apunto|inscribeme|inscribirme|reservame|quiero ir|vamos a ir|me quiero apuntar)\b"
_BUSCAR = (r"\b(que hay|que se hace|que planes?|planes|algo que hacer|que puedo hacer|que hacer|actividades|agenda|"
           r"eventos?|donde (ir|salir)|alguna (fiesta|ruta|actividad)|hay algo|recomiendame|recomendacion(es)?)\b")
_INTERROGATIVO = r"^\s*(¿|que|cuando|donde|cuanto|cuanta|como|hay|a que hora|quien|se puede|puedo)\b"
_FECHA_U_HORA = r"\b\d{1,2}\s+de\s+[a-z]+|\b\d{1,2}[:.h]\d{2}\b|\ba las \d"


@dataclass
class Intencion:
    tipo: Tipo


def detectar(texto: str, mirando_evento: bool = False) -> Intencion:
    t = _normalizar(texto).replace("¿", " ").strip()
    pregunta = "?" in texto or bool(re.search(_INTERROGATIVO, _normalizar(texto)))

    if re.search(_GUSTOS, t) and not re.search(_FECHA_U_HORA, t):
        return Intencion("gustos")
    if re.search(_INSCRIBIR, t):
        return Intencion("inscribir")
    # Un post largo con fecha u hora es alguien publicando, aunque lleve un «¿te apuntas?»
    if len(texto) > 60 and re.search(_FECHA_U_HORA, t) and not re.search(r"\b(que hay|hay algo|que se hace)\b", t):
        return Intencion("publicar")
    if mirando_evento and pregunta and not re.search(_BUSCAR, t):
        return Intencion("pregunta_evento")
    if re.search(_BUSCAR, t) or pregunta:
        return Intencion("buscar")
    return Intencion("publicar")
