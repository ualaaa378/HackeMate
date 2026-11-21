"""Consentimiento para los avisos de planes nuevos y recomendaciones (decisión D1, tarea B7).

Solo se avisa a quien lo acepta: el bot lo pregunta después de que diga sus gustos y entiende «no quiero avisos» y
«avísame» en cualquier momento. Lo guarda en la API (`acepta_avisos` del usuario, PATCH /usuarios/{id}); quien manda
los avisos y filtra por ese campo es la API."""

import logging
import re
import unicodedata

from app import api_cliente, telegram
from app.api_cliente import ApiNoDisponible, ErrorApi
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante

log = logging.getLogger(__name__)

PREGUNTA = ("🔔 ¿Quieres que te avise por aquí cuando haya planes nuevos que te puedan gustar? Te escribiré solo "
            "con lo que encaje con tus gustos y lo que haces. Puedes cambiarlo cuando quieras.")
BOTONES = [("avisos:si", "🔔 Sí, avísame"), ("avisos:no", "No, gracias")]
_NO = re.compile(r"\b(no quiero (mas |recibir )?avisos|no me avises|deja de avisarme|no me mandes (mas )?avisos|"
                 r"quitame (de )?los avisos|desactiva(r)? (los )?avisos|baja de los avisos)\b")
_SI = re.compile(r"\b(avisame|quiero (recibir )?avisos|activa(r)? (los )?avisos|si,? avisame|mandame avisos)\b")
_SI_CORTO = re.compile(r"^(si|sí|vale|ok|claro|venga|por favor)\b")
_NO_CORTO = re.compile(r"^(no|no gracias|nah)\b")

preguntado: set[str] = set()  # ya se le preguntó en esta sesión del bot: no insistir
esperando_respuesta: set[str] = set()  # acaba de ver la pregunta: un «sí» o «no» suelto es la respuesta
pendiente_numero: dict[str, bool] = {}  # Telegram sin vincular: se guarda al compartir el número


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn").strip()


def que_quiere(msg: MensajeEntrante, texto: str) -> bool | None:
    """True/False si este mensaje dice que quiere (o no) avisos; None si no habla de eso."""
    boton = msg.boton_id or ""
    if boton.startswith("avisos:"):
        return boton == "avisos:si"
    t = _normalizar(texto)
    if _NO.search(t):
        return False
    if _SI.search(t):
        return True
    if msg.de in esperando_respuesta and len(t) <= 20:
        if _NO_CORTO.match(t):
            return False
        if _SI_CORTO.match(t):
            return True
    return None


def pregunta_si_toca(msg: MensajeEntrante, usuario: dict | None) -> list:
    """Tras decir sus gustos: la pregunta, una vez por sesión. Se pregunta aunque la API diga `acepta_avisos`:
    hoy vale true por defecto (A8), así que no prueba que la persona lo haya aceptado."""
    if msg.de in preguntado:
        return []
    preguntado.add(msg.de)
    esperando_respuesta.add(msg.de)
    return [Respuesta(PREGUNTA, BOTONES)]


def responder(msg: MensajeEntrante, acepta: bool, usuario: dict | None) -> list:
    esperando_respuesta.discard(msg.de)
    preguntado.add(msg.de)
    if not (usuario or {}).get("id"):
        if telegram.es_telegram(msg.de):
            pendiente_numero[msg.de] = acepta
            return [Respuesta("Para guardarlo necesito saber quién eres: pulsa *Compartir mi número* aquí abajo 📱",
                              pedir_contacto=True)]
        return ["Ahora mismo no puedo guardarlo 🙏 Inténtalo en un rato."]
    return [_guardar(usuario["id"], acepta)]


def tras_vincular(msg: MensajeEntrante, usuario: dict | None) -> list:
    if msg.de not in pendiente_numero or not (usuario or {}).get("id"):
        return []
    return [_guardar(usuario["id"], pendiente_numero.pop(msg.de))]


def _guardar(usuario_id: str, acepta: bool) -> str:
    try:
        guardado = api_cliente.guardar_preferencias(usuario_id, {"acepta_avisos": acepta})
    except (ApiNoDisponible, ErrorApi) as e:
        log.warning("No se pudo guardar acepta_avisos: %s", e)
        guardado = False
    if not guardado:
        return "Ahora mismo no puedo guardarlo 🙏 Dímelo otra vez en un rato («avísame» o «no quiero avisos»)."
    if acepta:
        return ("¡Hecho! 🔔 Te avisaré de los planes nuevos que encajen contigo. Si un día no quieres más, "
                "escríbeme «no quiero avisos».")
    return "Entendido, no te mandaré avisos de planes nuevos 👍 Si cambias de idea, escríbeme «avísame»."
