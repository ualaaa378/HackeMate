"""Conversación del vecino (Hito 3): buscar planes, decir sus gustos, apuntarse con un botón
y preguntar por un evento (responde la IA solo con la ficha; si no lo sabe, al organizador).
El estado vive en memoria por contacto; los datos de verdad están en la api."""

import logging
import re
import unicodedata
from dataclasses import dataclass, field
from datetime import datetime
from zoneinfo import ZoneInfo

from app import api_cliente, telegram
from app.agentes import asistente, busqueda, preferencias
from app.api_cliente import ApiNoDisponible, ErrorApi
from app.config import get_settings
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante

log = logging.getLogger(__name__)

MAX_TARJETAS = 3
NOMBRE_CATEGORIA = {"deportiva": "deporte y rutas", "cultural": "cultura", "fiestas": "fiestas",
                    "gastronomia": "gastronomía", "ludica": "ocio y juegos", "comercio": "ofertas"}
PEDIR_TELEFONO = "Para apuntarte necesito saber quién eres: pulsa *Compartir mi número* aquí abajo."
PLAN_TERMINADO = "Ese plan ya ha terminado 😕 Pregúntame «¿qué hay este finde?» y te enseño los próximos."
ESTADOS_TERMINADOS = ("finalizado", "cancelado", "archivado")


@dataclass
class Vecino:
    evento_activo: dict | None = None  # el que está mirando: sus preguntas van al asistente
    consulta_pendiente: busqueda.Consulta | None = None  # esperando su ubicación
    inscripcion_pendiente: str | None = None  # esperando que comparta su número
    ultimos: list[str] = field(default_factory=list)
    titulos: dict[str, str] = field(default_factory=dict)  # id → título de los últimos que vio


vecinos: dict[str, Vecino] = {}
preferencias_locales: dict[str, preferencias.Preferencias] = {}  # mientras la api no las guarde
ubicaciones: dict[str, tuple[float, float]] = {}


def _v(contacto: str) -> Vecino:
    return vecinos.setdefault(contacto, Vecino())


def _ahora() -> datetime:
    return datetime.now(ZoneInfo(get_settings().zona_horaria))


def _canal(msg: MensajeEntrante) -> str:
    return msg.canal if msg.canal != "console" else "web"


def _enlace(evento_id: str) -> str:
    return f"{get_settings().web_url.rstrip('/')}/evento/{evento_id}"


def terminado(ev: dict) -> bool:
    """Plan pasado (o cancelado): no admite inscripciones ni preguntas (contrato: 409 evento_finalizado)."""
    if ev.get("estado") in ESTADOS_TERMINADOS:
        return True
    try:
        fin = datetime.fromisoformat(ev.get("fecha_fin") or ev["fecha_inicio"])
    except (KeyError, TypeError, ValueError):
        return False
    return fin < _ahora()


def mirando_evento(contacto: str) -> bool:
    return bool(vecinos.get(contacto) and vecinos[contacto].evento_activo)


# ---------- Tarjetas ----------

def _fecha(ev: dict) -> str:
    try:
        return datetime.fromisoformat(ev["fecha_inicio"]).strftime("%d/%m a las %H:%M")
    except (KeyError, TypeError, ValueError):
        return ""


def tarjeta(ev: dict, motivo: str | None = None) -> str:
    lugar = ", ".join(x for x in (ev.get("lugar"), ev.get("municipio")) if x)
    lineas = [f"📌 *{ev.get('titulo', '')}*", f"📅 {_fecha(ev)}", f"📍 {lugar}"]
    if ev.get("es_gratuito"):
        lineas.append("💶 Gratis")
    elif ev.get("precio_eur") is not None:
        lineas.append(f"💶 {ev['precio_eur']:g} €")
    if ev.get("plazas_libres") is not None:
        lineas.append("👥 ¡Últimas plazas!" if ev["plazas_libres"] <= 3 else f"👥 Quedan {ev['plazas_libres']} plazas")
    if motivo:
        lineas.append(f"⭐ {motivo}")
    return "\n".join(lineas)


def _botones(ev: dict) -> list:
    return [(f"insc:{ev['id']}", "✋ Apuntarme"), (f"info:{ev['id']}", "ℹ️ Más info")]


# ---------- Buscar ----------

def _gustos(contacto: str, usuario: dict | None) -> list[str]:
    if contacto in preferencias_locales:
        return list(preferencias_locales[contacto].gustos)
    return list((usuario or {}).get("gustos") or [])


