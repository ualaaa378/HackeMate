"""Cliente HTTP del servicio api (Flujo A). Si la api no responde, el evento se
guarda en una cola en memoria y se reintenta con reintentar_pendientes()."""

import logging

import httpx

from app.config import get_settings
from app.schemas import ExtraccionEvento

log = logging.getLogger(__name__)

pendientes: list[dict] = []


def _cabeceras() -> dict:
    return {"X-Internal-Token": get_settings().internal_token}


def importar_evento(extraccion: ExtraccionEvento, telefono: str, canal: str = "whatsapp",
                    url_origen: str | None = None) -> dict | None:
    cuerpo = {
        "extraccion": extraccion.model_dump(),
        "telefono_publicador": telefono,
        "origen": {"canal": canal, "url": url_origen, "importado_auto": canal in ("facebook", "instagram", "web_externa")},
    }
    try:
        r = httpx.post(f"{get_settings().api_url}/api/v1/eventos/importar", json=cuerpo, headers=_cabeceras(),
                       timeout=5)
        r.raise_for_status()
        return r.json()
    except httpx.HTTPError as e:
        log.warning("api no disponible, evento en cola: %s", e)
        pendientes.append(cuerpo)
        return None


def reintentar_pendientes() -> int:
    enviados = 0
    for cuerpo in list(pendientes):
        try:
            r = httpx.post(f"{get_settings().api_url}/api/v1/eventos/importar", json=cuerpo, headers=_cabeceras(),
                           timeout=5)
            r.raise_for_status()
        except httpx.HTTPError:
            break
        pendientes.remove(cuerpo)
        enviados += 1
    return enviados
