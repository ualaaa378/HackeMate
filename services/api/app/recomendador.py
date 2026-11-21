"""Recomendador por reglas (H3.6). Sin embeddings: son opcionales y aquí no hacen falta.

Cada evento `publicado` que aún no ha empezado recibe una puntuación con estas razones:

| razón      | peso                                                                                   |
|------------|----------------------------------------------------------------------------------------|
| gustos     | +3 si la categoría está en sus gustos; +2 por etiqueta de interés que coincide (máx. +4) |
| distancia  | +2 en su pueblo, bajando hasta 0 en su `radio_km` (30 km si no tiene); negativo más allá |
| fecha      | hasta +1.5 si es hoy, bajando a 0 a los 30 días                                         |
| plazas     | +1 si quedan plazas, +1.5 si son las últimas; −3 si está completo (lista de espera)    |
| historial  | +1 si ya se apuntó antes a eventos de esa categoría                                    |

Se excluyen los eventos a los que ya está apuntado (en cualquier estado salvo `cancelada`) y los suyos propios
como publicador. El motivo junta las 2–3 razones de más peso en una frase:
«Te gusta el senderismo, es en Velefique (a 5 km) y quedan 8 plazas».
"""

import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from app.config import get_settings
from app.modelos import Evento, Inscripcion, Municipio, Usuario
from app.rutas.publico import distancia_km

RADIO_POR_DEFECTO_KM = 30.0
VENTANA_DIAS = 30
PESO_CATEGORIA = 3.0
PESO_ETIQUETA = 2.0
MAX_ETIQUETAS = 2
PESO_DISTANCIA = 2.0
PESO_FECHA = 1.5
PESO_PLAZAS = 1.0
PESO_ULTIMAS_PLAZAS = 1.5
PENALIZA_COMPLETO = -3.0
PESO_HISTORIAL = 1.0
# «Últimas plazas»: quedan 5 o menos, o una cuarta parte o menos del total.
ULTIMAS_PLAZAS_ABS = 5
ULTIMAS_PLAZAS_FRACCION = 0.25
MAX_RAZONES_MOTIVO = 3
ESTADOS_HISTORIAL = ("confirmada", "lista_espera", "asistio")

FRASE_CATEGORIA = {
    "deportiva": "el deporte",
    "cultural": "la cultura",
    "fiestas": "las fiestas",
    "gastronomia": "la buena mesa",
    "ludica": "los juegos",
    "comercio": "el comercio local",
}
NOMBRE_CATEGORIA = {
    "deportiva": "deporte",
    "cultural": "cultura",
    "fiestas": "fiestas",
    "gastronomia": "gastronomía",
    "ludica": "ocio y juegos",
    "comercio": "comercio local",
}
# Etiquetas con artículo para que la frase suene natural; el resto va entre comillas.
FRASE_ETIQUETA = {
    "senderismo": "el senderismo",
    "solidario": "lo solidario",
    "teatro": "el teatro",
    "humor": "el humor",
    "baile": "el baile",
    "flamenco": "el flamenco",
    "cine": "el cine",
    "artesania": "la artesanía",
    "patrimonio": "el patrimonio",
    "mineria": "la minería",
    "musica": "la música",
    "tapas": "las tapas",
    "navidad": "la Navidad",
    "trail": "el trail",
    "domino": "el dominó",
    "juegos de mesa": "los juegos de mesa",
    "mercado": "los mercados",
    "taller": "los talleres",
    "verbena": "las verbenas",
    "migas": "las migas",
    "comida tradicional": "la comida tradicional",
    "producto local": "el producto local",
    "visita guiada": "las visitas guiadas",
    "fiesta patronal": "las fiestas patronales",
    "fiestas patronales": "las fiestas patronales",
}


# Orden en que se leen las razones elegidas para el motivo (las elige el peso; las ordena esto).
ORDEN_RAZONES = ("gustos", "distancia", "plazas", "fecha", "historial")


@dataclass
class Razon:
    tipo: str  # uno de ORDEN_RAZONES
    peso: float
    frase: str | None  # None: cuenta para la puntuación pero no se menciona en el motivo


@dataclass
class Recomendacion:
    evento: Evento
    puntuacion: float
    motivo: str
    distancia_km: float | None
    razones: list[Razon] = field(default_factory=list)


def normalizar(texto: str) -> str:
    """«Visita_guiada» y «visita guiada», «Artesanía» y «artesania»: lo mismo."""
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return " ".join(sin_tildes.lower().replace("_", " ").replace("-", " ").split())


def _frase_etiqueta(etiqueta: str) -> str:
    return FRASE_ETIQUETA.get(normalizar(etiqueta), f"«{etiqueta.replace('_', ' ')}»")


def _te_gusta(cosa: str) -> str:
    return f"te gustan {cosa}" if cosa.startswith(("los ", "las ")) else f"te gusta {cosa}"


def _razon_gustos(usuario: Usuario, evento: Evento) -> Razon | None:
    etiquetas_evento = {normalizar(e) for e in evento.etiquetas or []}
    # En el orden del usuario: la primera es la que más le importa y la que sale en el motivo.
    coinciden = [e for e in usuario.etiquetas_interes or [] if normalizar(e) in etiquetas_evento]
    coinciden = list(dict.fromkeys(coinciden))
    categoria = evento.categoria in (usuario.gustos or [])
    peso = (PESO_CATEGORIA if categoria else 0) + PESO_ETIQUETA * min(len(coinciden), MAX_ETIQUETAS)
    if not peso:
        return None
    if coinciden:
        return Razon("gustos", peso, _te_gusta(_frase_etiqueta(coinciden[0])))
    return Razon("gustos", peso, _te_gusta(FRASE_CATEGORIA.get(evento.categoria, evento.categoria)))


