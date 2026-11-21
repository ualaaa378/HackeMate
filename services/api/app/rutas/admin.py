"""Panel de robustez del moderador: la API hace de intermediaria con el bot para que el INTERNAL_TOKEN no llegue
nunca al navegador. `GET /admin/bot/metricas` → bot `GET /metrics`; `POST /admin/bot/simular-caida` → bot
`POST /admin/simular-caida`. Si el bot no responde, 503 `bot_no_disponible`; si responde con error, 502."""

import logging

import httpx
from fastapi import APIRouter, Depends
from pydantic import BaseModel, ConfigDict, StrictBool

from app.config import get_settings
from app.errores import ErrorApi
from app.seguridad import exigir_moderador

log = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/admin/bot", tags=["admin"], dependencies=[Depends(exigir_moderador)])

TIMEOUT_BOT_S = 3.0


class CaidaSimulada(BaseModel):
    """components/schemas/CaidaSimulada."""

    model_config = ConfigDict(extra="ignore")

    activa: StrictBool


def _no_disponible(status: int, mensaje: str, details: dict | None = None) -> ErrorApi:
    return ErrorApi(status, "bot_no_disponible", mensaje, details)


def _llamar_bot(metodo: str, ruta: str, cuerpo: dict | None = None) -> dict:
    ajustes = get_settings()
    if not ajustes.bot_url:
        raise _no_disponible(503, "El bot no está configurado (BOT_URL vacío)")
    try:
        r = httpx.request(
            metodo,
            ajustes.bot_url.rstrip("/") + ruta,
            json=cuerpo,
            headers={"X-Internal-Token": ajustes.internal_token},
            timeout=TIMEOUT_BOT_S,
        )
    except httpx.HTTPError as e:
        log.info("bot %s no responde (%s)", ruta, type(e).__name__)
        raise _no_disponible(503, "El bot no responde") from None
    if r.status_code >= 400:
        raise _no_disponible(502, "El bot ha respondido con un error", {"status": r.status_code})
    try:
        datos = r.json()
    except ValueError:
        datos = None
    if not isinstance(datos, dict):
        raise _no_disponible(502, "El bot ha respondido algo que no es JSON", {"status": r.status_code})
    return datos


@router.get("/metricas")
def metricas_bot():
    return _llamar_bot("GET", "/metrics")


@router.post("/simular-caida")
def simular_caida(datos: CaidaSimulada):
    respuesta = _llamar_bot("POST", "/admin/simular-caida", {"activa": datos.activa})
    if not isinstance(respuesta.get("activa"), bool):
        raise _no_disponible(502, "Respuesta inesperada del bot", {"status": 200})
    return {"activa": respuesta["activa"]}
