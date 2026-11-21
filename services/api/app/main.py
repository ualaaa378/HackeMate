import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app import __version__, errores
from app.config import avisar_configuracion_insegura, get_settings
from app.notificaciones import ciclo_reintentos
from app.tareas_programadas import ciclo_tareas
from app.rutas import (
    admin,
    auth,
    calendario,
    estadisticas,
    eventos,
    importar,
    inscripciones,
    mensajes,
    moderacion,
    publicadores,
    publico,
    recomendaciones,
    sugerencias,
    usuarios,
)

log = logging.getLogger(__name__)

# Las fotos van hasta 2 MB en base64 (~2,7 MB de JSON): 4 MB deja margen para el resto de campos.
MAX_CUERPO_BYTES = 4 * 1024 * 1024


async def bucle_reintentos(intervalo: float) -> None:
    """Cada `intervalo` segundos reintenta los avisos pendientes (H4.5). La primera vuelta espera el intervalo:
    el arranque no depende ni de la base ni del bot. El envío (httpx síncrono) va en un hilo."""
    while True:
        await asyncio.sleep(intervalo)
        try:
            await asyncio.to_thread(ciclo_reintentos)
        except Exception:  # noqa: BLE001
            log.exception("fallo en la tarea de reintento de avisos")


async def bucle_tareas(intervalo: float) -> None:
    """Recordatorios, «¿qué tal fue?» y resumen semanal (app/tareas_programadas.py), cada `intervalo` segundos."""
    while True:
        await asyncio.sleep(intervalo)
        try:
            await asyncio.to_thread(ciclo_tareas)
        except Exception:  # noqa: BLE001
            log.exception("fallo en las tareas programadas")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    avisar_configuracion_insegura()
    ajustes = get_settings()
    intervalo = ajustes.notificaciones_reintento_s
    tareas = []
    if intervalo > 0:
        tareas.append(asyncio.create_task(bucle_reintentos(intervalo)))
    if ajustes.tareas_cada_min > 0:
        tareas.append(asyncio.create_task(bucle_tareas(ajustes.tareas_cada_min * 60)))
    try:
        yield
    finally:
        for tarea in tareas:
            tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarea


app = FastAPI(title="HackeMate api", version=__version__, lifespan=ciclo_de_vida)
errores.registrar(app)


@app.middleware("http")
async def limitar_cuerpo(request: Request, call_next):
    """413 `cuerpo_demasiado_grande` si `Content-Length` pasa de 4 MB (antes de leer el cuerpo)."""
    longitud = request.headers.get("content-length")
    if longitud is not None:
        try:
            demasiado = int(longitud) > MAX_CUERPO_BYTES
        except ValueError:
            demasiado = False
        if demasiado:
            return JSONResponse(
                {"error": {"code": "cuerpo_demasiado_grande", "message": "La petición ocupa más de 4 MB",
                           "details": {"max_bytes": MAX_CUERPO_BYTES}}},
                status_code=413,
            )
    return await call_next(request)


# CORS después (queda por fuera): así el 413 también lleva las cabeceras CORS y la web puede leerlo.
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().lista_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.include_router(publico.router)
app.include_router(importar.router)
app.include_router(eventos.router)
app.include_router(inscripciones.router)
app.include_router(mensajes.router)
app.include_router(publicadores.router)
app.include_router(usuarios.router)
app.include_router(usuarios.router_me)
app.include_router(auth.router)
app.include_router(moderacion.router)
app.include_router(calendario.router)
app.include_router(recomendaciones.router)
app.include_router(estadisticas.router)
app.include_router(admin.router)
app.include_router(sugerencias.router)


@app.get("/health")
def health():
    return {"status": "ok", "version": get_settings().app_version or __version__}
