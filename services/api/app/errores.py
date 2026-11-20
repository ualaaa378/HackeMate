"""Formato común de error (PLAN.md §5.2): {"error": {"code", "message", "details"}}, para cualquier fallo."""

import logging

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException

log = logging.getLogger(__name__)

# Códigos para los errores que lanza el propio framework (ruta inexistente, método no permitido…)
_CODIGOS_HTTP = {
    401: "no_autenticado",
    403: "prohibido",
    404: "no_encontrado",
    405: "metodo_no_permitido",
    409: "conflicto",
    429: "demasiadas_peticiones",
}


class ErrorApi(Exception):
    def __init__(self, status: int, code: str, message: str, details: dict | None = None):
        self.status, self.code, self.message, self.details = status, code, message, details or {}


def _cuerpo(code: str, message: str, details: dict | None = None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or {}}}


def registrar(app: FastAPI) -> None:
    @app.exception_handler(ErrorApi)
    async def _error_api(_: Request, e: ErrorApi):
        return JSONResponse(_cuerpo(e.code, e.message, e.details), status_code=e.status)

    @app.exception_handler(RequestValidationError)
    async def _validacion(_: Request, e: RequestValidationError):
        detalles = {"errores": jsonable_encoder(e.errors(), exclude={"ctx", "input"})}
        return JSONResponse(_cuerpo("validacion", "Parámetros no válidos", detalles), status_code=422)

    @app.exception_handler(HTTPException)
    async def _http(_: Request, e: HTTPException):
        code = _CODIGOS_HTTP.get(e.status_code, "error_http")
        return JSONResponse(_cuerpo(code, str(e.detail)), status_code=e.status_code, headers=e.headers)

    @app.exception_handler(Exception)
    async def _inesperado(request: Request, e: Exception):
        log.exception("Error no controlado en %s %s", request.method, request.url.path)
        return JSONResponse(_cuerpo("error_interno", "Error interno del servidor"), status_code=500)
