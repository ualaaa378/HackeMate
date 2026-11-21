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

from app import alta, api_cliente, apelacion, avisos, canales, organizador, telegram, vecino
from app.agentes import antispam, moderador, extractor, idiomas, intencion, medios, voz
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
    "🏛️ ¿Representas una asociación, un bar o el ayuntamiento? Escribe «quiero dar de alta mi asociación».\n"
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
    if (est and (est.preguntando or est.esperando_confirmacion)) or alta.en_curso(msg.de):
        return False
    return len(msg.texto) > 40 or bool(msg.media_url or msg.media_id)


idiomas_por_contacto: dict[str, str] = {}  # el último idioma claro en que escribió


def procesar(msg: MensajeEntrante, solo_consola: bool = False) -> list[str]:
    """Procesa un mensaje y envía las respuestas. Devuelve los textos enviados.
    solo_consola: el simulador (/dev/mensaje) nunca debe escribir a un canal real."""
    idioma = _idioma(msg)
    if idioma != "es" and msg.texto and not msg.boton_id:
        msg = msg.model_copy(update={"texto": idiomas.traducir([msg.texto], "es", origen=idioma)[0]})

    respuestas = [r if isinstance(r, Respuesta) else Respuesta(r) for r in _responder(msg)]
    if idioma != "es":
        _traducir_respuestas(respuestas, idioma)

    for r in respuestas:
        if solo_consola:
            canales.enviar_consola(msg.de, r.texto, r.botones, r.pedir_contacto)
        else:
            canales.enviar(msg.de, r.texto, r.botones, pedir_contacto=r.pedir_contacto,
                           quitar_teclado=r.quitar_teclado, pedir_ubicacion=r.pedir_ubicacion)
    textos = [r.texto for r in respuestas]
    if not solo_consola and _quiere_voz(msg):
        ogg = voz.sintetizar(voz.texto_para_voz(textos))
        if ogg:
            canales.enviar_voz(msg.de, ogg)
    return textos


def _idioma(msg: MensajeEntrante) -> str:
    if msg.texto and not msg.boton_id and (detectado := idiomas.detectar(msg.texto)):
        idiomas_por_contacto[msg.de] = detectado
    return idiomas_por_contacto.get(msg.de, "es")


def _traducir_respuestas(respuestas: list[Respuesta], idioma: str) -> None:
    """Una sola llamada a la IA para todos los textos y botones de la respuesta."""
    etiquetas = [t for r in respuestas for _, t in (r.botones or [])]
    traducidos = idiomas.traducir([r.texto for r in respuestas] + etiquetas, idioma)
    for r, texto in zip(respuestas, traducidos):
        r.texto = texto
    resto = iter(traducidos[len(respuestas):])
    for r in respuestas:
        if r.botones:
            r.botones = [(i, next(resto, t)) for i, t in r.botones]


