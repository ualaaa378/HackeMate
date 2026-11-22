"""Cliente HTTP del servicio api (Flujo A), según contracts/openapi.yaml.

Si la api no responde (red caída), importar y confirmar se guardan en una cola que se escribe en
disco (COLA_PATH), así un reinicio del bot no pierde nada, y se reintentan solos cada pocos segundos
(ver main.py). Los errores de negocio (4xx) se devuelven como ErrorApi para que la conversación
pueda explicarlos."""

import json as jsonlib
import logging
import threading
from dataclasses import dataclass, field
from pathlib import Path
from urllib.parse import quote, urlencode

import httpx

from app.config import get_settings
from app.schemas import ExtraccionEvento

log = logging.getLogger(__name__)

# {"metodo", "ruta", "json"} y, opcional, "al_reintentar": {"confirmar": {...}, "evento_ruta"…}
pendientes: list[dict] = []
_cerrojo = threading.Lock()


def _ruta_cola() -> Path | None:
    ruta = get_settings().cola_path
    return Path(ruta) if ruta else None


def guardar_cola() -> None:
    ruta = _ruta_cola()
    if ruta is None:
        return
    try:
        ruta.parent.mkdir(parents=True, exist_ok=True)
        tmp = ruta.with_suffix(".tmp")
        tmp.write_text(jsonlib.dumps(pendientes, ensure_ascii=False), encoding="utf-8")
        tmp.replace(ruta)  # escritura atómica: nunca queda un archivo a medias
    except OSError as e:
        log.error("No se pudo guardar la cola en %s: %s", ruta, e)


