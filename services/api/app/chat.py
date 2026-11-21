"""Chat (tablón) de cada evento (H3.4): teléfonos fuera, respuesta automática a preguntas y anuncios.

- Nunca sale un teléfono: se tapa al guardar y otra vez al serializar (por si hay datos antiguos).
- Respuesta a una pregunta: primero `bot /ai/responder-ficha` (la IA solo con la ficha del evento). Si el bot no
  está (o aún no tiene esa ruta), reglas simples sobre la ficha: hora, lugar, precio y plazas. Si el bot dice que
  no está en la ficha, o las reglas no saben, la pregunta queda para el organizador y se le avisa.
- Ninguna función hace commit ni lanza por culpa del bot.
"""

import logging
import re
import time

import httpx
from sqlalchemy.orm import Session

from app.config import get_settings
from app.inscripciones import fecha_corta
from app.modelos import Evento, MensajeEvento, Notificacion, Usuario
from app.moderacion import TIMEOUT_BOT_S
from app.notificaciones import notificar_moderadores, notificar_publicador
from app.serializar import evento_a_dict, fecha_iso
from app.texto import plegar

log = logging.getLogger(__name__)

TELEFONO_OCULTO = "[teléfono oculto]"
NOMBRE_ASISTENTE = "Asistente"
MAX_TEXTO = 1000  # contracts/schemas/mensaje_evento.json

# Españoles (9 cifras empezando por 6–9, con o sin +34/0034 y separadores sueltos) y cualquier E.164 con «+».
RE_TELEFONO = re.compile(
    r"(?<![\d+])(?:(?:\+|00)\s?34[\s.-]?)?[6789](?:[\s.-]?\d){8}(?!\d)"
    r"|(?<![\w+])(?:\+|00)[1-9](?:[\s.-]?\d){6,14}(?!\d)"
)

# Tras un fallo de red, un 5xx o un 404 (el bot aún sin /ai/responder-ficha) no se vuelve a llamar en este tiempo.
CIRCUITO_FICHA_S = 30.0
_circuito_ficha: dict[str, float] = {}


def ocultar_telefonos(texto: str) -> str:
    return RE_TELEFONO.sub(TELEFONO_OCULTO, texto or "")


def mensaje_a_dict(m: MensajeEvento) -> dict:
    """contracts/schemas/mensaje_evento.json. Nunca lleva teléfonos (ni campo ni dentro del texto)."""
    return {
        "id": m.id,
        "evento_id": m.evento_id,
        "autor_id": m.autor_id,
        "autor_nombre": ocultar_telefonos(m.autor_nombre) or NOMBRE_ASISTENTE,
        "autor_rol": m.autor_rol,
        "tipo": m.tipo,
        "texto": ocultar_telefonos(m.texto)[:MAX_TEXTO],
        "en_respuesta_a": m.en_respuesta_a,
        "imagen_url": m.imagen_url,
        "fijado": bool(m.fijado),
        "oculto": bool(m.oculto),
        "respondido_por_ia": bool(m.respondido_por_ia),
        "score_spam": m.score_spam,
        "creado_en": fecha_iso(m.creado_en),
    }


def autor_en_evento(usuario: Usuario, evento: Evento, organizador: bool) -> tuple[str, str]:
    """(autor_nombre, autor_rol) con que firma `usuario` en el chat de `evento`. El organizador firma con el
    nombre del publicador (como en los fixtures); fuera de sus eventos, un publicador es un vecino más."""
    if usuario.rol == "moderador":
        return usuario.nombre, "moderador"
    if organizador:
        return (evento.publicador.nombre if evento.publicador else usuario.nombre), "publicador"
    return usuario.nombre, "vecino"


# --- Respuesta automática -----------------------------------------------------------------------


def reiniciar_circuito_ficha() -> None:
    _circuito_ficha.clear()


def _abrir_circuito(bot_url: str) -> None:
    _circuito_ficha[bot_url] = time.monotonic() + CIRCUITO_FICHA_S


def _llamar_bot_ficha(evento_json: dict, pregunta: str) -> tuple[bool, str | None] | None:
    """POST {BOT_URL}/ai/responder-ficha → (puede_responder, respuesta), o None si el bot no está o responde mal."""
    ajustes = get_settings()
    if not ajustes.bot_url or _circuito_ficha.get(ajustes.bot_url, 0.0) > time.monotonic():
        return None
    try:
        r = httpx.post(
            ajustes.bot_url.rstrip("/") + "/ai/responder-ficha",
            json={"evento": evento_json, "pregunta": pregunta},
            headers={"X-Internal-Token": ajustes.internal_token},
            timeout=TIMEOUT_BOT_S,
        )
        if r.status_code >= 500 or r.status_code == 404:
            _abrir_circuito(ajustes.bot_url)
            return None
        if r.status_code != 200:
            return None
        datos = r.json()
    except httpx.TransportError as e:
        _abrir_circuito(ajustes.bot_url)
        log.info("bot /ai/responder-ficha no responde (%s); reglas durante %.0f s", type(e).__name__, CIRCUITO_FICHA_S)
        return None
    except Exception as e:  # noqa: BLE001 — cualquier fallo del bot cae a reglas
        log.info("bot /ai/responder-ficha no disponible (%s); se usan reglas", type(e).__name__)
        return None
    if not isinstance(datos, dict) or not isinstance(datos.get("puede_responder"), bool):
        return None
    respuesta = datos.get("respuesta")
    respuesta = respuesta.strip() if isinstance(respuesta, str) and respuesta.strip() else None
    return datos["puede_responder"] and respuesta is not None, respuesta