def _quiere_voz(msg: MensajeEntrante) -> bool:
    """Responde también en audio a quien escribe con notas de voz o pidió avisos por voz."""
    if (msg.media_tipo or "").startswith("audio"):
        return True
    prefs = vecino.preferencias_locales.get(msg.de)
    return bool(prefs and prefs.formato_aviso == "audio")


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
    # Solo se guarda lo encontrado: «no existe» puede dejar de ser verdad al momento (el bot da de alta al decir
    # sus gustos, al aceptar avisos o al apuntarse) y no puede quedarse 60 s olvidando a la persona
    if usuario is not None:
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
        organizador.cancelar(msg.de)
        apelacion.cancelar(msg.de)
        if alta.en_curso(msg.de):
            alta.cancelar(msg.de)
            return [Respuesta("Vale, dejo el alta y he borrado los datos.", quitar_teclado=True)]
        return ["Vale, borrado. Cuando quieras me mandas otro evento."]

    # D2: viene de la web para entrar con código (t.me/HackeMate_bot?start=codigo)
    if t == "/codigo":
        return _para_codigo(msg)

    # Alta de una entidad (B5): mientras dura, cada mensaje es la respuesta a su pregunta
    if alta.en_curso(msg.de):
        return alta.responder(msg, texto)
    if msg.de in esperando_edad and (texto or msg.boton_id == "edad_saltar"):  # P4b
        respuesta = _responder_edad(msg, texto)
        if respuesta is not None:
            return respuesta
    if texto and not msg.boton_id and alta.quiere_alta(texto):
        return alta.empezar(msg, _usuario(msg.de))

    if t.startswith("mod:rechazar:") and msg.boton_id:  # idea 5: primero el motivo, luego el rechazo
        if not _es_moderador(msg):
            return ["Esa opción es solo para moderadores 🙂"]
        return _proponer_rechazo(msg, msg.boton_id.split(":", 2)[2])
    if t.startswith("mod:"):
        return _decidir(msg, t)
    if msg.boton_id and (t.startswith(("modrz_ok:", "modrz_otro:")) or t == "modrz_no"):
        return _rechazo(msg, msg.boton_id)
    if texto and not msg.boton_id and (_rechazos.get(msg.de) or {}).get("escribiendo") and _es_moderador(msg):
        return _decidir(msg, f"mod:rechazar:{_rechazos[msg.de]['evento_id']}", motivo=texto[:500])
    # P3b: apelar un plan rechazado (botón del aviso, el motivo que espera o «quiero apelar»)
    if msg.boton_id and t.startswith("apelar:"):
        return apelacion.empezar(msg.de, msg.boton_id.split(":", 1)[1], _usuario(msg.de))
    if msg.boton_id and t == "apelar_no":
        apelacion.cancelar(msg.de)
        return ["Vale, no apelo 👍"]
    if texto and not msg.boton_id and apelacion.esperando(msg.de):
        return apelacion.responder(msg.de, texto, _usuario(msg.de))
    if texto and not msg.boton_id and apelacion.quiere_apelar(texto):
        return apelacion.empezar(msg.de, None, _usuario(msg.de))
    # P5b: «modificar plan» (botones, la respuesta que espera y la frase que lo empieza)
    if msg.boton_id and (t.startswith(("orgplan:", "orgcampo:")) or t == "orgfin"):
        return organizador.boton(msg.de, msg.boton_id)
    if texto and not msg.boton_id and organizador.en_curso(msg.de):
        return organizador.responder(msg.de, texto)
    if texto and not msg.boton_id and organizador.quiere_modificar(texto):
        return organizador.empezar(msg.de, texto, _usuario(msg.de))
    if t.startswith("insc:"):
        return vecino.inscribir(msg, msg.boton_id.split(":", 1)[1], _usuario(msg.de))
    if t.startswith("desinsc:"):  # N6b: [Desapuntarme]
        _, evento_id, insc_id = msg.boton_id.split(":", 2)
        return vecino.desinscribir(msg, evento_id, insc_id, _usuario(msg.de))
    if t == "insc_ok":
        return ["👍 ¡Nos vemos allí!"]
    if t.startswith("valora:"):  # botón de «¿qué tal fue?»
        _, evento_id, nivel = msg.boton_id.split(":", 2)
        return vecino.valorar(msg, evento_id, vecino.VALORACIONES.get(nivel, nivel), _usuario(msg.de))
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

    # D1: «avísame» / «no quiero avisos» (también con los botones de la pregunta o en una nota de voz)
    if not es_cartel and (acepta := avisos.que_quiere(msg, texto)) is not None:
        return eco + avisos.responder(msg, acepta, _usuario(msg.de))

    # Contesta a «¿qué tal fue?» con sus palabras (o una nota de voz): si no está buscando ni apuntándose, es la
    # valoración del plan y va como comentario
    if not es_cartel and texto and (evento_valorado := vecino.valoracion_pendiente(msg.de)):
        if intencion.detectar(texto).tipo not in ("buscar", "inscribir", "desinscribir", "gustos"):
            return eco + vecino.valorar(msg, evento_valorado, f"💬 {texto[:900]}", _usuario(msg.de))

    # Un cartel siempre es para publicar; texto y notas de voz pueden ser de un vecino que busca planes
    if not es_cartel:
        tipo = intencion.detectar(texto, vecino.mirando_evento(msg.de)).tipo
        if tipo == "buscar" and intencion.es_pregunta_concreta(texto) and vecino.plan_nombrado(msg, texto):
            tipo = "pregunta_evento"  # pregunta por un plan que nombra: se responde, no se busca
        if tipo == "buscar":
            return eco + vecino.buscar(msg, texto, _usuario(msg.de))
        if tipo == "gustos":
            usuario = _usuario(msg.de)
            return eco + vecino.gustos(msg, texto, usuario) + avisos.pregunta_si_toca(msg, usuario)
        if tipo == "inscribir":
            return eco + vecino.inscribir(msg, None, _usuario(msg.de))
        if tipo == "desinscribir":
            return eco + vecino.desinscribir(msg, None, None, _usuario(msg.de))
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
    if extraccion.faltan_obligatorios():
        # La API pasa el antispam al confirmar, y sin fecha no se puede confirmar: si es spam, no preguntamos
        spam = antispam.puntuar(texto)
        if spam.es_spam:
            estados[msg.de] = Estado()
            log.info("Post descartado por el antispam del bot (%.2f): %s", spam.score_spam, spam.motivo)
            return eco + ["No puedo publicar esto: parece publicidad o spam 🚫\n"
                          "Si es un error, habla con el ayuntamiento para que lo revise."]
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
        res = api_cliente.importar_evento(
            est.borrador, contacto=msg.de, canal=_canal(msg),
            confirmar_despues={"campos": est.campos_corregidos, "canal": _canal(msg)})
        if res is None:
            return "✅ Guardado. Lo enviaré a revisión en cuanto el sistema esté disponible y te aviso."
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


