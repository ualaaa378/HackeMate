import asyncio
import hmac
import json
import logging
from collections import OrderedDict
from contextlib import asynccontextmanager
from typing import Literal, Optional
from xml.sax.saxutils import escape

from fastapi import BackgroundTasks, FastAPI, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

from app import (
    __version__, api_cliente, apelacion, canales, coche, conversacion, meta, metrics, radio, telegram, vecino,
)
from app.agentes import antispam, asistente, extractor, preferencias, sugerencias, voz
from app.config import get_settings
from app.llm import router
from app.schemas import ExtraccionEvento, MensajeEntrante

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
# httpx registra cada URL en INFO, y las de Telegram llevan el token del bot dentro: fuera de los logs
logging.getLogger("httpx").setLevel(logging.WARNING)
log = logging.getLogger("bot")


def registrar_webhook_telegram() -> dict | None:
    """Con PUBLIC_URL (la del túnel), el bot se da de alta él solo en Telegram al arrancar."""
    s = get_settings()
    if not (s.public_url and s.telegram_token):
        return None
    url = f"{s.public_url.rstrip('/')}/webhook/telegram"
    ok = telegram.configurar_webhook(url)
    if ok:
        log.info("Webhook de Telegram registrado en %s", url)
    else:
        log.error("No se pudo registrar el webhook de Telegram en %s", url)
    return {"url": url, "ok": bool(ok)}


async def _reintentar_cola_siempre() -> None:
    while True:
        await asyncio.sleep(get_settings().cola_reintento_s)
        if api_cliente.pendientes:
            try:
                await asyncio.to_thread(api_cliente.reintentar_pendientes)
            except Exception:
                log.exception("Fallo al reintentar la cola")


@asynccontextmanager
async def ciclo_de_vida(_app: FastAPI):
    if n := api_cliente.cargar_cola():
        log.warning("Cola recuperada del disco: %s petición(es) pendiente(s) para la api", n)
    await asyncio.to_thread(registrar_webhook_telegram)
    tarea = asyncio.create_task(_reintentar_cola_siempre())
    yield
    tarea.cancel()


app = FastAPI(title="HackeMate bot", version=__version__, lifespan=ciclo_de_vida)

ACUSE = "Recibido 👍 Dame un momento que lo leo…"


def _twiml(texto: str | None = None) -> Response:
    cuerpo = f"<Message>{escape(texto)}</Message>" if texto else ""
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{cuerpo}</Response>',
                    media_type="application/xml")


def _comprobar_interno(token: str | None) -> None:
    if not hmac.compare_digest((token or "").encode(), get_settings().internal_token.encode()):
        raise HTTPException(401, detail={"code": "token_interno_invalido", "message": "Falta X-Internal-Token"})


def _procesar_seguro(msg: MensajeEntrante) -> None:
    try:
        conversacion.procesar(msg)
    except Exception:
        log.exception("Error procesando mensaje de %s", msg.de)
        canales.enviar(msg.de, "Estamos teniendo un problema, inténtalo en un minuto 🙏")


@app.get("/health")
def health():
    return {"status": "ok", "version": __version__}


# ---------- WhatsApp Cloud API (Meta) ----------

# Meta reintenta el webhook si no contestamos rápido: recordamos los últimos ids
_vistos: OrderedDict[str, None] = OrderedDict()


def _ya_visto(id_mensaje: str | None) -> bool:
    if not id_mensaje:
        return False
    if id_mensaje in _vistos:
        return True
    _vistos[id_mensaje] = None
    while len(_vistos) > 1000:
        _vistos.popitem(last=False)
    return False


def _procesar_con_acuse(msg: MensajeEntrante) -> None:
    if conversacion.necesita_ia(msg):
        canales.enviar(msg.de, ACUSE)
    _procesar_seguro(msg)


@app.post("/webhook/telegram")
async def webhook_telegram(request: Request, tareas: BackgroundTasks):
    if not telegram.secreto_valido(request.headers.get("X-Telegram-Bot-Api-Secret-Token")):
        raise HTTPException(403, detail={"code": "secreto_telegram_invalido", "message": "Secreto no válido"})
    try:
        update = await request.json()
    except ValueError:
        raise HTTPException(400, detail={"code": "json_invalido", "message": "Cuerpo no es JSON"})
    msg, callback_id = telegram.parsear(update)
    if callback_id:
        tareas.add_task(telegram.responder_boton, callback_id)
    if msg and not _ya_visto(msg.id_mensaje):
        tareas.add_task(_procesar_con_acuse, msg)
    return {"ok": True}


@app.get("/webhook/meta")
def webhook_meta_verificar(
    modo: str = Query("", alias="hub.mode"),
    token: str = Query("", alias="hub.verify_token"),
    reto: str = Query("", alias="hub.challenge"),
):
    """Meta llama aquí una vez al configurar el webhook y espera recibir el reto tal cual."""
    s = get_settings()
    if modo == "subscribe" and s.meta_verify_token and token == s.meta_verify_token:
        return PlainTextResponse(reto)
    raise HTTPException(403, detail={"code": "verificacion_meta_fallida", "message": "verify_token incorrecto"})


