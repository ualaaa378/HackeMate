"""Choque de fechas al confirmar un plan (tareas nocturnas 22/11).

Antes de preguntar «¿Lo publico así?», el bot pide a la API (`GET /api/v1/choques`) si ese día ya hay otro plan
publicado a 20 km o menos. Si lo hay, la IA elige entre los días libres que da la API y redacta el aviso; el
publicador decide con [📅 Cambiar al …] o [Mantener la fecha]. Sin IA, reglas: el primer día libre y una plantilla.
Se mira una sola vez por plan."""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app import api_cliente
from app.api_cliente import ApiNoDisponible, ErrorApi
from app.config import get_settings
from app.llm import router
from app.respuestas import Respuesta

log = logging.getLogger(__name__)

CAMBIAR, MANTENER = "choque:cambiar", "choque:mantener"
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")

SYSTEM = """Ayudas a quien organiza planes en pueblos de Almería. Su plan coincide el mismo día con otro plan cercano.
Elige el mejor día libre de la lista (número de la opción, empezando en 0) pensando en que vaya más gente: mejor
fin de semana si el plan era en fin de semana y mejor lo más cercano a la fecha original. Escribe un aviso breve
(máx. 220 caracteres, de tú, en español, sin inventar datos) que diga con qué plan coincide y proponga ese día.
La decisión es de la persona: no le digas lo que tiene que hacer."""


class _Propuesta(BaseModel):
    opcion: int = Field(description="Índice del día libre elegido, desde 0")
    texto: str = Field(description="Aviso breve para quien organiza")


def dia_bonito(iso: str) -> str:
    d = datetime.fromisoformat(iso).astimezone(ZoneInfo(get_settings().zona_horaria))
    return f"{DIAS[d.weekday()]} {d.day}"


def _plantilla(choque: dict, alternativa: str) -> str:
    return (f"⚠️ Ese día ya hay «{choque['titulo']}» en {choque['municipio']}. Si lo pasas al "
            f"{dia_bonito(alternativa)}, no se pisan y puede ir más gente. ¿Qué prefieres?")


def proponer(fecha_inicio: str, municipio: str, evento_id: str | None) -> tuple[Respuesta, str] | None:
    """(aviso con botones, fecha propuesta) si hay choque y un día libre; None si no hay choque o no se puede mirar.
    Nunca lanza: si falla algo, el plan se confirma como siempre."""
    try:
        res = api_cliente.choques(fecha_inicio, municipio, evento_id) or {}
    except (ApiNoDisponible, ErrorApi) as e:
        log.info("Choque de fechas sin comprobar: %s", e)
        return None
    choques, libres = res.get("choques") or [], res.get("alternativas") or []
    if not choques or not libres:
        return None
    choque = choques[0]
    opciones = "\n".join(f"{i}: {dia_bonito(f)} ({f})" for i, f in enumerate(libres))
    try:
        r = router.estructurado(
            tarea="choque_fechas",
            system=SYSTEM,
            texto=(f"Plan del organizador: {dia_bonito(fecha_inicio)} en {municipio}.\n"
                   f"Coincide con «{choque['titulo']}» en {choque['municipio']} (a {choque['distancia_km']} km).\n"
                   f"Días libres:\n{opciones}"),
            salida=_Propuesta,
            reglas=lambda _t: _Propuesta(opcion=0, texto=_plantilla(choque, libres[0])),
            cadena=get_settings().proveedores_tareas_n,
        )
        elegida = libres[r.salida.opcion] if 0 <= r.salida.opcion < len(libres) else libres[0]
        texto = (r.salida.texto or "").strip()[:300] or _plantilla(choque, elegida)
    except Exception:  # noqa: BLE001 — sin IA, reglas
        elegida, texto = libres[0], _plantilla(choque, libres[0])
    if not texto.startswith("⚠️"):
        texto = "⚠️ " + texto
    botones = [(CAMBIAR, f"📅 Cambiar al {dia_bonito(elegida)}"), (MANTENER, "Mantener la fecha")]
    return Respuesta(texto, botones), elegida