LISTO_PARA_CODIGO = ("✅ Listo. Vuelve a la web y pulsa *Pedir el código*: te llegará aquí un código de 6 cifras "
                     "para comprobar que el número es tuyo.")
esperando_codigo: set[str] = set()  # vino de la web y aún no ha compartido su número


def _para_codigo(msg: MensajeEntrante) -> list[str | Respuesta]:
    """D2: para que la API pueda mandarle el código, el bot tiene que conocer su número."""
    usuario = _usuario(msg.de)
    if (usuario or {}).get("telefono"):
        return [LISTO_PARA_CODIGO]
    esperando_codigo.add(msg.de)
    return [Respuesta("¡Hola! 👋 Para mandarte el código de la web necesito tu número: pulsa *Compartir mi número* "
                      "aquí abajo 📱", pedir_contacto=True)]


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
        vecino.tras_vincular(msg, usuario) + alta.tras_vincular(msg, usuario) + avisos.tras_vincular(msg, usuario) + \
        _codigo_tras_vincular(msg) + _preguntar_edad(msg, usuario)


# ---------- P4b: la edad, opcional, la primera vez que se identifica ----------

esperando_edad: set[str] = set()
PREGUNTA_EDAD = "Una última cosa (opcional): ¿cuántos años tienes? Así te recomiendo mejor los planes."
BOTON_SIN_EDAD = [("edad_saltar", "⏭️ Prefiero no decirlo")]


def _preguntar_edad(msg: MensajeEntrante, usuario: dict | None) -> list:
    if not (usuario or {}).get("id") or usuario.get("edad") is not None or usuario.get("rol") == "moderador":
        return []
    if alta.en_curso(msg.de):  # el alta de la asociación ya pregunta la del responsable
        return []
    esperando_edad.add(msg.de)
    return [Respuesta(PREGUNTA_EDAD, BOTON_SIN_EDAD)]


def _responder_edad(msg: MensajeEntrante, texto: str) -> list | None:
    """La respuesta a «¿cuántos años tienes?». None si no es una edad: se olvida la pregunta y sigue normal."""
    if msg.boton_id == "edad_saltar":
        esperando_edad.discard(msg.de)
        return ["Sin problema 👍"]
    if not re.fullmatch(r"\D{0,20}\d{1,3}\D{0,20}", texto or ""):
        esperando_edad.discard(msg.de)
        return None
    error = alta.error_edad(texto)
    if error:
        return [Respuesta(error.replace("*Saltar*", "«Prefiero no decirlo»"), BOTON_SIN_EDAD)]
    esperando_edad.discard(msg.de)
    usuario = _usuario(msg.de)
    if not (usuario or {}).get("id"):
        return ["Ahora mismo no puedo guardarlo, pero no pasa nada 🙂"]
    try:
        api_cliente.guardar_preferencias(usuario["id"], {"edad": alta.leer_edad(texto)})
    except ApiNoDisponible:
        return ["Ahora mismo no puedo guardarlo, pero no pasa nada 🙂"]
    except ErrorApi as e:
        if e.code == "edad_minima":
            return ["Para registrarse hace falta tener al menos 14 años 🙏"]
        return [f"No he podido guardarlo: {e.message}"]
    _usuarios.pop(msg.de, None)
    return ["¡Apuntado, gracias! ✅"]


