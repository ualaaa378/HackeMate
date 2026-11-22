"""Alta de una entidad por chat (tarea B5). Desde el 22/11 09:35 es el alta de una asociación (decisión de Adán: los
ayuntamientos ya vienen dados de alta con su perfil): ya no se pregunta el tipo, se envía siempre `asociacion`.

Pide el nombre y el pueblo de la entidad y los datos del responsable (nombre, DNI o NIE y dónde vive) y los
manda a `POST /publicadores` (contrato: `PublicadorCrear.responsable`). Sin esos datos, la entidad nunca podrá
publicar sin revisión. El DNI es un dato personal: solo vive en memoria mientras dura el alta, no se escribe en los
logs, no va a la cola en disco y en pantalla solo se enseña enmascarado. La API comprueba la letra y lo guarda solo
para los moderadores."""

import logging
import re
import unicodedata
from dataclasses import dataclass, field

from app import api_cliente, telegram
from app.agentes.extractor import buscar_municipio
from app.api_cliente import ApiNoDisponible, ErrorApi
from app.respuestas import Respuesta
from app.schemas import MUNICIPIOS, MensajeEntrante

log = logging.getLogger(__name__)

TIPOS = {
    "asociacion": "Asociación", "ayuntamiento": "Ayuntamiento", "bar_restaurante": "Bar o restaurante",
    "comercio": "Comercio", "otro": "Otro",
}
_PALABRAS_TIPO = {
    "asociacion": ("asociacion", "asoc", "club", "pena", "hermandad", "cofradia", "ampa", "colectivo"),
    "ayuntamiento": ("ayuntamiento", "ayto", "concejalia", "alcaldia"),
    "bar_restaurante": ("bar", "restaurante", "cafeteria", "meson", "taberna"),
    "comercio": ("comercio", "tienda", "negocio", "panaderia", "carniceria"),
    "otro": ("otro", "otra"),
}
_EMPEZAR = re.compile(
    r"\b(dar(me|nos|la|lo)? de alta|darse de alta|alta de (mi|nuestra|la|el) |registrar (mi|nuestra|la|el) "
    r"(asociacion|entidad|bar|restaurante|comercio|negocio|ayuntamiento|club)|quiero ser publicador|"
    r"hacerme publicador|ser organizador|publicar (como|en nombre de|por) (una|la|mi|el)? ?(asociacion|entidad|"
    r"bar|ayuntamiento|negocio|comercio|club))\b")

PREGUNTAS = {
    "nombre": "¿Cómo se llama la asociación? (por ejemplo, «Asociación Amigos de Velefique»)",
    "tipo": "¿Qué es?",
    "municipio": "¿En qué pueblo está? (" + ", ".join(MUNICIPIOS) + ")",
    "responsable": ("Ahora, la persona que la representa. Solo lo verán los moderadores del ayuntamiento, para "
                    "comprobar quién está detrás antes de dejaros publicar sin revisión.\n"
                    "¿Nombre y apellidos del responsable?"),
    "dni": "¿DNI o NIE del responsable? (por ejemplo, 12345678Z)",
    "residencia": "¿En qué pueblo vive el responsable?",
    "edad": "¿Cuántos años tiene el responsable? (opcional: pulsa *Saltar* si no quieres decirlo)",
}
TIPO_FIJO = "asociacion"  # los ayuntamientos ya están dados de alta: el paso «tipo» ya no se pregunta
PASOS = ["nombre", "municipio", "responsable", "dni", "residencia", "edad"]
BOTON_SALTAR = [("alta_saltar", "⏭️ Saltar")]
BOTONES_TIPO = [(f"alta_tipo:{k}", v) for k, v in TIPOS.items()]
BOTONES_CONFIRMAR = [("alta_si", "Sí, enviar"), ("alta_no", "No, cancelar")]
_LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"


@dataclass
class Alta:
    paso: str = "nombre"
    datos: dict = field(default_factory=dict)
    telefono: str | None = None
    esperando_telefono: bool = False  # Telegram: hace falta «Compartir mi número»


altas: dict[str, Alta] = {}