@app.post("/webhook/meta")
async def webhook_meta(request: Request, tareas: BackgroundTasks):
    s = get_settings()
    cuerpo = await request.body()
    if s.meta_app_secret and not meta.firma_valida(cuerpo, request.headers.get("X-Hub-Signature-256"),
                                                   s.meta_app_secret):
        raise HTTPException(403, detail={"code": "firma_meta_invalida", "message": "Firma no válida"})
    try:
        payload = json.loads(cuerpo)
    except ValueError:
        raise HTTPException(400, detail={"code": "json_invalido", "message": "Cuerpo no es JSON"})
    for fallo in meta.fallos_de_entrega(payload):
        log.warning("WhatsApp no entregó un mensaje a %s: error %s (%s) %s",
                    fallo["para"], fallo["codigo"], fallo["motivo"], fallo["detalle"])
    for msg in meta.parsear(payload):
        if not _ya_visto(msg.id_mensaje):
            tareas.add_task(_procesar_con_acuse, msg)
    # 200 al momento: el trabajo pesado va en segundo plano
    return {"ok": True}


@app.post("/webhook/twilio")
async def webhook_twilio(
    request: Request,
    tareas: BackgroundTasks,
    From: str = Form(""),
    Body: str = Form(""),
    NumMedia: int = Form(0),
    MediaUrl0: Optional[str] = Form(None),
    MediaContentType0: Optional[str] = Form(None),
    Latitude: Optional[float] = Form(None),
    Longitude: Optional[float] = Form(None),
):
    s = get_settings()
    if s.twilio_validar_firma:
        from twilio.request_validator import RequestValidator

        form = await request.form()
        firma = request.headers.get("X-Twilio-Signature", "")
        if not RequestValidator(s.twilio_auth_token).validate(str(request.url), dict(form), firma):
            raise HTTPException(403, detail={"code": "firma_twilio_invalida", "message": "Firma no válida"})

    msg = MensajeEntrante(
        canal="whatsapp",
        de=From.removeprefix("whatsapp:"),
        texto=Body,
        media_url=MediaUrl0 if NumMedia else None,
        media_tipo=MediaContentType0 if NumMedia else None,
        lat=Latitude,
        lon=Longitude,
    )
    # Acuse inmediato en la respuesta HTTP; el trabajo pesado va en segundo plano
    acuse = ACUSE if conversacion.necesita_ia(msg) else None
    tareas.add_task(_procesar_seguro, msg)
    return _twiml(acuse)


class MensajeDev(BaseModel):
    de: str = "+34600000000"
    texto: str = ""
    boton_id: Optional[str] = None  # pulsar un botón (p. ej. «insc:<evento_id>» de un aviso)


@app.post("/dev/mensaje")
def dev_mensaje(m: MensajeDev):
    """Simulador de WhatsApp (plan C de la demo y pruebas sin Twilio)."""
    msg = MensajeEntrante(canal="console", de=m.de, texto=m.texto, boton_id=m.boton_id)
    respuestas = conversacion.procesar(msg, solo_consola=True)
    return {"respuestas": respuestas}


class PeticionExtraer(BaseModel):
    texto: str