def buscar(msg: MensajeEntrante, texto: str, usuario: dict | None,
           consulta: busqueda.Consulta | None = None) -> list:
    c = consulta or busqueda.interpretar(texto, _ahora())
    lat = lon = None
    if c.cerca and not c.municipio:
        if msg.de in ubicaciones:
            lat, lon = ubicaciones[msg.de]
        elif usuario and usuario.get("lat") is not None:
            lat, lon = usuario["lat"], usuario["lon"]
        elif usuario and usuario.get("municipio"):
            c.municipio = usuario["municipio"]
        else:
            _v(msg.de).consulta_pendiente = c
            if telegram.es_telegram(msg.de):
                return [Respuesta("Para buscar cerca de ti, pulsa *Enviar mi ubicación* aquí abajo 📍",
                                  pedir_ubicacion=True)]
            return ["¿En qué pueblo estás? (Lucainena, Senés, Velefique, Uleila o Tahal)"]

    gustos = _gustos(msg.de, usuario)
    generico = not (c.municipio or c.categorias or c.cerca)
    if generico and usuario and usuario.get("id"):
        try:
            recos = api_cliente.recomendaciones(usuario["id"], limite=MAX_TARJETAS)
        except (ApiNoDisponible, ErrorApi):
            recos = None
        if recos:
            return _presentar(msg, [r["evento"] for r in recos], f"Te recomiendo {c.periodo}:",
                              motivos={r["evento"]["id"]: r.get("motivo") for r in recos})

    try:
        eventos = api_cliente.buscar_eventos(c.parametros(lat, lon))
        cabecera = f"Esto es lo que hay {c.periodo}" + (f" en {c.municipio}" if c.municipio else "") + ":"
        if not eventos and (c.hasta and (c.hasta - c.desde).days < 25):
            c.hasta = None  # nada en esas fechas: miramos más adelante
            eventos = api_cliente.buscar_eventos(c.parametros(lat, lon))
            cabecera = f"No hay nada {c.periodo}" + (f" en {c.municipio}" if c.municipio else "") + \
                       ", pero más adelante hay esto:"
    except ApiNoDisponible:
        return ["Ahora mismo no puedo consultar la agenda. Inténtalo en un minuto 🙏"]

    if len(c.categorias) > 1:
        eventos = [e for e in eventos if e.get("categoria") in c.categorias]
    if not eventos:
        return ["No he encontrado planes con esa búsqueda 😕 Prueba con otro pueblo o con «¿qué hay este mes?»."]
    # Primero lo que le gusta; dentro, por fecha
    eventos.sort(key=lambda e: (e.get("categoria") not in gustos, e.get("fecha_inicio") or ""))
    motivos = {e["id"]: f"Te gusta: {NOMBRE_CATEGORIA.get(e['categoria'], e['categoria'])}"
               for e in eventos if e.get("categoria") in gustos}
    return _presentar(msg, eventos, cabecera, motivos)


def _presentar(msg: MensajeEntrante, eventos: list[dict], cabecera: str, motivos: dict | None = None) -> list:
    motivos = motivos or {}
    v = _v(msg.de)
    v.ultimos = [e["id"] for e in eventos[:MAX_TARJETAS]]
    v.titulos = {e["id"]: e.get("titulo") or "" for e in eventos[:MAX_TARJETAS]}
    salida: list = [cabecera]
    for ev in eventos[:MAX_TARJETAS]:
        salida.append(Respuesta(tarjeta(ev, motivos.get(ev["id"])), _botones(ev)))
    if len(eventos) > MAX_TARJETAS:
        salida.append(f"Y {len(eventos) - MAX_TARJETAS} más. Dime un pueblo, un día o un tipo de plan para afinar.")
    return salida


def ubicacion_recibida(msg: MensajeEntrante, usuario: dict | None) -> list:
    ubicaciones[msg.de] = (msg.lat, msg.lon)
    v = _v(msg.de)
    if v.consulta_pendiente:
        consulta, v.consulta_pendiente = v.consulta_pendiente, None
        return [Respuesta("¡Gracias! 📍", quitar_teclado=True)] + buscar(msg, "", usuario, consulta)
    return [Respuesta("¡Gracias! Ya sé por dónde estás. Pregúntame «¿qué hay cerca este finde?»", quitar_teclado=True)]


# ---------- Gustos ----------