def _codigo_tras_vincular(msg: MensajeEntrante) -> list[str]:
    if msg.de not in esperando_codigo:
        return []
    esperando_codigo.discard(msg.de)
    return [LISTO_PARA_CODIGO]


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
    # Idea 5: resumen de la bandeja y una sugerencia por plan (reglas, sin tokens)
    respuestas: list[str | Respuesta] = [moderador.resumen([i.get("motivo") for i in eventos])]
    _vista_bandeja[msg.de] = {i["evento"]["id"]: i for i in eventos}
    for item in eventos:
        ev = item["evento"]
        try:
            fecha = datetime.fromisoformat(ev["fecha_inicio"]).strftime("%d/%m %H:%M")
        except (KeyError, ValueError):
            fecha = ""
        spam = f" · spam {item['score_spam']:.0%}" if item.get("score_spam") is not None else ""
        respuestas.append(Respuesta(
            f"🔎 *{ev.get('titulo', '')}*\n📍 {ev.get('municipio', '')} · 📅 {fecha}{spam}\nMotivo: {item.get('motivo', '')}"
            f"\n{moderador.sugerencia(item.get('motivo'))}",
            [(f"mod:aprobar:{ev['id']}", "✅ Aprobar"), (f"mod:rechazar:{ev['id']}", "❌ Rechazar")],
        ))
    return respuestas


# ---------- Idea 5: el rechazo lleva un motivo amable que redacta la IA y revisa el moderador ----------

_vista_bandeja: dict[str, dict[str, dict]] = {}  # moderador -> {evento_id: item de la bandeja}
_rechazos: dict[str, dict] = {}  # moderador -> {evento_id, titulo, texto, escribiendo}


def _botones_rechazo(evento_id: str) -> list:
    return [(f"modrz_ok:{evento_id}", "✅ Enviar y rechazar"), (f"modrz_otro:{evento_id}", "✏️ Escribir otro"),
            ("modrz_no", "↩️ No rechazar")]


def _proponer_rechazo(msg: MensajeEntrante, evento_id: str) -> list:
    item = _vista_bandeja.get(msg.de, {}).get(evento_id)
    titulo, motivo = None, None
    if item:
        titulo, motivo = item["evento"].get("titulo"), item.get("motivo")
    else:
        try:
            ev = api_cliente.evento(evento_id) or {}
            titulo, motivo = ev.get("titulo"), ev.get("motivo_moderacion")
        except (ApiNoDisponible, ErrorApi):
            pass
    titulo = titulo or "este plan"
    texto, _ = moderador.motivo_rechazo(titulo, motivo)
    _rechazos[msg.de] = {"evento_id": evento_id, "titulo": titulo, "texto": texto, "escribiendo": False}
    return [Respuesta(f"Voy a rechazar *{titulo}*. Le enviaré este mensaje a quien lo propuso:\n\n«{texto}»",
                      _botones_rechazo(evento_id))]


def _rechazo(msg: MensajeEntrante, boton: str) -> list:
    if not _es_moderador(msg):
        return ["Esa opción es solo para moderadores 🙂"]
    if boton == "modrz_no":
        _rechazos.pop(msg.de, None)
        return ["Vale, no lo rechazo. Sigue en la bandeja 👍"]
    borrador = _rechazos.get(msg.de)
    evento_id = boton.split(":", 1)[1]
    if not borrador or borrador["evento_id"] != evento_id:
        return _proponer_rechazo(msg, evento_id)
    if boton.startswith("modrz_otro:"):
        borrador["escribiendo"] = True
        return [Respuesta("Escríbeme el motivo con tus palabras y se lo envío al rechazarlo.",
                          [("modrz_no", "↩️ No rechazar")])]
    return _decidir(msg, f"mod:rechazar:{evento_id}", motivo=borrador["texto"])


def _decidir(msg: MensajeEntrante, accion: str, motivo: str | None = None) -> list[str]:
    partes = accion.split(":", 2)
    if len(partes) != 3 or partes[1] not in ("aprobar", "rechazar", "retirar"):
        return ["No he entendido esa opción."]
    if not _es_moderador(msg):
        return ["Esa opción es solo para moderadores 🙂"]
    _, decision, evento_id = partes
    if decision == "rechazar":
        _rechazos.pop(msg.de, None)
    try:
        evento = api_cliente.decidir(evento_id, decision, motivo=motivo or f"Decidido por chat ({_canal(msg)})")
    except ApiNoDisponible:
        return ["No he podido guardar la decisión. Inténtalo en un minuto 🙏"]
    except ErrorApi as e:
        return [f"No he podido guardar la decisión: {e.message}"]
    titulo = (evento or {}).get("titulo", "el evento")
    return [f"{'✅ Aprobado' if decision == 'aprobar' else '❌ Rechazado'}: {titulo}"]