def _origen(db: Session, usuario: Usuario) -> tuple[float, float] | None:
    if usuario.lat is not None and usuario.lon is not None:
        return usuario.lat, usuario.lon
    if usuario.municipio:
        municipio = db.get(Municipio, usuario.municipio)
        if municipio is not None:
            return municipio.lat, municipio.lon
    return None


def _razon_distancia(usuario: Usuario, evento: Evento, km: float | None) -> Razon | None:
    if km is None:
        return None
    radio = usuario.radio_km or RADIO_POR_DEFECTO_KM
    # Más allá del radio resta, hasta −PESO_DISTANCIA.
    peso = max(-PESO_DISTANCIA, PESO_DISTANCIA * (1 - km / radio))
    if usuario.municipio and evento.municipio == usuario.municipio:
        return Razon("distancia", peso, f"es en tu pueblo ({evento.municipio})")
    if km > radio:
        return Razon("distancia", peso, None)
    return Razon("distancia", peso, f"es en {evento.municipio} (a {max(1, round(km))} km)")


def _razon_fecha(evento: Evento, ahora: datetime) -> Razon | None:
    dias = (evento.fecha_inicio - ahora).total_seconds() / 86400
    if dias >= VENTANA_DIAS:
        return None
    peso = PESO_FECHA * (1 - max(dias, 0) / VENTANA_DIAS)
    zona = ZoneInfo(get_settings().zona_horaria)
    dias_naturales = (evento.fecha_inicio.astimezone(zona).date() - ahora.astimezone(zona).date()).days
    if dias_naturales <= 0:
        frase = "es hoy"
    elif dias_naturales == 1:
        frase = "es mañana"
    else:
        frase = f"es dentro de {dias_naturales} días"
    return Razon("fecha", peso, frase)


def _razon_plazas(evento: Evento) -> Razon | None:
    if evento.plazas_totales is None or evento.plazas_libres is None:
        return None  # sin límite de plazas: ni suma ni resta
    libres = evento.plazas_libres
    if libres <= 0:
        return Razon("plazas", PENALIZA_COMPLETO, "está completo, pero puedes apuntarte a la lista de espera")
    if libres <= ULTIMAS_PLAZAS_ABS or libres <= evento.plazas_totales * ULTIMAS_PLAZAS_FRACCION:
        frase = "queda la última plaza" if libres == 1 else f"quedan las últimas {libres} plazas"
        return Razon("plazas", PESO_ULTIMAS_PLAZAS, frase)
    return Razon("plazas", PESO_PLAZAS, f"quedan {libres} plazas")


def _razon_historial(evento: Evento, categorias_previas: set[str]) -> Razon | None:
    if evento.categoria not in categorias_previas:
        return None
    tema = NOMBRE_CATEGORIA.get(evento.categoria, evento.categoria)
    return Razon("historial", PESO_HISTORIAL, f"ya te has apuntado a otros planes de {tema}")


def componer_motivo(razones: list[Razon]) -> str:
    """Las razones positivas de más peso, en una frase: «A, B y C»."""
    positivas = [r for r in sorted(razones, key=lambda r: -r.peso) if r.frase and r.peso > 0]
    # Si está completo hay que decirlo siempre, aunque reste.
    completo = [r for r in razones if r.frase and r.peso == PENALIZA_COMPLETO]
    elegidas = positivas[: MAX_RAZONES_MOTIVO - len(completo)] + completo
    frases = [r.frase for r in sorted(elegidas, key=lambda r: ORDEN_RAZONES.index(r.tipo))]
    if not frases:
        return "Es un plan en la comarca que aún no has visto"
    texto = frases[0] if len(frases) == 1 else ", ".join(frases[:-1]) + " y " + frases[-1]
    return texto[0].upper() + texto[1:]


def recomendar(db: Session, usuario: Usuario, ahora: datetime, limite: int = 5) -> list[Recomendacion]:
    inscripciones = db.execute(
        select(Inscripcion.evento_id, Inscripcion.estado, Evento.categoria)
        .join(Evento, Evento.id == Inscripcion.evento_id)
        .where(Inscripcion.usuario_id == usuario.id)
    ).all()
    ya_apuntado = {evento_id for evento_id, estado, _ in inscripciones if estado != "cancelada"}
    categorias_previas = {categoria for _, estado, categoria in inscripciones if estado in ESTADOS_HISTORIAL}

    candidatos = db.scalars(
        select(Evento)
        .options(selectinload(Evento.publicador))
        .where(Evento.estado == "publicado", Evento.fecha_inicio >= ahora)
    ).all()
    origen = _origen(db, usuario)

    resultado = []
    for evento in candidatos:
        if evento.id in ya_apuntado:
            continue
        if usuario.publicador_id and evento.publicador_id == usuario.publicador_id:
            continue
        km = distancia_km(origen[0], origen[1], evento.lat, evento.lon) if origen else None
        razones = [
            r
            for r in (
                _razon_gustos(usuario, evento),
                _razon_distancia(usuario, evento, km),
                _razon_fecha(evento, ahora),
                _razon_plazas(evento),
                _razon_historial(evento, categorias_previas),
            )
            if r is not None
        ]
        resultado.append(
            Recomendacion(
                evento=evento,
                puntuacion=round(sum(r.peso for r in razones), 2),
                motivo=componer_motivo(razones),
                distancia_km=None if km is None else round(km, 1),
                razones=razones,
            )
        )
    resultado.sort(key=lambda r: (-r.puntuacion, r.evento.fecha_inicio, r.evento.id))
    return resultado[:limite]
