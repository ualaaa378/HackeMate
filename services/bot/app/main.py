import logging
from typing import Optional

from fastapi import BackgroundTasks, FastAPI, Form, Header, HTTPException, Request, Response
from pydantic import BaseModel
from xml.sax.saxutils import escape

from app import __version__, api_cliente, canales, conversacion, metrics
from app.agentes import extractor
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
    respuestas = conversacion.procesar(MensajeEntrante(canal="console", de=m.de, texto=m.texto))
    return {"respuestas": respuestas}


class PeticionExtraer(BaseModel):
    texto: str


@app.post("/ai/extraer", response_model=ExtraccionEvento)
def ai_extraer(p: PeticionExtraer, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    return extractor.extraer(p.texto)


class Notificacion(BaseModel):
    telefono: str
    tipo: str = "anuncio"
    texto: str


@app.post("/notify")
def notify(n: Notificacion, x_internal_token: str | None = Header(None)):
    _comprobar_interno(x_internal_token)
    canales.enviar(n.telefono, n.texto)
    return {"enviado": True}


@app.get("/metrics")
def ver_metricas():
    return {**metrics.resumen(), "eventos_en_cola": len(api_cliente.pendientes)}
