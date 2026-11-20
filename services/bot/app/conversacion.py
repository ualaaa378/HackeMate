"""Conversaciones del bot. El estado vive en memoria por contacto (+34… o tg:…); basta para la demo.

Publicador (contrato: importar → completar → confirmar):
  post, cartel o nota de voz → la IA extrae la ficha → POST /eventos/importar (pendiente_confirmacion)
  → el bot pregunta lo que falta → botones [Sí, publicar] [No] → POST /eventos/{id}/confirmar.
  La API decide si queda publicado o en revisión; el bot solo lo cuenta.
Moderador: «pendientes» → bandeja con motivo y botones [Aprobar] [Rechazar].
Vecino (app/vecino.py): «¿qué hay este finde?», «me gustan las rutas», [Apuntarme], preguntas sobre un evento.
Telegram: «Compartir mi número» → POST /usuarios/vincular, para que la API sepa quién es."""

import logging
import re
import time
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app import api_cliente, canales, telegram, vecino
from app.agentes import extractor, intencion, medios
from app.api_cliente import ApiNoDisponible, ErrorApi
from app.config import get_settings
from app.respuestas import Respuesta
from app.schemas import CAMPOS_OBLIGATORIOS, MUNICIPIOS, Campo, ExtraccionEvento, MensajeEntrante

log = logging.getLogger(__name__)

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
    "🔎 ¿Buscas planes? Pregúntame «¿qué hay este finde?» o «¿qué hay en Senés?». También vale una nota de voz.\n"
    "❤️ Dime qué te gusta («me gustan las rutas») y te aviso cuando haya algo.\n"
    "📣 ¿Organizas algo? Mándame el texto, *una foto del cartel* o *una nota de voz* y preparo la ficha.\n"
    "Escribe *cancelar* en cualquier momento para empezar de nuevo."
)
AYUDA_MODERADOR = "Eres moderador/a: escribe *pendientes* para ver lo que espera revisión."
PEDIR_TELEFONO = ("Para saber quién eres (y si publicas por una asociación, bar o ayuntamiento), "
                  "pulsa el botón *Compartir mi número* de abajo.")
COMANDOS_MODERACION = ("pendientes", "moderar", "moderacion", "moderación", "revisar", "bandeja")

BOTONES_CONFIRMAR = [("si", "Sí, publicar"), ("no", "No")]


@dataclass
class Estado:
    borrador: ExtraccionEvento | None = None
    evento_id: str | None = None  # id en la api tras importar (None si la api no estaba)
    campos_corregidos: dict = field(default_factory=dict)  # lo que el publicador completa, para /confirmar
    preguntando: str | None = None
    esperando_confirmacion: bool = False
    primera_pregunta: bool = True


estados: dict[str, Estado] = {}
_usuarios: dict[str, tuple[float, dict | None]] = {}  # caché de by-contacto (60 s)


def necesita_ia(msg: MensajeEntrante) -> bool:
    """Para decidir si el webhook manda acuse inmediato («un momento…»)."""
    est = estados.get(msg.de)
    if est and (est.preguntando or est.esperando_confirmacion):
        return False
    return len(msg.texto) > 40 or bool(msg.media_url or msg.media_id)


def procesar(msg: MensajeEntrante, solo_consola: bool = False) -> list[str]:
    """Procesa un mensaje y envía las respuestas. Devuelve los textos enviados.
    solo_consola: el simulador (/dev/mensaje) nunca debe escribir a un canal real."""
    respuestas = [r if isinstance(r, Respuesta) else Respuesta(r) for r in _responder(msg)]
    for r in respuestas:
        if solo_consola:
            canales.enviar_consola(msg.de, r.texto, r.botones, r.pedir_contacto)
        else:
            canales.enviar(msg.de, r.texto, r.botones, pedir_contacto=r.pedir_contacto,
                           quitar_teclado=r.quitar_teclado, pedir_ubicacion=r.pedir_ubicacion)
    return [r.texto for r in respuestas]


def _canal(msg: MensajeEntrante) -> str:
    return msg.canal if msg.canal != "console" else "manual"


def _usuario(contacto: str) -> dict | None:
    cacheado = _usuarios.get(contacto)
    if cacheado and time.monotonic() - cacheado[0] < 60:
        return cacheado[1]
    try:
        usuario = api_cliente.usuario_por_contacto(contacto)
    except (ApiNoDisponible, ErrorApi):
        return None
    _usuarios[contacto] = (time.monotonic(), usuario)
    return usuario