def gustos(msg: MensajeEntrante, texto: str, usuario: dict | None) -> list:
    nuevas = preferencias.interpretar(texto)
    if not nuevas.gustos and not nuevas.formato_aviso:
        return ["No he entendido qué te gusta 🤔 Dímelo así: «me gustan las rutas y las fiestas»."]
    previas = preferencias_locales.get(msg.de) or preferencias.Preferencias(gustos=(usuario or {}).get("gustos") or [])
    combinadas = preferencias.Preferencias(
        gustos=list(dict.fromkeys(previas.gustos + nuevas.gustos)),
        etiquetas_interes=list(dict.fromkeys(previas.etiquetas_interes + nuevas.etiquetas_interes))[:10],
        municipio=nuevas.municipio or previas.municipio,
        formato_aviso=nuevas.formato_aviso or previas.formato_aviso,
    )
    preferencias_locales[msg.de] = combinadas
    if usuario and usuario.get("id"):
        cambios = {"gustos": combinadas.gustos, "etiquetas_interes": combinadas.etiquetas_interes}
        if combinadas.municipio:
            cambios["municipio"] = combinadas.municipio
        if combinadas.formato_aviso:
            cambios["formato_aviso"] = combinadas.formato_aviso
        try:
            api_cliente.guardar_preferencias(usuario["id"], cambios)
        except (ApiNoDisponible, ErrorApi) as e:
            log.warning("No se pudieron guardar las preferencias en la api: %s", e)
    lista = ", ".join(NOMBRE_CATEGORIA.get(g, g) for g in combinadas.gustos)
    salida: list = [f"¡Apuntado! 📝 Te gusta: {lista}." + (
        " Te avisaré con notas de voz 🎙️" if combinadas.formato_aviso == "audio" else "")]
    if nuevas.gustos:
        c = busqueda.interpretar("", _ahora())
        c.categorias = nuevas.gustos
        if nuevas.municipio:
            c.municipio = nuevas.municipio
        resultado = buscar(msg, "", usuario, c)
        if len(resultado) > 1:  # hay tarjetas
            salida += ["Mira lo que hay ahora mismo que te puede gustar:"] + resultado[1:]
    return salida


# ---------- Ficha, preguntas e inscripción ----------

def info(msg: MensajeEntrante, evento_id: str) -> list:
    try:
        ev = api_cliente.evento(evento_id)
    except ApiNoDisponible:
        return ["Ahora mismo no puedo abrir la ficha. Inténtalo en un minuto 🙏"]
    if ev is None:
        return ["Ese plan ya no está en la agenda 😕"]
    _v(msg.de).evento_activo = ev
    texto = tarjeta(ev)
    if ev.get("descripcion"):
        texto += f"\n\n{ev['descripcion']}"
    if terminado(ev):
        # Plan pasado: no se puede apuntar ni preguntar, solo ver fotos y comentar en la web
        texto += f"\n\nEste plan ya terminó 📸 Mira las fotos y los comentarios en la web:\n🔗 {_enlace(ev['id'])}"
        return [Respuesta(texto)]
    texto += f"\n\n🔗 {_enlace(ev['id'])}\n\nPregúntame lo que quieras de este plan (hora, precio, qué llevar…)."
    return [Respuesta(texto, [(f"insc:{ev['id']}", "✋ Apuntarme")])]


def pregunta(msg: MensajeEntrante, texto: str, usuario: dict | None) -> list:
    ev = _v(msg.de).evento_activo
    botones = None if terminado(ev) else [(f"insc:{ev['id']}", "✋ Apuntarme")]
    r = asistente.responder(ev, texto)
    if r.puede_responder:
        return [Respuesta(r.respuesta, botones)]
    if terminado(ev):
        return [f"Eso no lo pone en la ficha, y el plan ya terminó 📸 En la web puedes ver las fotos y comentar:\n"
                f"🔗 {_enlace(ev['id'])}"]
    if usuario and usuario.get("id"):
        try:
            api_cliente.preguntar_en_chat(ev["id"], usuario["id"], texto)
            return ["Eso no lo pone en la ficha 🤔 Se lo he pasado al organizador y te contestará."]
        except ErrorApi as e:
            if e.code == "evento_finalizado":
                return [PLAN_TERMINADO]
            log.info("No se pudo dejar la pregunta en el chat del evento: %s", e)
        except ApiNoDisponible as e:
            log.info("No se pudo dejar la pregunta en el chat del evento: %s", e)
    return [f"Eso no lo pone en la ficha 🤔 Puedes preguntarlo al organizador en el chat del evento:\n🔗 {_enlace(ev['id'])}"]


