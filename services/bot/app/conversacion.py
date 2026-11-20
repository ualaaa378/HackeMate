"""Conversación del publicador (bloque 1): manda un post → el bot extrae la ficha →
pregunta lo que falta → pide confirmación → la entrega a la api.
El estado vive en memoria por teléfono; basta para la demo."""

import re
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app import api_cliente, canales
from app.agentes import extractor
from app.config import get_settings
from app.schemas import MUNICIPIOS, Campo, ExtraccionEvento, MensajeEntrante

PREGUNTAS = {
    "titulo": "¿Cómo se llama la actividad?",
    "categoria": "¿De qué tipo es? (deportiva, cultural, fiestas, gastronomía, lúdica o comercio)",
    "municipio": "¿En qué pueblo es? (" + ", ".join(MUNICIPIOS) + ")",
    "fecha_inicio": "¿Qué día y a qué hora empieza? (p. ej. «30 de noviembre a las 9:00»)",
}
NOMBRES = {
    "titulo": "📌", "categoria": "🏷️", "municipio": "📍", "lugar": "🏠", "fecha_inicio": "📅",
    "precio_eur": "💶", "plazas_totales": "👥",
}
AYUDA = (
    "¡Hola! Soy el asistente de HackeMate 👋\n"
    "Si organizas algo, mándame el texto del cartel o del post y yo preparo la ficha.\n"
    "Escribe *cancelar* en cualquier momento para empezar de nuevo."
)


@dataclass
class Estado:
    borrador: ExtraccionEvento | None = None
    preguntando: str | None = None
    esperando_confirmacion: bool = False
    historial: list[str] = field(default_factory=list)


estados: dict[str, Estado] = {}


def necesita_ia(msg: MensajeEntrante) -> bool:
    """Para decidir si el webhook manda acuse inmediato («un momento…»)."""
    est = estados.get(msg.de)
    if est and (est.preguntando or est.esperando_confirmacion):
        return False
    return len(msg.texto) > 40 or bool(msg.media_url)


def procesar(msg: MensajeEntrante) -> list[str]:
    """Procesa un mensaje y envía las respuestas. Devuelve los textos enviados."""
    respuestas = _responder(msg)
    for r in respuestas:
        canales.enviar(msg.de, r)
    return respuestas


def _responder(msg: MensajeEntrante) -> list[str]:
    texto = msg.texto.strip()
    t = texto.lower()
    est = estados.setdefault(msg.de, Estado())

    if t in ("cancelar", "salir", "reset"):
        estados[msg.de] = Estado()
        return ["Vale, borrado. Cuando quieras me mandas otro evento."]

    if est.esperando_confirmacion and est.borrador:
        if re.match(r"^(s[ií]|vale|ok|confirmo|publica)", t):
            return [_entregar(msg, est)]
        if re.match(r"^no\b", t):
            estados[msg.de] = Estado()
            return ["De acuerdo, no lo publico."]
        return ["Responde *SÍ* para publicarlo o *NO* para descartarlo."]

    if est.preguntando and est.borrador:
        _rellenar(est.borrador, est.preguntando, texto)
        return _siguiente_paso(est)

    if msg.media_url and not texto:
        return ["He recibido el archivo 📎. De momento solo entiendo texto: pégame el texto del cartel o del post."]

    if len(texto) <= 40 and not re.search(r"\d", texto):
        return [AYUDA]

    extraccion = extractor.extraer(texto)
    if not extraccion.es_evento:
        return ["No veo ninguna actividad en ese mensaje 🤔\n" + AYUDA]
    est.borrador = extraccion
    est.historial.append(texto)
    return _siguiente_paso(est)


def _siguiente_paso(est: Estado) -> list[str]:
    faltan = est.borrador.faltan_obligatorios()
    if faltan:
        est.preguntando = faltan[0]
        cabecera = [] if len(est.historial) > 1 else [ficha_texto(est.borrador)]
        est.historial.append(f"pregunta:{faltan[0]}")
        return cabecera + [PREGUNTAS[faltan[0]]]
    est.preguntando = None
    est.esperando_confirmacion = True
    return [ficha_texto(est.borrador) + "\n\n¿Lo publico así? Responde *SÍ* o *NO*."]


def _rellenar(ex: ExtraccionEvento, campo: str, respuesta: str) -> None:
    valor = None
    tz = ZoneInfo(get_settings().zona_horaria)
    if campo == "fecha_inicio":
        ficha = extractor.extraer_con_reglas(respuesta, datetime.now(tz).date(), tz)
        valor = ficha.fecha_inicio
    elif campo == "municipio":
        valor = extractor.buscar_municipio(respuesta)
    elif campo == "categoria":
        norm = extractor._normalizar(respuesta)
        valor = next((c for c in extractor.PALABRAS_CATEGORIA if c[:5] in norm), None)
    else:
        valor = respuesta.strip()[:120] or None
    if valor is not None:
        ex.campos[campo] = Campo(valor=valor, confianza="alta")
        if campo in ex.faltan:
            ex.faltan.remove(campo)


def ficha_texto(ex: ExtraccionEvento) -> str:
    c = ex.campos
    lineas = ["Esto es lo que he entendido:"]
    for nombre, icono in NOMBRES.items():
        valor = c[nombre].valor
        if valor is None:
            continue
        if nombre == "fecha_inicio":
            try:
                valor = datetime.fromisoformat(valor).strftime("%d/%m/%Y %H:%M")
            except ValueError:
                pass
        if nombre == "precio_eur":
            valor = f"{valor:g} €"
        marca = " (?)" if c[nombre].confianza in ("media", "baja") else ""
        lineas.append(f"{icono} {valor}{marca}")
    if c["es_gratuito"].valor:
        lineas.append("💶 Gratis")
    return "\n".join(lineas)


def _entregar(msg: MensajeEntrante, est: Estado) -> str:
    resultado = api_cliente.importar_evento(est.borrador, telefono=msg.de)
    estados[msg.de] = Estado()
    if resultado is None:
        return "✅ Guardado. Lo enviaré a revisión en cuanto el sistema esté disponible."
    return "✅ ¡Enviado! El ayuntamiento lo revisará y te aviso cuando esté publicado."