def _responder(msg: MensajeEntrante) -> list[str | Respuesta]:
    texto = msg.texto.strip()
    # Si pulsó un botón, usamos su id (p. ej. "si"): no depende de tildes ni mayúsculas
    t = (msg.boton_id or texto).lower()
    est = estados.setdefault(msg.de, Estado())

    if msg.telefono_compartido:
        return _vincular(msg)

    if t in ("cancelar", "salir", "reset"):
        estados[msg.de] = Estado()
        return ["Vale, borrado. Cuando quieras me mandas otro evento."]

    if t.startswith("mod:"):
        return _decidir(msg, t)
    if t.startswith("insc:"):
        return vecino.inscribir(msg, msg.boton_id.split(":", 1)[1], _usuario(msg.de))
    if t.startswith("info:"):
        return vecino.info(msg, msg.boton_id.split(":", 1)[1])
    if msg.lat is not None and msg.lon is not None and not texto:
        return vecino.ubicacion_recibida(msg, _usuario(msg.de))

    if est.esperando_confirmacion and est.borrador:
        if re.match(r"^(s[ií]|vale|ok|confirmo|publica)", t):
            return [_entregar(msg, est)]
        if re.match(r"^no\b", t):
            estados[msg.de] = Estado()
            return ["De acuerdo, no lo publico."]
        return [Respuesta("Responde *SÍ* para publicarlo o *NO* para descartarlo.", BOTONES_CONFIRMAR)]

    if est.preguntando and est.borrador:
        _rellenar(est, est.preguntando, texto)
        return _siguiente_paso(est)

    eco: list[str | Respuesta] = []
    es_cartel = (msg.media_tipo or "").startswith("image")
    if msg.media_url or msg.media_id:
        leido = _leer_medio(msg)
        if leido is None:
            tipo = "la nota de voz" if (msg.media_tipo or "").startswith("audio") else "el archivo"
            return [f"No he podido entender {tipo} 😕 ¿Me lo escribes con tus palabras?"]
        eco.append(f"{'🎙️ He entendido' if (msg.media_tipo or '').startswith('audio') else '🖼️ En el cartel pone'}:"
                   f"\n«{leido[:600]}»")
        texto = f"{texto}\n{leido}".strip()
        t = texto.lower()

    if t in COMANDOS_MODERACION:
        return _bandeja(msg)

    # Un cartel siempre es para publicar; texto y notas de voz pueden ser de un vecino que busca planes
    if not es_cartel:
        tipo = intencion.detectar(texto, vecino.mirando_evento(msg.de)).tipo
        if tipo == "buscar":
            return eco + vecino.buscar(msg, texto, _usuario(msg.de))
        if tipo == "gustos":
            return eco + vecino.gustos(msg, texto, _usuario(msg.de))
        if tipo == "inscribir":
            return eco + vecino.inscribir(msg, None, _usuario(msg.de))
        if tipo == "pregunta_evento":
            return eco + vecino.pregunta(msg, texto, _usuario(msg.de))

    if len(texto) <= 40 and not re.search(r"\d", texto):
        return _saludo(msg)

    extraccion = extractor.extraer(texto)
    if not extraccion.es_evento:
        return eco + ["No veo ninguna actividad en ese mensaje 🤔\n" + AYUDA]
    est.borrador = extraccion
    aviso = _importar(msg, est)
    if aviso is not None:
        return eco + [aviso]
    return eco + _siguiente_paso(est)


# ---------- Publicador ----------

def _leer_medio(msg: MensajeEntrante) -> str | None:
    tipo = msg.media_tipo or ""
    if msg.media_id and msg.canal == "telegram":
        datos = telegram.descargar_archivo(msg.media_id)
    elif msg.media_id and msg.canal == "whatsapp":
        bajado = canales.descargar_media_meta(msg.media_id)
        datos = bajado[0] if bajado else None
        tipo = tipo or (bajado[1] if bajado else "")
    else:
        datos = None  # Twilio: URL con autenticación; de momento no se descarga
    if not datos:
        return None
    if tipo.startswith("audio"):
        return medios.transcribir(datos, tipo)
    if tipo.startswith("image"):
        return medios.leer_imagen(datos, tipo)
    return None


