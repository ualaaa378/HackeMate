"""Cadena de proveedores: prueba cada IA en orden y, si todas fallan, usa reglas.
Cada intento queda registrado (tokens, latencia, fallo) en app.metrics."""

import logging
import time
from typing import Callable, TypeVar

from pydantic import BaseModel

from app import metrics
from app.config import get_settings
from app.llm.proveedores import ErrorProveedor, construir

log = logging.getLogger(__name__)
T = TypeVar("T", bound=BaseModel)

# Interruptor en caliente para la demo de robustez (POST /admin/simular-caida). None = lo que diga .env
_caida_forzada: bool | None = None


def caida_simulada() -> bool:
    return get_settings().llm_simular_caida if _caida_forzada is None else _caida_forzada


def forzar_caida(activa: bool | None) -> None:
    global _caida_forzada
    _caida_forzada = activa


class Resultado(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    salida: BaseModel
    proveedor: str
    tokens_entrada: int = 0
    tokens_salida: int = 0
    intentos: list[str] = []


def estructurado(
    tarea: str,
    system: str,
    texto: str,
    salida: type[T],
    reglas: Callable[[str], T],
    cadena: list[str] | None = None,
) -> Resultado:
    """`cadena`: orden propio de una tarea (p. ej. las N, FreeLLM primero) sin tocar LLM_CADENA."""
    s = get_settings()
    intentos: list[str] = []
    for nombre in cadena or s.proveedores:
        if nombre == "reglas":
            break
        proveedor = construir(nombre)
        if proveedor is None or not proveedor.disponible():
            intentos.append(f"{nombre}: sin configurar")
            continue
        if caida_simulada():
            intentos.append(f"{nombre}: caída simulada")
            metrics.registrar(nombre, proveedor.modelo, tarea, 0, 0, 0, ok=False)
            continue
        inicio = time.monotonic()
        try:
            obj, t_in, t_out = proveedor.estructurado(system, texto, salida)
        except ErrorProveedor as e:
            ms = int((time.monotonic() - inicio) * 1000)
            log.warning("Proveedor %s falló en %s ms: %s", nombre, ms, e)
            intentos.append(str(e))
            metrics.registrar(nombre, proveedor.modelo, tarea, 0, 0, ms, ok=False)
            continue
        ms = int((time.monotonic() - inicio) * 1000)
        metrics.registrar(nombre, proveedor.modelo, tarea, t_in, t_out, ms)
        return Resultado(salida=obj, proveedor=f"{nombre}:{proveedor.modelo}", tokens_entrada=t_in,
                         tokens_salida=t_out, intentos=intentos)

    metrics.registrar("reglas", "reglas", tarea, 0, 0, 0)
    return Resultado(salida=reglas(texto), proveedor="reglas", intentos=intentos)
