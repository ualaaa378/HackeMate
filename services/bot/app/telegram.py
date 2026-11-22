"""Canal de Telegram (Bot API): gratis, sin límite de mensajes y sin verificar negocio.
Los usuarios se identifican como «tg:<chat_id>» porque Telegram no da el teléfono."""

import hashlib
import hmac
import html
import logging
import re

import httpx

from app.config import get_settings
from app.schemas import MensajeEntrante

log = logging.getLogger(__name__)

PREFIJO = "tg:"
# /start <parámetro> del enlace de la web → lo que el bot entiende como primer mensaje
START = {"codigo": "/codigo", "alta": "quiero dar de alta mi asociación"}


def es_telegram(destino: str) -> bool:
    return destino.startswith(PREFIJO)


def _api(metodo: str) -> str:
    return f"https://api.telegram.org/bot{get_settings().telegram_token}/{metodo}"


def _llamar(metodo: str, cuerpo: dict) -> dict | None:
    try:
        r = httpx.post(_api(metodo), json=cuerpo, timeout=10)
        datos = r.json()
        if not datos.get("ok"):
            log.error("Telegram %s falló: %s", metodo, datos.get("description"))
            return None
        return datos.get("result")
    except (httpx.HTTPError, ValueError) as e:
        log.error("No se pudo contactar con Telegram (%s): %s", metodo, e)
        return None


def a_html(texto: str) -> str:
    """El bot escribe *negrita* al estilo WhatsApp; Telegram la quiere en HTML."""
    return re.sub(r"\*([^*\n]+)\*", r"<b>\1</b>", html.escape(texto, quote=False))


# ---------- Salida ----------

BOTON_COMPARTIR = "📱 Compartir mi número"


def enviar(destino: str, texto: str, botones: list[tuple[str, str]] | None = None,
           pedir_contacto: bool = False, quitar_teclado: bool = False, pedir_ubicacion: bool = False) -> None:
    cuerpo = {"chat_id": destino.removeprefix(PREFIJO), "text": a_html(texto)[:4096], "parse_mode": "HTML"}
    if botones:
        # Un botón por fila: más grandes y fáciles de pulsar para personas mayores
        cuerpo["reply_markup"] = {"inline_keyboard": [[{"text": t, "callback_data": i[:64]}] for i, t in botones]}
    elif pedir_contacto:
        # Telegram solo da el teléfono si el usuario pulsa este botón: así lo casamos con la API
        # is_persistent: que no se esconda detrás del icono del teclado
        cuerpo["reply_markup"] = {"keyboard": [[{"text": BOTON_COMPARTIR, "request_contact": True}]],
                                  "resize_keyboard": True, "one_time_keyboard": True, "is_persistent": True}
    elif pedir_ubicacion:
        cuerpo["reply_markup"] = {"keyboard": [[{"text": "📍 Enviar mi ubicación", "request_location": True}]],
                                  "resize_keyboard": True, "one_time_keyboard": True, "is_persistent": True}
    elif quitar_teclado:
        cuerpo["reply_markup"] = {"remove_keyboard": True}
    _llamar("sendMessage", cuerpo)


def enviar_voz(destino: str, ogg: bytes) -> bool:
    """Nota de voz (OGG/Opus). Telegram la muestra como un audio que se escucha con un toque."""
    try:
        r = httpx.post(_api("sendVoice"), data={"chat_id": destino.removeprefix(PREFIJO)},
                       files={"voice": ("respuesta.ogg", ogg, "audio/ogg")}, timeout=30)
        datos = r.json()
    except (httpx.HTTPError, ValueError) as e:
        log.error("No se pudo enviar la nota de voz: %s", e)
        return False
    if not datos.get("ok"):
        log.error("Telegram sendVoice falló: %s", datos.get("description"))
    return bool(datos.get("ok"))


def normalizar_telefono(numero: str) -> str:
    """Telegram manda el número sin «+» (34600…). La API lo quiere en E.164."""
    digitos = "".join(c for c in numero if c.isdigit())
    return f"+{digitos}"


def responder_boton(callback_id: str) -> None:
    """Quita el relojito del botón pulsado en la app de Telegram."""
    _llamar("answerCallbackQuery", {"callback_query_id": callback_id})


