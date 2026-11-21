"""P5b, organizador: «modificar plan». Quien propuso un plan (vecino o asociación) lo cambia por el bot.

1. «modificar plan», «mis planes» o «quiero cambiar la hora de la ruta» → sus planes (GET /eventos?organizador_id=,
   P5a). Si nombra uno o solo tiene uno, va directo a él.
2. ¿Qué cambiar? Fecha y hora, lugar, descripción o plazas (botones, o dicho en la misma frase: «la hora»).
3. El nuevo valor → PATCH /eventos/{id}. Si cambia la fecha o el lugar, la API ya avisa a los apuntados.

Solo se ofrecen planes que se pueden cambiar (en revisión, pendientes o publicados que no han pasado). Un plan
rechazado no se modifica: se apela (P3). El bot llama con el token interno, así que solo enseña y cambia los planes
que la API dice que son de esa persona.
"""

import logging
import re
import unicodedata
from dataclasses import dataclass
from datetime import datetime
from zoneinfo import ZoneInfo

from app import api_cliente
from app.agentes import extractor
from app.api_cliente import ApiNoDisponible, ErrorApi
from app.config import get_settings
from app.respuestas import Respuesta

log = logging.getLogger(__name__)

EDITABLES = ("pendiente_confirmacion", "en_revision", "publicado")
ESTADOS = {
    "pendiente_confirmacion": "📝 sin terminar",
    "en_revision": "⏳ en revisión",
    "publicado": "✅ publicado",
    "rechazado": "❌ rechazado",
    "finalizado": "🏁 ya pasó",
    "cancelado": "🚫 cancelado",
    "archivado": "📦 retirado",
}
CAMPOS = {
    "fecha": ("📅 Fecha y hora", "¿Cuándo es ahora? Por ejemplo: «el sábado 12 de diciembre a las 18:00» o solo "
                                "«a las 19:30» si cambia la hora."),
    "lugar": ("📍 Lugar", "¿Dónde es ahora? Escríbeme el sitio (por ejemplo: «Plaza de la Iglesia»)."),
    "descripcion": ("📝 Descripción", "Escríbeme la nueva descripción del plan."),
    "plazas": ("👥 Plazas", "¿Cuántas plazas hay ahora? Escribe un número (0 = sin límite)."),
}

_MODIFICAR = (r"\b(modificar|modifica|modifico|cambiar|cambia|cambio|editar|edita|corregir|corrige|mover|mueve|"
              r"retrasar|retrasa|adelantar|adelanta)\b.*\b(plan|evento|actividad|hora|fecha|dia|lugar|sitio|"
              r"descripcion|plazas|ruta|taller|fiesta|torneo|concierto|charla|excursion)\b|"
              r"\bmis planes( propuestos)?\b|\bplanes que (he|e) propuesto\b|^modificar$")
_CAMPO_EN_TEXTO = (
    ("fecha", r"\b(hora|fecha|dia|retrasa\w*|adelanta\w*|mover|mueve)\b"),
    ("lugar", r"\b(lugar|sitio|donde)\b"),
    ("descripcion", r"\b(descripcion|texto|explicacion)\b"),
    ("plazas", r"\b(plazas|aforo|sitios para)\b"),
)
_VACIAS = {"el", "la", "los", "las", "de", "del", "un", "una", "mi", "plan", "quiero", "cambiar", "modificar", "hora",
           "fecha", "lugar", "en", "a", "al", "y", "que", "por", "para", "con"}


@dataclass
class Sesion:
    planes: dict[str, dict]
    evento_id: str | None = None
    campo: str | None = None


_sesiones: dict[str, Sesion] = {}


