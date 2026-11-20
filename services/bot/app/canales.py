"""Adaptadores de salida. La lógica del bot llama a enviar() / enviar_plantilla() y
no sabe si detrás está WhatsApp Cloud API (Meta), Twilio o la consola."""

import logging
import sys
from functools import lru_cache

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

# Últimos mensajes enviados por la consola: los usan los tests y /dev/mensaje
bandeja_consola: list[dict] = []

Boton = tuple[str, str]  # (id que nos devuelve WhatsApp al pulsarlo, texto visible)


def enviar(telefono: str, texto: str, botones: list[Boton] | None = None) -> None:
    """Mensaje de sesión: respuesta a alguien que nos ha escrito en las últimas 24 h."""
    from app import telegram

    canal = get_settings().canal
    if telegram.es_telegram(telefono) and get_settings().telegram_token:
        telegram.enviar(telefono, texto, botones)
    elif canal == "meta":
        _enviar_meta(telefono, texto, botones)
    elif canal == "twilio":
        _enviar_twilio(telefono, texto)
    else:
        _enviar_consola(telefono, texto, botones)


def enviar_plantilla(telefono: str, plantilla: str, parametros: list[str], texto_alternativo: str) -> None:
    """Mensaje que inicia el bot (avisos). WhatsApp solo lo permite fuera de la ventana
    de 24 h con una plantilla aprobada por Meta. En los otros canales se manda el texto."""
    from app import telegram

    # Telegram no tiene ventana de 24 h ni plantillas: el aviso va como texto normal
    if get_settings().canal == "meta" and not telegram.es_telegram(telefono):
        _enviar_plantilla_meta(telefono, plantilla, parametros)
    else:
        enviar(telefono, texto_alternativo)


# ---------- Consola ----------

def _enviar_consola(telefono: str, texto: str, botones: list[Boton] | None) -> None:
    bandeja_consola.append({"para": telefono, "texto": texto, "botones": botones or []})
    del bandeja_consola[:-200]
    # La consola de Windows usa cp1252 y no sabe pintar emojis: mejor UTF-8 que romper
    if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding.lower() != "utf-8":
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    extra = "\n" + "  ".join(f"[{t}]" for _, t in botones) if botones else ""
    print(f"\n[bot → {telefono}]\n{texto}{extra}\n", flush=True)


# ---------- WhatsApp Cloud API (Meta) ----------

def _url_meta(ruta: str) -> str:
    s = get_settings()
    return f"https://graph.facebook.com/{s.meta_graph_version}/{ruta}"


def _post_meta(cuerpo: dict) -> None:
    s = get_settings()
    cuerpo = {"messaging_product": "whatsapp", "recipient_type": "individual", **cuerpo}
    try:
        r = httpx.post(_url_meta(f"{s.meta_phone_number_id}/messages"), json=cuerpo,
                       headers={"Authorization": f"Bearer {s.meta_token}"}, timeout=10)
        r.raise_for_status()
    except httpx.HTTPStatusError as e:
        log.error("Meta rechazó el mensaje a %s: %s %s", cuerpo.get("to"), e.response.status_code, e.response.text)
    except httpx.HTTPError as e:
        log.error("No se pudo contactar con Meta: %s", e)


def _destino(telefono: str) -> str:
    return telefono.lstrip("+")  # Meta usa el número sin «+»


def _enviar_meta(telefono: str, texto: str, botones: list[Boton] | None) -> None:
    if botones:
        # Mensaje interactivo: máximo 3 botones de 20 caracteres y cuerpo de 1024
        cuerpo = {
            "to": _destino(telefono),
            "type": "interactive",
            "interactive": {
                "type": "button",
                "body": {"text": texto[:1024]},
                "action": {"buttons": [
                    {"type": "reply", "reply": {"id": i[:256], "title": t[:20]}} for i, t in botones[:3]
                ]},
            },
        }
    else:
        cuerpo = {"to": _destino(telefono), "type": "text", "text": {"body": texto[:4096], "preview_url": False}}
    _post_meta(cuerpo)


def _enviar_plantilla_meta(telefono: str, plantilla: str, parametros: list[str]) -> None:
    s = get_settings()
    componentes = []
    if parametros:
        componentes.append({"type": "body", "parameters": [{"type": "text", "text": p} for p in parametros]})
    _post_meta({
        "to": _destino(telefono),
        "type": "template",
        "template": {"name": plantilla, "language": {"code": s.meta_idioma_plantillas}, "components": componentes},
    })


def descargar_media_meta(media_id: str) -> tuple[bytes, str] | None:
    """Audios e imágenes llegan como un id: hay que pedir la URL y descargarla con el token."""
    s = get_settings()
    cabeceras = {"Authorization": f"Bearer {s.meta_token}"}
    try:
        info = httpx.get(_url_meta(media_id), headers=cabeceras, timeout=10)
        info.raise_for_status()
        datos = info.json()
        fichero = httpx.get(datos["url"], headers=cabeceras, timeout=30)
        fichero.raise_for_status()
        return fichero.content, datos.get("mime_type", "")
    except (httpx.HTTPError, KeyError) as e:
        log.error("No se pudo descargar el media %s: %s", media_id, e)
        return None


# ---------- Twilio (alternativa) ----------

@lru_cache
def _cliente_twilio():
    from twilio.rest import Client

    s = get_settings()
    return Client(s.twilio_account_sid, s.twilio_auth_token)


def _enviar_twilio(telefono: str, texto: str) -> None:
    from twilio.base.exceptions import TwilioRestException

    s = get_settings()
    try:
        _cliente_twilio().messages.create(from_=s.twilio_whatsapp_from, to=f"whatsapp:{telefono}", body=texto[:1600])
    except TwilioRestException as e:
        log.error("Twilio no pudo enviar a %s: %s", telefono, e)