@app.post("/ai/extraer", response_model=ExtraccionEvento)
def ai_extraer(p: PeticionExtraer, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    return extractor.extraer(p.texto)


class PeticionSpam(BaseModel):
    texto: str
    contexto: Literal["evento", "mensaje"] = "evento"
    publicador_id: Optional[str] = None


@app.post("/ai/spam", response_model=antispam.ResultadoSpam)
def ai_spam(p: PeticionSpam, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    return antispam.puntuar(p.texto, p.contexto)


class PeticionFicha(BaseModel):
    evento: dict
    pregunta: str


@app.post("/ai/responder-ficha", response_model=asistente.RespuestaFicha)
def ai_responder_ficha(p: PeticionFicha, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    return asistente.responder(p.evento, p.pregunta)


class PeticionPreferencias(BaseModel):
    texto: str


@app.post("/ai/preferencias", response_model=preferencias.Preferencias)
def ai_preferencias(p: PeticionPreferencias, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    return preferencias.interpretar(p.texto)


@app.post("/ai/sugerir-eventos", response_model=sugerencias.Sugerencias)
def ai_sugerir_eventos(p: sugerencias.PeticionSugerencias, x_internal_token: str | None = Header(None)):
    """N8: planes con mucha participación → 1-3 propuestas de planes nuevos para los administradores (N7)."""
    _comprobar_interno(x_internal_token)
    return sugerencias.sugerir(p)


class Notificacion(BaseModel):
    """contracts/schemas/notificacion.json"""

    # D1: quien solo usa Telegram no tiene teléfono; basta con uno de los dos (contacto manda si vienen ambos)
    telefono: Optional[str] = None
    contacto: Optional[str] = None  # +34… (WhatsApp) o tg:<chat_id> (Telegram); si viene, manda sobre telefono
    tipo: str = "anuncio"
    texto: str
    evento_id: Optional[str] = None
    formato: Literal["texto", "audio"] = "texto"
    botones: list[str] = []
    # Los avisos que inicia el bot (cambio de hora, recomendación) fuera de la ventana
    # de 24 h solo los acepta WhatsApp con una plantilla aprobada por Meta
    plantilla: Optional[str] = None
    parametros: list[str] = []


@app.post("/notify")
def notify(n: Notificacion, tareas: BackgroundTasks, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    destino = n.contacto or n.telefono
    if not destino:
        raise HTTPException(422, detail={"code": "sin_destino", "message": "Hace falta telefono o contacto"})
    botones = None
    if n.evento_id and n.texto.startswith(vecino.MARCA_QUE_TAL):
        # Tarea programada «¿qué tal fue?»: valoración con botones; lo que conteste va al plan como comentario
        vecino.esperar_valoracion(destino, n.evento_id)
        botones = vecino.botones_valoracion(n.evento_id)
    elif n.evento_id and coche.es_propuesta(n.texto):  # idea 6: ¿vais juntos en coche?
        botones = coche.botones(n.evento_id)
    elif n.evento_id and n.tipo == "recomendacion":
        # Recomendación → la vecina se apunta con un botón (paso 4 de la demo)
        botones = [(f"insc:{n.evento_id}", "✋ Apuntarme"), (f"info:{n.evento_id}", "ℹ️ Más info")]
    elif n.evento_id and n.tipo == "anuncio":
        # Recordatorio o anuncio de un plan al que ya está apuntado: [Apuntarme] no pinta nada
        botones = [(f"info:{n.evento_id}", "ℹ️ Ver el plan")]
    elif n.evento_id and apelacion.es_aviso_de_rechazo(n.tipo, n.texto):
        botones = [apelacion.boton(n.evento_id)]  # P3b
    elif n.botones:
        botones = [(b, b) for b in n.botones[:3]]
    if n.plantilla:
        canales.enviar_plantilla(destino, n.plantilla, n.parametros, texto_alternativo=n.texto)
    else:
        canales.enviar(destino, n.texto, botones)
    if radio.es_resumen(n.texto) and not n.plantilla:  # «La radio del pueblo»: el resumen del lunes, también en voz
        tareas.add_task(radio.emitir, destino, n.texto)
    elif n.formato == "audio":  # personas mayores: el aviso también en nota de voz
        ogg = voz.sintetizar(voz.texto_para_voz([n.texto]))
        if ogg:
            canales.enviar_voz(destino, ogg)
    return {"enviado": True}


class CaidaSimulada(BaseModel):
    activa: bool


@app.get("/admin/simular-caida")
def ver_caida(x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    return {"activa": router.caida_simulada()}


@app.post("/admin/simular-caida")
def simular_caida(c: CaidaSimulada, x_internal_token: str | None = Header(None)):
    """Demo de robustez: con la caída activa, todas las IAs «fallan» y el bot sigue con reglas."""
    _comprobar_interno(x_internal_token)
    router.forzar_caida(c.activa)
    log.warning("Caída simulada de la IA: %s", "ACTIVADA" if c.activa else "desactivada")
    return {"activa": router.caida_simulada()}


@app.get("/metrics")
def ver_metricas():
    return {**metrics.resumen(), "eventos_en_cola": len(api_cliente.pendientes),
            "caida_simulada": router.caida_simulada()}


class UrlPublica(BaseModel):
    public_url: Optional[str] = None
    web_url: Optional[str] = None  # enlaces a las fichas que manda el bot ({web_url}/evento/{id})


@app.post("/admin/webhook-telegram")
def webhook_telegram_admin(u: UrlPublica, x_internal_token: str | None = Header(None)):
    """Si cambia la URL del túnel: se vuelve a registrar el webhook y se cambian los enlaces SIN reiniciar el bot,
    para no perder las conversaciones a medias que guarda en memoria (scripts/url_publica.py lo llama)."""
    _comprobar_interno(x_internal_token)
    s = get_settings()
    if u.web_url:
        s.web_url = u.web_url
    if u.public_url:
        s.public_url = u.public_url
    if not (s.public_url and s.telegram_token):
        if u.web_url and not u.public_url:  # solo los enlaces (máquina sin Telegram)
            return {"url": None, "ok": True, "web_url": s.web_url}
        raise HTTPException(422, detail={"code": "falta_configuracion",
                                         "message": "Hace falta TELEGRAM_TOKEN y una public_url"})
    return {**registrar_webhook_telegram(), "web_url": s.web_url}


@app.post("/admin/reintentar-cola")
def reintentar_cola(x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    enviados = api_cliente.reintentar_pendientes()
    return {"enviados": enviados, "quedan": len(api_cliente.pendientes)}