def _contiene(norm: str, claves: tuple[str, ...]) -> bool:
    return any(re.search(r"\b" + re.escape(c), norm) for c in claves)


def responder_por_reglas(evento: Evento, pregunta: str) -> str | None:
    """Respuesta sacada de la ficha para preguntas de hora, lugar, precio o plazas; None si no es ninguna
    o la ficha no tiene el dato."""
    norm = plegar(pregunta)
    partes: list[str] = []
    if _contiene(norm, ("hora", "cuando", "que dia", "empieza", "sale", "salida", "comienza", "termina", "acaba")):
        texto = f"empieza el {fecha_corta(evento.fecha_inicio)}"
        if evento.fecha_fin is not None:
            texto += f" y termina el {fecha_corta(evento.fecha_fin)}"
        partes.append(texto)
    if _contiene(norm, ("donde", "lugar", "direccion", "punto de encuentro", "se queda", "quedamos")) and evento.lugar:
        partes.append(f"es en {evento.lugar} ({evento.municipio})")
    if _contiene(norm, ("precio", "cuesta", "cuanto vale", "gratis", "gratuit", "pagar", "euros", "entrada")):
        if evento.es_gratuito or evento.precio_eur == 0:
            partes.append("es gratis")
        elif evento.precio_eur is not None:
            partes.append(f"cuesta {evento.precio_eur:g} €")
    if _contiene(norm, ("plaza", "aforo", "quedan", "hay sitio", "queda sitio", "completo", "lleno")):
        if evento.plazas_totales is None:
            partes.append("no hay límite de plazas")
        elif not evento.plazas_libres:
            partes.append("ahora mismo está completo; si te apuntas, entras en la lista de espera")
        else:
            partes.append(f"quedan {evento.plazas_libres} plazas libres")
    if not partes:
        return None
    return "Según la ficha, " + "; ".join(partes) + "."


def respuesta_automatica(evento: Evento, pregunta: str, inscritos: int = 0) -> str | None:
    """Texto de la respuesta del asistente o None si hay que dejársela al organizador."""
    # Sin la foto (puede ser una data URL de 2 MB que la IA no necesita) ni datos privados (evento_a_dict
    # sin `privados` ya no lleva `datos_ayuntamiento`).
    ficha = evento_a_dict(evento, inscritos)
    ficha.pop("imagen_url", None)
    ficha.pop("datos_ayuntamiento", None)
    resultado = _llamar_bot_ficha(ficha, pregunta)
    if resultado is not None:
        puede, respuesta = resultado
        return ocultar_telefonos(respuesta)[:MAX_TEXTO] if puede else None
    return responder_por_reglas(evento, pregunta)


def avisar_pregunta_al_organizador(db: Session, evento: Evento, pregunta: str) -> list[Notificacion]:
    """Aviso (sin enviar) al publicador del evento; si no tiene, a los moderadores."""
    corta = pregunta if len(pregunta) <= 200 else pregunta[:197] + "…"
    texto = f"Nueva pregunta en «{evento.titulo}»: «{corta}». Contesta desde el chat del evento."
    if evento.publicador is not None:
        return [notificar_publicador(db, evento.publicador, "respuesta", texto, evento.id, enviar=False)]
    return notificar_moderadores(db, "respuesta", texto, evento.id, enviar=False)


def anuncio_automatico(db: Session, evento: Evento, texto: str, autor: Usuario | None = None) -> MensajeEvento:
    """Anuncio fijado en el chat (p. ej. cambio de hora, H3.5). Firma el publicador del evento. No hace commit."""
    if evento.publicador is not None:
        nombre, rol = evento.publicador.nombre, "publicador"
    elif autor is not None and autor.rol == "moderador":
        nombre, rol = autor.nombre, "moderador"
    else:
        nombre, rol = "Organización", "publicador"
    mensaje = MensajeEvento(
        evento_id=evento.id,
        autor_id=autor.id if autor is not None else None,
        autor_nombre=nombre,
        autor_rol=rol,
        tipo="anuncio",
        texto=ocultar_telefonos(f"Aviso: {texto}")[:MAX_TEXTO],
        fijado=True,
        oculto=False,
        respondido_por_ia=False,
    )
    db.add(mensaje)
    db.flush()
    return mensaje
