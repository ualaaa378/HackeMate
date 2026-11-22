"""Registro de tokens por llamada a la IA (criterio del jurado «coste en tokens»).
Se guarda en memoria para /metrics y se manda a la api sin bloquear la respuesta."""

import logging
import threading
import time
from collections import defaultdict

import httpx

from app.config import get_settings

log = logging.getLogger(__name__)

_lock = threading.Lock()
_totales: dict[str, dict[str, int]] = defaultdict(lambda: {"llamadas": 0, "entrada": 0, "salida": 0, "fallos": 0})
_ultimas: list[dict] = []


def registrar(proveedor: str, modelo: str, tarea: str, entrada: int, salida: int, ms: int, ok: bool = True) -> None:
    registro = {
        "proveedor": proveedor,
        "modelo": modelo,
        "tarea": tarea,
        "tokens_entrada": entrada,
        "tokens_salida": salida,
        "latencia_ms": ms,
        "ok": ok,
        "ts": time.time(),
    }
    with _lock:
        t = _totales[proveedor]
        t["llamadas"] += 1
        t["entrada"] += entrada
        t["salida"] += salida
        if not ok:
            t["fallos"] += 1
        _ultimas.append(registro)
        del _ultimas[:-100]
    threading.Thread(target=_enviar_a_api, args=(registro,), daemon=True).start()


def _enviar_a_api(registro: dict) -> None:
    s = get_settings()
    try:
        httpx.post(
            f"{s.api_url}/api/v1/metrics/tokens",
            json=registro,
            headers={"X-Internal-Token": s.internal_token},
            timeout=3,
        )
    except httpx.HTTPError as e:
        log.debug("No se pudieron enviar las métricas a la api: %s", e)


def resumen() -> dict:
    with _lock:
        return {"totales": dict(_totales), "ultimas": list(_ultimas[-20:])}
