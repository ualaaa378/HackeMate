import asyncio
import contextlib
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, errores
from app.config import get_settings
from app.notificaciones import ciclo_reintentos
from app.rutas import (
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
    usuarios,
)

log = logging.getLogger(__name__)


async def bucle_reintentos(intervalo: float) -> None:
    """Cada `intervalo` segundos reintenta los avisos pendientes (H4.5). La primera vuelta espera el intervalo:
    el arranque no depende ni de la base ni del bot. El envío (httpx síncrono) va en un hilo."""
    while True:
        await asyncio.sleep(intervalo)
        try:
            await asyncio.to_thread(ciclo_reintentos)
        except Exception:  # noqa: BLE001
            log.exception("fallo en la tarea de reintento de avisos")


@asynccontextmanager
async def ciclo_de_vida(_: FastAPI):
    intervalo = get_settings().notificaciones_reintento_s
    tarea = asyncio.create_task(bucle_reintentos(intervalo)) if intervalo > 0 else None
    try:
        yield
    finally:
        if tarea is not None:
            tarea.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await tarea


app = FastAPI(title="HackeMate api", version=__version__, lifespan=ciclo_de_vida)
app.add_middleware(
    CORSMiddleware,
    allow_origins=get_settings().lista_cors,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
errores.registrar(app)
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


@app.get("/health")
def health():
    return {"status": "ok", "version": get_settings().app_version or __version__}
