"""¿Qué quiere la persona? Reglas baratas (sin tokens): publicar un evento, buscar qué hacer,
decir sus gustos, apuntarse o preguntar por el evento que está mirando."""

import re
from dataclasses import dataclass
from typing import Literal

from app.agentes.extractor import _normalizar

Tipo = Literal["publicar", "buscar", "gustos", "inscribir", "desinscribir", "pregunta_evento"]

_GUSTOS = r"\bme (gusta|gustan|encanta|encantan|interesa|interesan|chifla|chiflan)\b|\bmis gustos\b|\bme van\b"
_DESINSCRIBIR = (r"\b(desapuntame|desapuntarme|me desapunto|borrame|quitame|darme de baja) (de|del)\b|"
                 r"\bya no (voy|puedo ir|podemos ir)\b|\bcancela(r)? mi (plaza|inscripcion|reserva)\b|"
                 r"\bno voy a poder ir\b")
_INSCRIBIR = r"\b(apuntame|apuntarme|me apunto|inscribeme|inscribirme|reservame|quiero ir|vamos a ir|me quiero apuntar)\b"
_BUSCAR = (r"\b(que hay|que se hace|que planes?|planes|algo que hacer|que puedo hacer|que podemos hacer|que hacer|"
           r"actividades|agenda|eventos?|donde (ir|salir)|alguna (fiesta|ruta|actividad)|hay algo|recomiendame|"
           r"recomendacion(es)?|algo (para|gratis|tranquilo|con)|plan(es)? para|para ir con|"
           r"con (los |mis )?(ninos|peques|crios|nietos|hijos|perro|familia))\b")
_EMPIEZA_BUSCANDO = (r"(hola,? )?(algo|planes?|que|hay|donde|busco|buscamos|quiero|queremos|recomiendame|"
                     r"me recomiendas|alguna|algun|tienes|sabes)\b")
# Mensajes cortos tipo «rutas este fin de semana», «conciertos mañana», «algo para el finde»
_TIPO_DE_PLAN = (r"\b(rutas?|senderismo|excursion(es)?|conciertos?|fiestas?|talleres?|teatro|cine|mercados?|"
                 r"mercadillos?|deportes?|torneos?|musica|cultura|gastronomia|comidas?|cenas?|bailes?|charlas?|"
                 r"exposicion(es)?|actividades|juegos|ninos|peques|mayores)\b")
_CUANDO = (r"\b(este fin de semana|el fin de semana|fin de semana|este finde|el finde|finde|hoy|manana|pasado manana|"
           r"esta semana|la semana que viene|esta tarde|esta noche|este (lunes|martes|miercoles|jueves|viernes|"
           r"sabado|domingo)|el (sabado|domingo)|en navidad|este mes)\b")
_INTERROGATIVO =r"^\s*(¿|que|cuando|donde|cuanto|cuanta|como|hay|a que hora|quien|se puede|puedo)\b"
_FECHA_U_HORA = r"\b\d{1,2}\s+de\s+[a-z]+|\b\d{1,2}[:.h]\d{2}\b|\ba las \d"


def es_pregunta_concreta(texto: str) -> bool:
    """Una pregunta que no pide planes («¿hay que llevar agua?», no «¿qué hay este finde?»)."""
    t = _normalizar(texto).replace("¿", " ").strip()
    pregunta = "?" in texto or bool(re.search(_INTERROGATIVO, _normalizar(texto)))
    return pregunta and not re.search(_BUSCAR, t)


@dataclass
class Intencion:
    tipo: Tipo


def detectar(texto: str, mirando_evento: bool = False) -> Intencion:
    t = _normalizar(texto).replace("¿", " ").strip()
    pregunta = "?" in texto or bool(re.search(_INTERROGATIVO, _normalizar(texto)))

    if re.search(_GUSTOS, t) and not re.search(_FECHA_U_HORA, t):
        return Intencion("gustos")
    if re.search(_DESINSCRIBIR, t):  # N6b, antes que inscribir
        return Intencion("desinscribir")
    if re.search(_INSCRIBIR, t):
        return Intencion("inscribir")
    # Un post largo con fecha u hora es alguien publicando, aunque lleve un «¿te apuntas?»
    if len(texto) > 60 and re.search(_FECHA_U_HORA, t) and not re.search(r"\b(que hay|hay algo|que se hace)\b", t):
        return Intencion("publicar")
    # Corto y sin fecha ni hora concretas: busca planes. Con fecha u hora es alguien publicando
    if (len(texto) <= 60 and not mirando_evento and not re.search(_FECHA_U_HORA, t)
            and (re.search(_TIPO_DE_PLAN, t) or re.search(_CUANDO, t))):
        return Intencion("buscar")
    if mirando_evento and pregunta and not re.search(_BUSCAR, t):
        return Intencion("pregunta_evento")
    # Un anuncio largo («Concierto de la banda el domingo… con los niños del colegio») no es una búsqueda aunque
    # diga «con los niños»: quien busca pregunta o empieza con «algo», «planes», «qué», «busco»…
    if len(texto) > 90 and not pregunta and not re.match(_EMPIEZA_BUSCANDO, t):
        return Intencion("publicar")
    if re.search(_BUSCAR, t) or pregunta:
        return Intencion("buscar")
    return Intencion("publicar")
