"""Cliente HTTP del servicio api (Flujo A), según contracts/openapi.yaml.

Si la api no responde (red caída), importar y confirmar se guardan en una cola en memoria y se
reintentan con reintentar_pendientes(). Los errores de negocio (4xx) se devuelven como ErrorApi
para que la conversación pueda explicarlos."""

import logging
from dataclasses import dataclass
from urllib.parse import quote, urlencode

import httpx

from app.config import get_settings
from app.schemas import ExtraccionEvento

log = logging.getLogger(__name__)

pendientes: list[dict] = []  # {"metodo", "ruta", "json"}


@dataclass
class ErrorApi(Exception):
    status: int
    code: str
    message: str = ""


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
        raise ErrorApi(r.status_code, err.get("code", "error"), err.get("message", r.text[:200]))
    return r.json() if r.content else None


def _o_en_cola(metodo: str, ruta: str, json: dict) -> dict | None:
    try:
        return _peticion(metodo, ruta, json)
    except ApiNoDisponible as e:
        log.warning("api no disponible, %s %s en cola: %s", metodo, ruta, e)
        pendientes.append({"metodo": metodo, "ruta": ruta, "json": json})
        return None


# ---------- Ingesta ----------

def importar_evento(extraccion: ExtraccionEvento, contacto: str, canal: str = "telegram",
                    url_origen: str | None = None, en_cola: bool = True) -> dict | None:
    """ResultadoImportacion {evento, faltan, duplicado}. Si la api no está: con en_cola=True queda en
    cola y devuelve None; con en_cola=False lanza ApiNoDisponible."""
    cuerpo = {
        "extraccion": extraccion.model_dump(),
        "contacto_publicador": contacto,
        "origen": {"canal": canal, "url": url_origen, "importado_auto": canal in ("facebook", "instagram", "web_externa")},
    }
    if en_cola:
        return _o_en_cola("POST", "/api/v1/eventos/importar", cuerpo)
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
        pendientes.append({"metodo": "POST", "ruta": f"/api/v1/eventos/{evento_id}/confirmar", "json": cuerpo})
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


def preguntar_en_chat(evento_id: str, usuario_id: str, texto: str) -> dict | None:
    return _peticion("POST", f"/api/v1/eventos/{evento_id}/mensajes",
                     {"texto": texto[:1000], "tipo": "pregunta", "usuario_id": usuario_id})


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
    enviados = 0
    for item in list(pendientes):
        try:
            _peticion(item["metodo"], item["ruta"], item["json"])
        except ApiNoDisponible:
            break
        except ErrorApi as e:
            log.error("La api rechazó %s %s de la cola: %s %s", item["metodo"], item["ruta"], e.code, e.message)
        pendientes.remove(item)
        enviados += 1
    return enviados