def _importar(msg: MensajeEntrante, est: Estado) -> str | None:
    """Crea el evento en la api en pendiente_confirmacion. Devuelve un aviso si hay que parar ahí."""
    try:
        res = api_cliente.importar_evento(est.borrador, contacto=msg.de, canal=_canal(msg), en_cola=False)
    except ApiNoDisponible:
        return None  # seguimos en local; al confirmar se importa (o queda en cola)
    except ErrorApi as e:
        if e.code == "publicador_pausado":
            estados[msg.de] = Estado()
            return "Ahora mismo tu cuenta de publicador está en pausa. Habla con el ayuntamiento para reactivarla."
        log.warning("La api rechazó la importación: %s %s", e.code, e.message)
        return None
    if res.get("duplicado"):
        estados[msg.de] = Estado()
        return "Ese evento ya lo tenía guardado 👍 No hace falta mandarlo otra vez."
    est.evento_id = res["evento"]["id"]
    # La api valida cada campo: lo que ella dice que falta manda
    for campo in res.get("faltan", []):
        if campo in CAMPOS_OBLIGATORIOS and campo not in est.borrador.faltan:
            est.borrador.faltan.append(campo)
            est.borrador.campos[campo] = Campo(valor=None, confianza="falta")
    return None


def _siguiente_paso(est: Estado) -> list[str | Respuesta]:
    faltan = est.borrador.faltan_obligatorios()
    if faltan:
        est.preguntando = faltan[0]
        if est.primera_pregunta:
            est.primera_pregunta = False
            # Ficha y pregunta en un solo mensaje: menos mensajes y más fácil de leer
            return [ficha_texto(est.borrador) + "\n\n" + PREGUNTAS[faltan[0]]]
        return [PREGUNTAS[faltan[0]]]
    est.preguntando = None
    est.esperando_confirmacion = True
    return [Respuesta(ficha_texto(est.borrador) + "\n\n¿Lo publico así? Responde *SÍ* o *NO*.", BOTONES_CONFIRMAR)]


def _rellenar(est: Estado, campo: str, respuesta: str) -> None:
    valor = None
    tz = ZoneInfo(get_settings().zona_horaria)
    if campo == "fecha_inicio":
        valor = extractor.extraer_con_reglas(respuesta, datetime.now(tz).date(), tz).fecha_inicio
    elif campo == "municipio":
        valor = extractor.buscar_municipio(respuesta)
    elif campo == "categoria":
        norm = extractor._normalizar(respuesta)
        valor = next((c for c in extractor.PALABRAS_CATEGORIA if c[:5] in norm), None)
    else:
        valor = respuesta.strip()[:120] or None
    if valor is not None:
        est.borrador.campos[campo] = Campo(valor=valor, confianza="alta")
        est.campos_corregidos[campo] = valor
        if campo in est.borrador.faltan:
            est.borrador.faltan.remove(campo)


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
    estados[msg.de] = Estado()
    if est.evento_id is None:
        # La api no estaba al empezar: se importa ahora con todo completado (o queda en cola)
        res = api_cliente.importar_evento(est.borrador, contacto=msg.de, canal=_canal(msg))
        if res is None:
            return "✅ Guardado. Lo enviaré a revisión en cuanto el sistema esté disponible."
        est.evento_id = res["evento"]["id"]
    try:
        evento, confirmado = api_cliente.confirmar_evento(est.evento_id, est.campos_corregidos, _canal(msg))
    except ErrorApi as e:
        return f"No he podido confirmarlo: {e.message} 🙏"
    if not confirmado:
        return "✅ ¡Recibido! Queda guardado y el ayuntamiento lo revisará. Te aviso cuando esté publicado."
    estado = (evento or {}).get("estado")
    if estado == "publicado":
        return "✅ ¡Publicado! Ya sale en la agenda y en el mapa 🎉"
    return "✅ ¡Enviado! El moderador lo revisará y te aviso cuando esté publicado."


# ---------- Identidad (Telegram) ----------