def _normalizar(texto: str) -> str:
    t = unicodedata.normalize("NFD", (texto or "").lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def quiere_alta(texto: str) -> bool:
    return bool(_EMPEZAR.search(_normalizar(texto)))


def en_curso(contacto: str) -> bool:
    return contacto in altas


def cancelar(contacto: str) -> None:
    altas.pop(contacto, None)


def normalizar_dni(dni: str) -> str | None:
    """Misma regla que la API (services/api/app/confianza.py): así el error se ve al momento, sin esperar al envío."""
    limpio = re.sub(r"[\s.-]", "", dni or "").upper()
    if m := re.fullmatch(r"(\d{8})([A-Z])", limpio):
        numero, letra = int(m[1]), m[2]
    elif m := re.fullmatch(r"([XYZ])(\d{7})([A-Z])", limpio):
        numero, letra = "XYZ".index(m[1]) * 10_000_000 + int(m[2]), m[3]
    else:
        return None
    return limpio if _LETRAS_DNI[numero % 23] == letra else None


def _enmascarar(dni: str) -> str:
    return "•" * (len(dni) - 4) + dni[-4:]


def _pregunta(alta: Alta) -> Respuesta:
    if alta.paso == "tipo":
        return Respuesta(PREGUNTAS["tipo"], BOTONES_TIPO)
    if alta.paso == "edad":
        return Respuesta(PREGUNTAS["edad"], BOTON_SALTAR)
    return Respuesta(PREGUNTAS[alta.paso])


def _resumen(alta: Alta) -> Respuesta:
    d = alta.datos
    return Respuesta(
        "Esto es lo que voy a enviar al ayuntamiento:\n"
        f"🏷️ {d['nombre']} ({TIPOS[d['tipo']]})\n📍 {d['municipio']}\n"
        f"👤 Responsable: {d['responsable']}, {_enmascarar(d['dni'])}, vive en {d['residencia']}"
        f"{', ' + str(d['edad']) + ' años' if d.get('edad') else ''}\n\n"
        "¿Lo envío?", BOTONES_CONFIRMAR)


def empezar(msg: MensajeEntrante, usuario: dict | None) -> list:
    if (usuario or {}).get("publicador_id"):
        return ["Ya publicas en nombre de una entidad ✅ Mándame el texto, una foto del cartel o una nota de voz y "
                "preparo la ficha."]
    alta = Alta(datos={"tipo": TIPO_FIJO})
    altas[msg.de] = alta
    salida: list = ["¡Genial! Doy de alta tu asociación en un momento. Te haré unas preguntas (escribe *cancelar* "
                    "para dejarlo)."]
    if telegram.es_telegram(msg.de):
        alta.telefono = (usuario or {}).get("telefono")
        if not alta.telefono:
            alta.esperando_telefono = True
            return salida + [Respuesta("Primero necesito tu número: pulsa *Compartir mi número* aquí abajo 📱",
                                       pedir_contacto=True)]
    elif msg.de.startswith("+"):
        alta.telefono = msg.de  # WhatsApp: el contacto ya es su teléfono
    return salida + [_pregunta(alta)]


def tras_vincular(msg: MensajeEntrante, usuario: dict | None) -> list:
    """Compartió su número a mitad del alta: seguimos donde íbamos."""
    alta = altas.get(msg.de)
    if not alta or not alta.esperando_telefono:
        return []
    alta.esperando_telefono = False
    alta.telefono = (usuario or {}).get("telefono") or msg.telefono_compartido
    if (usuario or {}).get("publicador_id"):
        cancelar(msg.de)
        return ["Ese número ya tiene una entidad dada de alta ✅ Ya puedes mandarme lo que organicéis."]
    return [_pregunta(alta)]


def responder(msg: MensajeEntrante, texto: str) -> list:
    alta = altas[msg.de]
    if alta.esperando_telefono:
        return [Respuesta("Para seguir, pulsa *Compartir mi número* aquí abajo 📱 (o escribe *cancelar*).",
                          pedir_contacto=True)]
    boton = msg.boton_id or ""
    if alta.paso == "confirmar":
        if boton == "alta_si" or re.match(r"^(s[ií]|vale|ok|envia|adelante)", _normalizar(texto)):
            return _enviar(msg, alta)
        if boton == "alta_no" or re.match(r"^no\b", _normalizar(texto)):
            cancelar(msg.de)
            return ["Vale, no envío nada y he borrado los datos."]
        return [_resumen(alta)]

    error = _guardar(alta, texto, boton)
    if error:
        botones = BOTONES_TIPO if alta.paso == "tipo" else BOTON_SALTAR if alta.paso == "edad" else None
        return [Respuesta(error, botones)]
    siguiente = PASOS.index(alta.paso) + 1
    if siguiente < len(PASOS):
        alta.paso = PASOS[siguiente]
        return [_pregunta(alta)]
    alta.paso = "confirmar"
    return [_resumen(alta)]


def _guardar(alta: Alta, texto: str, boton: str) -> str | None:
    """Guarda la respuesta del paso actual. Devuelve un aviso si no vale (y se repite la pregunta)."""
    t = texto.strip()
    if alta.paso == "nombre":
        if len(t) < 2:
            return PREGUNTAS["nombre"]
        alta.datos["nombre"] = t[:120]
    elif alta.paso == "tipo":
        tipo = boton.split(":", 1)[1] if boton.startswith("alta_tipo:") else next(
            (k for k, ps in _PALABRAS_TIPO.items() if any(re.search(rf"\b{p}", _normalizar(t)) for p in ps)), None)
        if tipo not in TIPOS:
            return "Elige una opción de los botones:"
        alta.datos["tipo"] = tipo
    elif alta.paso == "municipio":
        municipio = buscar_municipio(t)
        if not municipio:
            return "Ese pueblo no está en la plataforma. " + PREGUNTAS["municipio"]
        alta.datos["municipio"] = municipio
    elif alta.paso == "responsable":
        if len(t.split()) < 2:
            return "Necesito el nombre y al menos un apellido del responsable."
        alta.datos["responsable"] = t[:120]
    elif alta.paso == "dni":
        dni = normalizar_dni(t)
        if not dni:
            return "Ese DNI o NIE no es válido: revisa los números y la letra (por ejemplo, 12345678Z o X1234567L)."
        alta.datos["dni"] = dni
    elif alta.paso == "residencia":
        if len(t) < 2:
            return PREGUNTAS["residencia"]
        alta.datos["residencia"] = t[:200]
    elif alta.paso == "edad":  # P4b: opcional
        if boton == "alta_saltar" or re.match(r"^(saltar|paso|no)\b", _normalizar(t)):
            alta.datos.pop("edad", None)
            return None
        error = error_edad(t)
        if error:
            return error
        alta.datos["edad"] = leer_edad(t)
    return None


def leer_edad(texto: str) -> int | None:
    numero = re.search(r"\d{1,3}", texto)
    return int(numero.group()) if numero else None


def error_edad(texto: str) -> str | None:
    """P4a: de 14 a 120 años (en España hace falta tener 14 para dar el consentimiento de datos)."""
    edad = leer_edad(texto)
    if edad is None:
        return "Escríbeme solo los años con números (por ejemplo, 45), o pulsa *Saltar*."
    if edad < 14:
        return "Para registrarse hace falta tener al menos 14 años 🙏 Escribe otra edad o pulsa *Saltar*."
    if edad > 120:
        return "Esa edad no me cuadra 😅 Escríbela otra vez o pulsa *Saltar*."
    return None


def _enviar(msg: MensajeEntrante, alta: Alta) -> list:
    d = alta.datos
    if not alta.telefono:
        cancelar(msg.de)
        return ["No tengo tu número de teléfono, y sin él no puedo darte de alta. Escríbeme «quiero dar de alta mi "
                "asociación» y lo intentamos de nuevo."]
    cuerpo = {"nombre": d["nombre"], "tipo": d["tipo"], "municipio": d["municipio"], "telefono": alta.telefono,
              "responsable": {"nombre": d["responsable"], "dni": d["dni"], "residencia": d["residencia"]}}
    if d.get("edad"):
        cuerpo["responsable"]["edad"] = d["edad"]
    try:
        api_cliente.crear_publicador(cuerpo)
    except ApiNoDisponible:
        # No se deja en la cola en disco: lleva un DNI. Los datos siguen en memoria para reintentar con «sí»
        return [Respuesta("Ahora mismo no puedo enviarlo 🙏 Inténtalo en un minuto respondiendo *sí*.",
                          BOTONES_CONFIRMAR)]
    except ErrorApi as e:
        if e.code == "dni_invalido":
            alta.paso = "dni"
            return ["El ayuntamiento no acepta ese DNI o NIE. " + PREGUNTAS["dni"]]
        if e.code == "municipio_no_encontrado":
            alta.paso = "municipio"
            return [PREGUNTAS["municipio"]]
        cancelar(msg.de)
        if e.code == "publicador_ya_existe":
            return ["Ese teléfono ya tiene una entidad dada de alta ✅ Ya puedes mandarme lo que organicéis."]
        log.warning("La api rechazó el alta de publicador: %s", e.code)  # sin datos personales en el log
        return [f"No he podido darte de alta: {e.message}"]
    cancelar(msg.de)  # fuera de memoria en cuanto se envía
    return [f"✅ ¡Solicitud enviada! *{d['nombre']}* queda pendiente de que el ayuntamiento la revise; te aviso aquí "
            "cuando esté aprobada. Mientras, ya puedes mandarme vuestros planes: los revisará el moderador antes "
            "de publicarlos."]
