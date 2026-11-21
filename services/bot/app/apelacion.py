"""P3b: apelar un plan rechazado desde el bot (POST /eventos/{id}/apelacion, P3a).

- El aviso de rechazo («Tu evento «…» no se ha publicado. Motivo: …») lleva [✍️ Apelar] (ver `main.notify`).
- También vale escribir «apelar», «quiero recurrir» o «que lo revisen otra vez»: se buscan sus planes rechazados.
- El bot pide el motivo (10 a 500 letras) y lo manda en nombre de la persona (`usuario_id`). Solo se apela una vez.
"""

import logging
import re
import unicodedata

from app import api_cliente
from app.api_cliente import ApiNoDisponible, ErrorApi
from app.respuestas import Respuesta

log = logging.getLogger(__name__)

PREGUNTA = ("✍️ ¿Por qué crees que debería publicarse? Cuéntaselo al ayuntamiento en un mensaje (al menos 10 "
            "letras). Solo se puede apelar una vez.")
_QUIERE = r"\b(apelar|apelo|apelacion|recurrir|recurro|reclamar|reclamo)\b|\brevis(en|ar|e) (otra vez|de nuevo)\b"

_esperando: dict[str, str] = {}  # contacto -> evento_id del que espera el motivo


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def es_aviso_de_rechazo(tipo: str, texto: str) -> bool:
    return tipo == "moderacion" and "no se ha publicado" in texto


def boton(evento_id: str) -> tuple[str, str]:
    return (f"apelar:{evento_id}", "✍️ Apelar")


def quiere_apelar(texto: str) -> bool:
    return bool(texto) and len(texto) <= 120 and bool(re.search(_QUIERE, _norm(texto)))


def esperando(contacto: str) -> bool:
    return contacto in _esperando


def cancelar(contacto: str) -> None:
    _esperando.pop(contacto, None)


def empezar(contacto: str, evento_id: str | None, usuario: dict | None) -> list:
    """Con el botón llega el plan; escrito, se buscan sus planes rechazados que aún no ha apelado."""
    if evento_id:
        _esperando[contacto] = evento_id
        return [Respuesta(PREGUNTA, [("apelar_no", "❌ No apelar")])]
    if not (usuario or {}).get("id"):
        return ["No encuentro planes tuyos desde este número 🤔"]
    try:
        rechazados = [p for p in api_cliente.planes_de(usuario["id"])
                      if p.get("estado") == "rechazado" and not p.get("apelacion")]
    except (ApiNoDisponible, ErrorApi):
        return ["Ahora mismo no puedo ver tus planes. Inténtalo en un minuto 🙏"]
    if not rechazados:
        return ["No tienes planes rechazados que se puedan apelar 🙂"]
    if len(rechazados) == 1:
        return empezar(contacto, rechazados[0]["id"], usuario)
    botones = [(f"apelar:{p['id']}", (p.get("titulo") or "Plan")[:40]) for p in rechazados[:6]]
    return [Respuesta("¿Qué plan quieres que revisen otra vez?", botones + [("apelar_no", "❌ Ninguno")])]


def responder(contacto: str, texto: str, usuario: dict | None) -> list:
    """El motivo de la apelación."""
    evento_id = _esperando.get(contacto)
    if evento_id is None:
        return []
    motivo = texto.strip()
    if len(motivo) < 10:
        return [Respuesta("Cuéntame un poco más (al menos 10 letras) para que el ayuntamiento lo entienda.",
                          [("apelar_no", "❌ No apelar")])]
    if not (usuario or {}).get("id"):
        cancelar(contacto)
        return ["No encuentro tu cuenta desde este número 🤔 Apela desde la web, en «Mis planes propuestos»."]
    try:
        api_cliente.apelar(evento_id, usuario["id"], motivo[:500])
    except ApiNoDisponible:
        return ["Ahora mismo no puedo enviarlo. Vuelve a mandarme el mensaje en un minuto 🙏"]
    except ErrorApi as e:
        cancelar(contacto)
        mensajes = {
            "apelacion_usada": "Ya apelaste este plan una vez: la decisión del ayuntamiento es definitiva.",
            "estado_invalido": "Ese plan ya no está rechazado, así que no hace falta apelar 🙂",
            "prohibido": "Solo quien propuso el plan puede apelarlo.",
            "evento_no_encontrado": "No encuentro ese plan 🤔",
        }
        if e.code in mensajes:
            return [mensajes[e.code]]
        log.warning("apelacion %s: %s %s", evento_id, e.code, e.message)
        return [f"No he podido enviar la apelación: {e.message}"]
    cancelar(contacto)
    return ["Hecho ✅ He enviado tu apelación. El ayuntamiento revisará el plan otra vez y te avisaré de lo que "
            "decida."]
