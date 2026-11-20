"""Entrada de WhatsApp Cloud API (Meta): firma del webhook y paso del JSON de Meta a
MensajeEntrante. Referencia del payload: «Webhooks > messages» en la doc de WhatsApp."""

import hashlib
import hmac

from app.schemas import MensajeEntrante


def firma_valida(cuerpo: bytes, cabecera: str | None, app_secret: str) -> bool:
    """Meta firma cada POST con HMAC-SHA256 del cuerpo usando el App Secret."""
    if not cabecera or not cabecera.startswith("sha256="):
        return False
    esperada = hmac.new(app_secret.encode(), cuerpo, hashlib.sha256).hexdigest()
    return hmac.compare_digest(esperada, cabecera.removeprefix("sha256="))


def parsear(payload: dict) -> list[MensajeEntrante]:
    mensajes: list[MensajeEntrante] = []
    for entrada in payload.get("entry", []):
        for cambio in entrada.get("changes", []):
            valor = cambio.get("value", {})
            # Los avisos de estado (enviado, entregado, leído) llegan en "statuses": se ignoran
            nombres = {c.get("wa_id"): c.get("profile", {}).get("name") for c in valor.get("contacts", [])}
            for m in valor.get("messages", []):
                mensaje = _convertir(m, nombres.get(m.get("from")))
                if mensaje:
                    mensajes.append(mensaje)
    return mensajes


def _convertir(m: dict, nombre: str | None) -> MensajeEntrante | None:
    tipo = m.get("type")
    base = {"canal": "whatsapp", "de": "+" + m.get("from", ""), "nombre": nombre, "id_mensaje": m.get("id")}

    if tipo == "text":
        return MensajeEntrante(**base, texto=m["text"].get("body", ""))
    if tipo == "interactive":
        i = m.get("interactive", {})
        r = i.get("button_reply") or i.get("list_reply") or {}
        return MensajeEntrante(**base, texto=r.get("title", ""), boton_id=r.get("id"))
    if tipo == "button":  # botón de respuesta rápida de una plantilla
        b = m.get("button", {})
        return MensajeEntrante(**base, texto=b.get("text", ""), boton_id=b.get("payload"))
    if tipo in ("image", "audio", "voice", "video", "document", "sticker"):
        media = m.get(tipo, {})
        return MensajeEntrante(**base, texto=media.get("caption", ""), media_id=media.get("id"),
                               media_tipo=media.get("mime_type"))
    if tipo == "location":
        loc = m.get("location", {})
        return MensajeEntrante(**base, lat=loc.get("latitude"), lon=loc.get("longitude"),
                               texto=loc.get("name") or loc.get("address") or "")
    return None  # reacciones, contactos, etc.: de momento no los usamos
