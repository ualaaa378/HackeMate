"""Posibles duplicados al importar (H2.2): mismo municipio, fecha cercana y título parecido.

El duplicado exacto (mismo origen.url) se resuelve en la ruta de importar; esto es para el mismo evento
llegado por otro canal o con otra URL. Solo se avisa: la decisión la toma una persona.
"""

from datetime import datetime, timedelta
from difflib import SequenceMatcher

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import Evento
from app.texto import normalizar

UMBRAL_SIMILITUD = 0.8
MARGEN_FECHA = timedelta(days=1)
ESTADOS_IGNORADOS = ("rechazado", "cancelado", "archivado")


def similitud_titulos(a: str, b: str) -> float:
    return SequenceMatcher(None, normalizar(a), normalizar(b)).ratio()


def buscar_posible_duplicado(
    db: Session, titulo: str, fecha_inicio: datetime, municipio: str, excluir_id: str | None = None
) -> Evento | None:
    """El evento del mismo municipio con fecha_inicio a ±1 día y título más parecido (>= umbral)."""
    consulta = select(Evento).where(
        Evento.municipio == municipio,
        Evento.fecha_inicio >= fecha_inicio - MARGEN_FECHA,
        Evento.fecha_inicio <= fecha_inicio + MARGEN_FECHA,
        Evento.estado.not_in(ESTADOS_IGNORADOS),
    )
    if excluir_id is not None:
        consulta = consulta.where(Evento.id != excluir_id)
    mejor: Evento | None = None
    mejor_ratio = UMBRAL_SIMILITUD
    for candidato in db.scalars(consulta.order_by(Evento.creado_en)).all():
        ratio = similitud_titulos(titulo, candidato.titulo)
        if ratio >= mejor_ratio and (mejor is None or ratio > mejor_ratio):
            mejor, mejor_ratio = candidato, ratio
    return mejor