def _norm(texto: str) -> str:
    t = unicodedata.normalize("NFD", texto.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def quiere_modificar(texto: str) -> bool:
    """Frase corta: un post largo con «cambio de hora» es alguien publicando, no editando."""
    return bool(texto) and len(texto) <= 120 and bool(re.search(_MODIFICAR, _norm(texto).strip()))


def en_curso(contacto: str) -> bool:
    s = _sesiones.get(contacto)
    return s is not None and s.campo is not None


def cancelar(contacto: str) -> None:
    _sesiones.pop(contacto, None)


def _cuando(plan: dict) -> str:
    try:
        f = datetime.fromisoformat(plan["fecha_inicio"]).astimezone(ZoneInfo(get_settings().zona_horaria))
        return f.strftime("%d/%m %H:%M")
    except (KeyError, TypeError, ValueError):
        return ""


def _linea(plan: dict) -> str:
    return f"• *{plan.get('titulo', 'Plan')}* ({_cuando(plan)}) · {ESTADOS.get(plan.get('estado'), plan.get('estado'))}"


def _por_nombre(texto: str, planes: dict[str, dict]) -> str | None:
    dichas = set(re.findall(r"[a-z0-9]+", _norm(texto))) - _VACIAS
    puntos = {i: len(dichas & (set(re.findall(r"[a-z0-9]+", _norm(p.get("titulo", "")))) - _VACIAS))
              for i, p in planes.items()}
    if not puntos:
        return None
    mejor = max(puntos, key=puntos.get)
    if puntos[mejor] < 1 or list(puntos.values()).count(puntos[mejor]) > 1:
        return None
    return mejor


def _campo_dicho(texto: str) -> str | None:
    t = _norm(texto)
    return next((campo for campo, patron in _CAMPO_EN_TEXTO if re.search(patron, t)), None)


def empezar(contacto: str, texto: str, usuario: dict | None) -> list:
    """«modificar plan» / «mis planes»: lista sus planes y, si puede, va directo al plan y al campo."""
    if not (usuario or {}).get("id"):
        return ["No encuentro planes tuyos desde este número 🤔 Si propusiste uno desde la web, entra allí en "
                "«Mis planes propuestos». Si es la primera vez, mándame el plan y lo publico."]
    try:
        res = api_cliente.planes_de(usuario["id"])
    except ApiNoDisponible:
        return ["Ahora mismo no puedo ver tus planes. Inténtalo en un minuto 🙏"]
    except ErrorApi as e:
        log.warning("planes_de %s: %s", e.code, e.message)
        return ["No he podido ver tus planes ahora mismo 😕"]
    if not res:
        return ["Todavía no has propuesto ningún plan. Mándame uno (texto, foto del cartel o nota de voz) y lo "
                "preparo 🙂"]
    editables = {p["id"]: p for p in res if p.get("estado") in EDITABLES}
    resumen = "Estos son tus planes:\n" + "\n".join(_linea(p) for p in res[:8])
    if not editables:
        return [resumen + "\n\nNinguno se puede modificar ahora (ya pasaron, se cancelaron o los rechazó el "
                          "ayuntamiento)."]
    sesion = _sesiones[contacto] = Sesion(planes=editables)
    elegido = _por_nombre(texto, editables) or (next(iter(editables)) if len(editables) == 1 else None)
    if elegido is None:
        botones = [(f"orgplan:{i}", (p.get("titulo") or "Plan")[:40]) for i, p in list(editables.items())[:6]]
        return [Respuesta(resumen + "\n\n¿Cuál quieres modificar?", botones + [("orgfin", "❌ Ninguno")])]
    sesion.evento_id = elegido
    campo = _campo_dicho(texto)
    if campo:
        return [_preguntar_valor(sesion, campo)]
    return [_preguntar_campo(sesion)]


def _preguntar_campo(sesion: Sesion) -> Respuesta:
    plan = sesion.planes[sesion.evento_id]
    botones = [(f"orgcampo:{c}", etiqueta) for c, (etiqueta, _) in CAMPOS.items()] + [("orgfin", "❌ Nada")]
    return Respuesta(f"*{plan.get('titulo', 'Tu plan')}* ({_cuando(plan)}). ¿Qué quieres cambiar?", botones)


def _preguntar_valor(sesion: Sesion, campo: str) -> Respuesta:
    sesion.campo = campo
    return Respuesta(CAMPOS[campo][1], [("orgfin", "❌ Dejarlo como está")])


def boton(contacto: str, boton_id: str) -> list:
    sesion = _sesiones.get(contacto)
    if boton_id == "orgfin":
        cancelar(contacto)
        return ["Vale, no cambio nada 👍"]
    if sesion is None:
        return ["Se me ha olvidado de qué plan hablábamos 😅 Escríbeme «modificar plan» otra vez."]
    if boton_id.startswith("orgplan:"):
        evento_id = boton_id.split(":", 1)[1]
        if evento_id not in sesion.planes:
            return ["Ese plan ya no se puede modificar 🤔"]
        sesion.evento_id, sesion.campo = evento_id, None
        return [_preguntar_campo(sesion)]
    if boton_id.startswith("orgcampo:") and sesion.evento_id:
        campo = boton_id.split(":", 1)[1]
        if campo in CAMPOS:
            return [_preguntar_valor(sesion, campo)]
    return ["No te he entendido. Escríbeme «modificar plan» para empezar otra vez."]


def _nueva_fecha(texto: str, plan: dict) -> str | None:
    """«el 12 de diciembre a las 18:00» → esa fecha; «a las 19:30» → el mismo día del plan a esa hora."""
    tz = ZoneInfo(get_settings().zona_horaria)
    ahora = datetime.now(tz)
    leida = extractor.extraer_con_reglas(texto, ahora.date(), tz).fecha_inicio
    if leida:
        return leida if isinstance(leida, str) else leida.isoformat()
    hora = re.search(r"\b(\d{1,2})(?:[:.h](\d{2}))?\s*(?:h\b|horas?\b)?", _norm(texto))
    if not hora or not re.search(r"\d", texto) or int(hora.group(1)) > 23 or int(hora.group(2) or 0) > 59:
        return None
    try:
        actual = datetime.fromisoformat(plan["fecha_inicio"]).astimezone(tz)
    except (KeyError, TypeError, ValueError):
        return None
    nueva = actual.replace(hour=int(hora.group(1)), minute=int(hora.group(2) or 0), second=0, microsecond=0)
    return nueva.isoformat()


def responder(contacto: str, texto: str) -> list:
    """El nuevo valor del campo que se está cambiando."""
    sesion = _sesiones.get(contacto)
    if sesion is None or not sesion.evento_id or not sesion.campo:
        return ["Escríbeme «modificar plan» para empezar."]
    plan = sesion.planes[sesion.evento_id]
    campo, texto = sesion.campo, texto.strip()
    if campo == "fecha":
        valor = _nueva_fecha(texto, plan)
        if valor is None:
            return [Respuesta("No he entendido la fecha 🤔 Prueba así: «el 12 de diciembre a las 18:00» o «a las "
                              "19:30».", [("orgfin", "❌ Dejarlo como está")])]
        cambios = {"fecha_inicio": valor}
    elif campo == "plazas":
        numero = re.search(r"\d+", texto)
        if not numero:
            return [Respuesta("Escríbeme solo el número de plazas (por ejemplo, 30).", [("orgfin", "❌ Dejarlo")])]
        total = int(numero.group())
        cambios = {"plazas_totales": total or None}
    elif campo == "lugar":
        cambios = {"lugar": texto[:200]}
    else:
        cambios = {"descripcion": texto[:2000]}
    if not any(v for v in cambios.values()) and campo != "plazas":
        return ["Escríbeme el nuevo valor, o pulsa «Dejarlo como está»."]
    try:
        nuevo = api_cliente.editar_evento(sesion.evento_id, cambios) or {}
    except ApiNoDisponible:
        return ["Ahora mismo no puedo guardar el cambio. Inténtalo en un minuto 🙏"]
    except ErrorApi as e:
        if e.code in ("fechas_invalidas", "validacion"):
            return [Respuesta(f"La API no lo acepta: {e.message}. Prueba con otro valor.",
                              [("orgfin", "❌ Dejarlo como está")])]
        cancelar(contacto)
        return [f"No he podido cambiarlo: {e.message}"]
    cancelar(contacto)
    titulo = nuevo.get("titulo") or plan.get("titulo") or "tu plan"
    extra = ""
    if campo in ("fecha", "lugar") and plan.get("estado") == "publicado":
        extra = "\nHe avisado a las personas apuntadas del cambio 📣"
    if campo == "fecha":
        detalle = f"ahora es el {_cuando({'fecha_inicio': cambios['fecha_inicio']})}"
    elif campo == "plazas":
        detalle = f"ahora tiene {cambios['plazas_totales']} plazas" if cambios["plazas_totales"] else "ya no tiene límite de plazas"
    elif campo == "lugar":
        detalle = f"ahora es en {cambios['lugar']}"
    else:
        detalle = "tiene la nueva descripción"
    return [f"Hecho ✅ *{titulo}* {detalle}.{extra}\nSi quieres cambiar algo más, escríbeme «modificar plan»."]
