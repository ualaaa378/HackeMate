from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app import __version__, errores
from app.config import get_settings
from app.rutas import (
    auth,
    calendario,
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

app = FastAPI(title="HackeMate api", version=__version__)
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


@app.get("/health")
def health():
    return {"status": "ok", "version": get_settings().app_version or __version__}
