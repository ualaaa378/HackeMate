"""Adaptadores de salida. La lógica del bot llama a enviar() y no sabe si detrás
hay WhatsApp (Twilio) o la consola."""

import logging
import sys
from functools import lru_cache

from app.config import get_settings

log = logging.getLogger(__name__)

# Últimos mensajes enviados por la consola: los usan los tests y /dev/mensaje
bandeja_consola: list[dict] = []


def enviar(telefono: str, texto: str) -> None:
    if get_settings().canal == "twilio":
        _enviar_twilio(telefono, texto)
    else:
        bandeja_consola.append({"para": telefono, "texto": texto})
        del bandeja_consola[:-200]
        # La consola de Windows usa cp1252 y no sabe pintar emojis: mejor UTF-8 que romper
        if hasattr(sys.stdout, "reconfigure") and sys.stdout.encoding.lower() != "utf-8":
            sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        print(f"\n[bot → {telefono}]\n{texto}\n", flush=True)


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