def descargar_archivo(file_id: str) -> bytes | None:
    """Notas de voz y fotos llegan como file_id: se pide la ruta y se descarga."""
    info = _llamar("getFile", {"file_id": file_id})
    if not info or "file_path" not in info:
        return None
    try:
        r = httpx.get(f"https://api.telegram.org/file/bot{get_settings().telegram_token}/{info['file_path']}",
                      timeout=30)
        r.raise_for_status()
        return r.content
    except httpx.HTTPError as e:
        log.error("No se pudo descargar el archivo %s: %s", file_id, e)
        return None


def secreto_webhook() -> str:
    """Secreto de la cabecera X-Telegram-Bot-Api-Secret-Token. TELEGRAM_SECRET si está; si no, uno derivado del
    TELEGRAM_TOKEN: así el webhook público nunca acepta mensajes falsos (alguien que se haga pasar por el moderador
    con su telegram_id). Vacío solo sin TELEGRAM_TOKEN (sin Telegram no hay nada que proteger)."""
    s = get_settings()
    if s.telegram_secret:
        return s.telegram_secret
    if not s.telegram_token:
        return ""
    return hmac.new(s.telegram_token.encode(), b"hackemate-webhook", hashlib.sha256).hexdigest()


def secreto_valido(recibido: str | None) -> bool:
    esperado = secreto_webhook()
    return not esperado or hmac.compare_digest((recibido or "").encode(), esperado.encode())


def configurar_webhook(url: str) -> dict | None:
    return _llamar("setWebhook", {
        "url": url,
        "secret_token": secreto_webhook(),
        "allowed_updates": ["message", "callback_query"],
        # False: lo que escriban mientras el bot se reinicia llega igual al volver
        "drop_pending_updates": False,
    })


# ---------- Entrada ----------

def parsear(update: dict) -> tuple[MensajeEntrante | None, str | None]:
    """Devuelve el mensaje normalizado y, si era un botón, el id del callback a contestar."""
    if cb := update.get("callback_query"):
        chat = (cb.get("message") or {}).get("chat", {}).get("id") or cb.get("from", {}).get("id")
        return MensajeEntrante(
            canal="telegram", de=f"{PREFIJO}{chat}", nombre=cb.get("from", {}).get("first_name"),
            id_mensaje=f"cb{cb.get('id')}", texto="", boton_id=cb.get("data"),
        ), cb.get("id")

    m = update.get("message")
    if not m:
        return None, None
    base = {
        "canal": "telegram",
        "de": f"{PREFIJO}{m['chat']['id']}",
        "nombre": m.get("from", {}).get("first_name"),
        "id_mensaje": f"m{update.get('update_id')}",
    }
    if "text" in m:
        texto = m["text"]
        if texto.startswith("/start"):
            # Enlaces t.me/HackeMate_bot?start=<x> desde la web: «codigo» (D2, entrar con código) o «alta» (B5)
            texto = START.get(texto.split(maxsplit=1)[1].strip() if " " in texto else "", "hola")
        return MensajeEntrante(**base, texto=texto), None
    if voz := (m.get("voice") or m.get("audio")):
        return MensajeEntrante(**base, texto=m.get("caption", ""), media_id=voz["file_id"],
                               media_tipo=voz.get("mime_type", "audio/ogg")), None
    if fotos := m.get("photo"):
        mayor = max(fotos, key=lambda f: f.get("file_size", 0))  # Telegram manda varios tamaños
        return MensajeEntrante(**base, texto=m.get("caption", ""), media_id=mayor["file_id"],
                               media_tipo="image/jpeg"), None
    if loc := m.get("location"):
        return MensajeEntrante(**base, lat=loc["latitude"], lon=loc["longitude"]), None
    if contacto := m.get("contact"):
        # Solo vale su propio número, no el de otra persona reenviado
        if contacto.get("user_id") == m.get("from", {}).get("id") and contacto.get("phone_number"):
            return MensajeEntrante(**base, telefono_compartido=normalizar_telefono(contacto["phone_number"])), None
        return MensajeEntrante(**base, texto=""), None
    return None, None