_VACIAS = set("de del la las el los al a en con por para y un una mi me que".split())


def _sin_tildes(texto: str) -> str:
    return unicodedata.normalize("NFKD", texto.lower()).encode("ascii", "ignore").decode()


def _por_nombre(texto: str, titulos: dict[str, str]) -> str | None:
    """«apúntame al taller de esparto» → el id del plan mostrado cuyo título encaja mejor (sin empates)."""
    dichas = set(re.findall(r"[a-z0-9]+", _sin_tildes(texto))) - _VACIAS
    puntos = {i: len(dichas & (set(re.findall(r"[a-z0-9]+", _sin_tildes(t))) - _VACIAS)) for i, t in titulos.items()}
    if not puntos:
        return None
    mejor = max(puntos, key=puntos.get)
    if puntos[mejor] == 0 or list(puntos.values()).count(puntos[mejor]) > 1:
        return None
    return mejor


def inscribir(msg: MensajeEntrante, evento_id: str | None, usuario: dict | None) -> list:
    v = _v(msg.de)
    evento_id = (evento_id or (_por_nombre(msg.texto or "", v.titulos) if not msg.boton_id else None)
                 or (v.evento_activo or {}).get("id") or (v.ultimos[0] if len(v.ultimos) == 1 else None))
    if not evento_id:
        if len(v.ultimos) > 1:
            return ["¿A cuál te apunto? Dime su nombre (por ejemplo, «apúntame a la ruta») o pulsa ✋ Apuntarme en su ficha."]
        return ["¿A qué plan te quieres apuntar? Búscalo primero, por ejemplo: «¿qué hay este finde?»"]
    if (v.evento_activo or {}).get("id") == evento_id and terminado(v.evento_activo):
        return [PLAN_TERMINADO]  # ya sabemos que pasó: ni lo intentamos
    if not usuario:
        if telegram.es_telegram(msg.de):
            v.inscripcion_pendiente = evento_id
            return [Respuesta(PEDIR_TELEFONO, pedir_contacto=True)]
        try:  # WhatsApp: el contacto ya es su teléfono
            usuario = api_cliente.vincular(msg.de, msg.de, msg.nombre)
        except (ApiNoDisponible, ErrorApi):
            return ["Ahora mismo no puedo apuntarte. Inténtalo en un minuto 🙏"]
    try:
        insc = api_cliente.inscribir(evento_id, usuario["id"], _canal(msg))
    except ApiNoDisponible:
        return ["Ahora mismo no puedo apuntarte. Inténtalo en un minuto 🙏"]
    except ErrorApi as e:
        if e.status == 409 and e.code == "evento_finalizado":
            return [PLAN_TERMINADO]
        if e.status == 409:
            return ["Ya estabas apuntado/a 😉"]
        if e.status == 404 and e.code == "no_encontrado":  # la api aún no tiene inscripciones
            return [f"Todavía no puedo apuntarte desde el chat. Puedes hacerlo aquí:\n🔗 {_enlace(evento_id)}"]
        if e.status == 404:
            return ["Ese plan ya no está en la agenda 😕"]
        return [f"No he podido apuntarte: {e.message}"]
    titulo = ((v.evento_activo or {}).get("titulo") if (v.evento_activo or {}).get("id") == evento_id
              else v.titulos.get(evento_id))
    nombre = f" a *{titulo}*" if titulo else ""
    if (insc or {}).get("estado") == "lista_espera":
        puesto = insc.get("posicion_espera")
        return [f"Ahora mismo está lleno{nombre}: estás en lista de espera" +
                (f" (puesto {puesto})" if puesto else "") + ". Si queda sitio, te aviso 🙌"]
    return [f"✅ ¡Apuntado/a{nombre}! Te avisaré si hay cambios. ¡Nos vemos allí! 🎉"]


def tras_vincular(msg: MensajeEntrante, usuario: dict | None) -> list:
    """Si compartió el número para apuntarse, completamos la inscripción."""
    v = _v(msg.de)
    if v.inscripcion_pendiente and usuario:
        evento_id, v.inscripcion_pendiente = v.inscripcion_pendiente, None
        return inscribir(msg, evento_id, usuario)
    return []