def cargar_cola() -> int:
    ruta = _ruta_cola()
    if ruta is None or not ruta.exists():
        return 0
    try:
        items = jsonlib.loads(ruta.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        log.error("Cola ilegible en %s, se ignora: %s", ruta, e)
        return 0
    with _cerrojo:
        pendientes[:] = [i for i in items if isinstance(i, dict) and "ruta" in i]
    return len(pendientes)


def _encolar(item: dict) -> None:
    with _cerrojo:
        pendientes.append(item)
        guardar_cola()


@dataclass
class ErrorApi(Exception):
    status: int
    code: str
    message: str = ""
    details: dict = field(default_factory=dict)  # p. ej. 409 ya_inscrito → {"inscripcion_id": …}


class ApiNoDisponible(Exception):
    """Red caída o la api devolvió 5xx."""


def _peticion(metodo: str, ruta: str, json: dict | None = None) -> dict | None:
    s = get_settings()
    try:
        r = httpx.request(metodo, f"{s.api_url}{ruta}", json=json, timeout=8,
                          headers={"X-Internal-Token": s.internal_token})
    except httpx.HTTPError as e:
        raise ApiNoDisponible(str(e)) from e
    if r.status_code >= 500:
        raise ApiNoDisponible(f"{r.status_code} {r.text[:200]}")
    if r.status_code >= 400:
        try:
            err = r.json().get("error", {})
        except ValueError:
            err = {}
        raise ErrorApi(r.status_code, err.get("code", "error"), err.get("message", r.text[:200]),
                       err.get("details") or {})
    return r.json() if r.content else None


def _o_en_cola(metodo: str, ruta: str, json: dict, al_reintentar: dict | None = None) -> dict | None:
    try:
        return _peticion(metodo, ruta, json)
    except ApiNoDisponible as e:
        log.warning("api no disponible, %s %s en cola: %s", metodo, ruta, e)
        item = {"metodo": metodo, "ruta": ruta, "json": json}
        if al_reintentar:
            item["al_reintentar"] = al_reintentar
        _encolar(item)
        return None


# ---------- Ingesta ----------

def importar_evento(extraccion: ExtraccionEvento, contacto: str, canal: str = "telegram",
                    url_origen: str | None = None, en_cola: bool = True,
                    confirmar_despues: dict | None = None) -> dict | None:
    """ResultadoImportacion {evento, faltan, duplicado}. Si la api no está: con en_cola=True queda en
    cola y devuelve None; con en_cola=False lanza ApiNoDisponible.
    confirmar_despues = {"campos": …, "canal": …}: el publicador ya dijo SÍ; al reintentar desde la
    cola se importa, se confirma y se le avisa."""
    cuerpo = {
        "extraccion": extraccion.model_dump(),
        "contacto_publicador": contacto,
        "origen": {"canal": canal, "url": url_origen, "importado_auto": canal in ("facebook", "instagram", "web_externa")},
    }
    if en_cola:
        extra = {"confirmar": confirmar_despues, "avisar": contacto} if confirmar_despues is not None else None
        return _o_en_cola("POST", "/api/v1/eventos/importar", cuerpo, al_reintentar=extra)
    return _peticion("POST", "/api/v1/eventos/importar", cuerpo)


def confirmar_evento(evento_id: str, campos: dict, canal: str) -> tuple[dict | None, bool]:
    """Devuelve (evento, confirmado). Mientras la api no tenga /confirmar (H2.3 de A), guarda los
    cambios con PATCH y el evento sigue en pendiente_confirmacion: confirmado = False."""
    cuerpo = {"campos": campos, "confirmado_por": canal if canal in ("whatsapp", "web", "telegram") else "web"}
    try:
        res = _peticion("POST", f"/api/v1/eventos/{evento_id}/confirmar", cuerpo)
        return (res or {}).get("evento", res), True
    except ErrorApi as e:
        if e.status not in (404, 405, 501) or e.code not in ("no_encontrado", "metodo_no_permitido", "error", "no_implementado"):
            raise
    except ApiNoDisponible:
        _encolar({"metodo": "POST", "ruta": f"/api/v1/eventos/{evento_id}/confirmar", "json": cuerpo})
        return None, False
    evento = _o_en_cola("PATCH", f"/api/v1/eventos/{evento_id}", campos) if campos else None
    return evento, False


# ---------- Usuarios ----------

def usuario_por_contacto(contacto: str) -> dict | None:
    try:
        return _peticion("GET", f"/api/v1/usuarios/by-contacto/{quote(contacto, safe=':')}")
    except ErrorApi as e:
        if e.status == 404:
            return None
        raise


def vincular(telefono: str, contacto: str, nombre: str | None = None) -> dict | None:
    cuerpo = {"telefono": telefono, "contacto": contacto}
    if nombre:
        cuerpo["nombre"] = nombre
    return _peticion("POST", "/api/v1/usuarios/vincular", cuerpo)


# ---------- Vecino ----------

def buscar_eventos(parametros: dict) -> list[dict]:
    """GET /eventos (solo publicados). Lanza ApiNoDisponible si la api no está."""
    res = _peticion("GET", "/api/v1/eventos?" + urlencode(parametros))
    return (res or {}).get("items", [])


def evento(evento_id: str) -> dict | None:
    try:
        return _peticion("GET", f"/api/v1/eventos/{evento_id}")
    except ErrorApi as e:
        if e.status == 404:
            return None
        raise


def planes_de(usuario_id: str) -> list[dict]:
    """P5a: los planes que propuso esa persona (o los de su entidad), en todos sus estados."""
    res = _peticion("GET", "/api/v1/eventos?" + urlencode({"organizador_id": usuario_id, "size": 50}))
    return (res or {}).get("items", [])


def apelar(evento_id: str, usuario_id: str, motivo: str) -> dict | None:
    """P3b: POST /eventos/{id}/apelacion en nombre de esa persona (con el token interno)."""
    return _peticion("POST", f"/api/v1/eventos/{evento_id}/apelacion", {"motivo": motivo, "usuario_id": usuario_id})


def editar_evento(evento_id: str, cambios: dict) -> dict | None:
    """P5b: PATCH /eventos/{id}. Si cambia la fecha o el lugar, la API avisa a los apuntados."""
    return _peticion("PATCH", f"/api/v1/eventos/{evento_id}", cambios)


def recomendaciones(usuario_id: str, limite: int = 3) -> list[dict] | None:
    """Lista de Recomendacion, o None si la api aún no tiene el recomendador."""
    try:
        res = _peticion("GET", f"/api/v1/recomendaciones?usuario_id={usuario_id}&limite={limite}")
    except ErrorApi as e:
        if e.status in (404, 405, 501) and e.code in ("no_encontrado", "metodo_no_permitido", "no_implementado"):
            return None
        raise
    return (res or {}).get("items", [])


def inscribir(evento_id: str, usuario_id: str, canal: str, plazas: int = 1) -> dict | None:
    canal = canal if canal in ("whatsapp", "web", "telegram") else "web"
    return _peticion("POST", f"/api/v1/eventos/{evento_id}/inscripciones",
                     {"usuario_id": usuario_id, "plazas": plazas, "canal": canal})


def responder_coche(evento_id: str, usuario_id: str, acepta: bool) -> dict | None:
    """Compartir coche: el sí o el no del vecino (la API solo pasa el contacto entre quienes dicen que sí)."""
    return _peticion("POST", f"/api/v1/eventos/{evento_id}/coche", {"usuario_id": usuario_id, "acepta": acepta})


def desinscribir(evento_id: str, inscripcion_id: str) -> dict | None:
    """N6b: devuelve la plaza (y sube al primero de la lista de espera)."""
    return _peticion("DELETE", f"/api/v1/eventos/{evento_id}/inscripciones/{inscripcion_id}")


def inscripcion_de(evento_id: str, usuario_id: str) -> dict | None:
    """La inscripción activa de esa persona en ese plan, o None (lista de inscritos con el token interno)."""
    res = _peticion("GET", f"/api/v1/eventos/{evento_id}/inscripciones?size=200")
    items = res.get("items", res) if isinstance(res, dict) else (res or [])
    return next((i for i in items if i.get("usuario_id") == usuario_id
                 and i.get("estado") in ("confirmada", "lista_espera")), None)


def preguntar_en_chat(evento_id: str, usuario_id: str, texto: str) -> dict | None:
    return _peticion("POST", f"/api/v1/eventos/{evento_id}/mensajes",
                     {"texto": texto[:1000], "tipo": "pregunta", "usuario_id": usuario_id})


def comentar_en_chat(evento_id: str, usuario_id: str, texto: str) -> dict | None:
    """«¿Qué tal fue?»: la valoración queda como comentario del plan (también vale con el plan ya terminado)."""
    return _peticion("POST", f"/api/v1/eventos/{evento_id}/mensajes",
                     {"texto": texto[:1000], "tipo": "comentario", "usuario_id": usuario_id})


def guardar_preferencias(usuario_id: str, cambios: dict) -> bool:
    """El contrato solo tiene PATCH /usuarios/me (login de usuario). Se prueba PATCH /usuarios/{id}
    con el token interno (propuesto a A); si no existe, el bot las guarda solo en memoria."""
    try:
        _peticion("PATCH", f"/api/v1/usuarios/{usuario_id}", cambios)
        return True
    except ErrorApi as e:
        if e.status in (404, 405, 501):
            return False
        raise


# ---------- Moderación ----------

def moderacion_pendientes(size: int = 5) -> list[dict]:
    res = _peticion("GET", f"/api/v1/moderacion/pendientes?size={size}")
    return (res or {}).get("items", [])


def decidir(evento_id: str, decision: str, motivo: str | None = None) -> dict | None:
    return _peticion("POST", f"/api/v1/moderacion/{evento_id}/decision", {"decision": decision, "motivo": motivo})


# ---------- Cola ----------

def reintentar_pendientes() -> int:
    """Manda la cola en orden. Para en cuanto la api vuelve a fallar (se reintentará luego).
    Lo que la api rechaza (4xx) se descarta: reintentarlo daría el mismo error."""
    enviados = 0
    for item in list(pendientes):
        try:
            res = _peticion(item["metodo"], item["ruta"], item["json"])
        except ApiNoDisponible:
            break
        except ErrorApi as e:
            log.error("La api rechazó %s %s de la cola: %s %s", item["metodo"], item["ruta"], e.code, e.message)
            res = None
        else:
            _despues_de_reintentar(item, res)
        with _cerrojo:
            if item in pendientes:
                pendientes.remove(item)
            guardar_cola()
        enviados += 1
    if enviados:
        log.info("Cola: %s petición(es) entregada(s) a la api, quedan %s", enviados, len(pendientes))
    return enviados


def _despues_de_reintentar(item: dict, res: dict | None) -> None:
    """Un evento que el publicador ya había confirmado sin api: ahora se confirma y se le avisa."""
    extra = item.get("al_reintentar")
    if not extra or not res or "evento" not in res:
        return
    from app import canales  # aquí para no crear un import circular

    titulo = res["evento"].get("titulo") or "tu evento"
    try:
        _, confirmado = confirmar_evento(res["evento"]["id"], extra["confirmar"].get("campos") or {},
                                         extra["confirmar"].get("canal", "web"))
    except ErrorApi as e:
        log.error("No se pudo confirmar desde la cola: %s", e.message)
        confirmado = False
    estado = "ya está enviado a revisión" if confirmado else "ya está guardado y el ayuntamiento lo revisará"
    if extra.get("avisar"):
        canales.enviar(extra["avisar"], f"✅ Ya hay conexión: *{titulo}* {estado}.")


# ---------- Alta de publicadores (B5) ----------

def crear_publicador(cuerpo: dict) -> dict | None:
    """POST /publicadores con el responsable (dato personal): nunca se encola en disco."""
    return _peticion("POST", "/api/v1/publicadores", cuerpo)


_municipios: dict[str, tuple[float, float]] = {}


def coordenadas_municipio(nombre: str) -> tuple[float, float] | None:
    """Lat/lon de un pueblo (GET /municipios, una vez). Para «cerca de Tahal»."""
    if not _municipios:
        try:
            for m in _peticion("GET", "/api/v1/municipios") or []:
                _municipios[m["nombre"]] = (m["lat"], m["lon"])
        except (ApiNoDisponible, ErrorApi, KeyError, TypeError):
            return None
    return _municipios.get(nombre)
