import logging
from typing import Literal, Optional

import json
from collections import OrderedDict

from fastapi import BackgroundTasks, FastAPI, Form, Header, HTTPException, Query, Request, Response
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel
from xml.sax.saxutils import escape

from app import __version__, api_cliente, canales, conversacion, meta, metrics, telegram
from app.agentes import antispam, asistente, extractor, preferencias, voz
from app.llm import router
from app.config import get_settings
from app.schemas import ExtraccionEvento, MensajeEntrante

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("bot")

app = FastAPI(title="HackeMate bot", version=__version__)

ACUSE = "Recibido 👍 Dame un momento que lo leo…"


def _twiml(texto: str | None = None) -> Response:
    cuerpo = f"<Message>{escape(texto)}</Message>" if texto else ""
    return Response(f'<?xml version="1.0" encoding="UTF-8"?><Response>{cuerpo}</Response>',
                    media_type="application/xml")


def _comprobar_interno(token: str | None) -> None:
    if token != get_settings().internal_token:
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
    s = get_settings()
    if s.telegram_secret and request.headers.get("X-Telegram-Bot-Api-Secret-Token") != s.telegram_secret:
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
    texto: str


@app.post("/dev/mensaje")
def dev_mensaje(m: MensajeDev):
    """Simulador de WhatsApp (plan C de la demo y pruebas sin Twilio)."""
    respuestas = conversacion.procesar(MensajeEntrante(canal="console", de=m.de, texto=m.texto), solo_consola=True)
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


class Notificacion(BaseModel):
    """contracts/schemas/notificacion.json"""

    telefono: str
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
def notify(n: Notificacion, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    destino = n.contacto or n.telefono
    botones = None
    if n.evento_id and n.tipo in ("recomendacion", "anuncio"):
        # Recomendación → la vecina se apunta con un botón (paso 4 de la demo)
        botones = [(f"insc:{n.evento_id}", "✋ Apuntarme"), (f"info:{n.evento_id}", "ℹ️ Más info")]
    elif n.botones:
        botones = [(b, b) for b in n.botones[:3]]
    if n.plantilla:
        canales.enviar_plantilla(destino, n.plantilla, n.parametros, texto_alternativo=n.texto)
    else:
        canales.enviar(destino, n.texto, botones)
    if n.formato == "audio":  # personas mayores: el aviso también en nota de voz
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