def _saludo(msg: MensajeEntrante) -> list[str | Respuesta]:
    usuario = _usuario(msg.de)
    if usuario and usuario.get("rol") == "moderador":
        return [f"¡Hola, {usuario['nombre']}! 👋\n{AYUDA_MODERADOR}\n\n{AYUDA}"]
    if usuario:
        return [f"¡Hola, {usuario['nombre']}! 👋\n" + AYUDA.split("\n", 1)[1]]
    if telegram.es_telegram(msg.de):
        return [Respuesta(AYUDA + "\n\n" + PEDIR_TELEFONO, pedir_contacto=True)]
    return [AYUDA]


def _vincular(msg: MensajeEntrante) -> list[str | Respuesta]:
    try:
        usuario = api_cliente.vincular(msg.telefono_compartido, msg.de, msg.nombre)
    except ApiNoDisponible:
        return [Respuesta("Gracias 🙏 Ahora mismo no puedo guardarlo; inténtalo en un rato.", quitar_teclado=True)]
    except ErrorApi as e:
        if e.code == "contacto_en_uso":
            return [Respuesta("Ese número ya está vinculado a otra cuenta de Telegram.", quitar_teclado=True)]
        return [Respuesta(f"No he podido guardar tu número: {e.message}", quitar_teclado=True)]
    _usuarios[msg.de] = (time.monotonic(), usuario)
    nombre = (usuario or {}).get("nombre") or msg.nombre or ""
    extra = ""
    if (usuario or {}).get("rol") == "moderador":
        extra = "\n" + AYUDA_MODERADOR
    elif (usuario or {}).get("publicador_id"):
        extra = "\nPublicas en nombre de tu entidad: lo que me mandes irá con su nombre."
    return [Respuesta(f"¡Gracias, {nombre}! Ya te tengo identificado ✅{extra}", quitar_teclado=True)] + \
        vecino.tras_vincular(msg, usuario)


# ---------- Moderador ----------

def _es_moderador(msg: MensajeEntrante) -> bool:
    usuario = _usuario(msg.de)
    return bool(usuario and usuario.get("rol") == "moderador")


def _bandeja(msg: MensajeEntrante) -> list[str | Respuesta]:
    if not _es_moderador(msg):
        return ["Esa opción es solo para moderadores 🙂"]
    try:
        items = api_cliente.moderacion_pendientes()
    except ApiNoDisponible:
        return ["No puedo consultar la bandeja ahora mismo. Inténtalo en un minuto 🙏"]
    except ErrorApi as e:
        if e.status == 404:
            return ["La bandeja de moderación aún no está disponible en la API."]
        return [f"No he podido abrir la bandeja: {e.message}"]
    eventos = [i for i in items if i.get("tipo") == "evento" and i.get("evento")]
    if not eventos:
        return ["No hay nada pendiente de revisar ✅"]
    respuestas: list[str | Respuesta] = [f"Tienes {len(eventos)} pendiente(s):"]
    for item in eventos:
        ev = item["evento"]
        try:
            fecha = datetime.fromisoformat(ev["fecha_inicio"]).strftime("%d/%m %H:%M")
        except (KeyError, ValueError):
            fecha = ""
        spam = f" · spam {item['score_spam']:.0%}" if item.get("score_spam") is not None else ""
        respuestas.append(Respuesta(
            f"🔎 *{ev.get('titulo', '')}*\n📍 {ev.get('municipio', '')} · 📅 {fecha}{spam}\nMotivo: {item.get('motivo', '')}",
            [(f"mod:aprobar:{ev['id']}", "✅ Aprobar"), (f"mod:rechazar:{ev['id']}", "❌ Rechazar")],
        ))
    return respuestas


def _decidir(msg: MensajeEntrante, accion: str) -> list[str]:
    partes = accion.split(":", 2)
    if len(partes) != 3 or partes[1] not in ("aprobar", "rechazar", "retirar"):
        return ["No he entendido esa opción."]
    if not _es_moderador(msg):
        return ["Esa opción es solo para moderadores 🙂"]
    _, decision, evento_id = partes
    try:
        evento = api_cliente.decidir(evento_id, decision, motivo=f"Decidido por chat ({_canal(msg)})")
    except ApiNoDisponible:
        return ["No he podido guardar la decisión. Inténtalo en un minuto 🙏"]
    except ErrorApi as e:
        return [f"No he podido guardar la decisión: {e.message}"]
    titulo = (evento or {}).get("titulo", "el evento")
    return [f"{'✅ Aprobado' if decision == 'aprobar' else '❌ Rechazado'}: {titulo}"]
