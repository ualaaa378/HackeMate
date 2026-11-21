"""N7: GET /admin/sugerencias y POST /admin/sugerencias/borrador (lógica en app/sugerencias.py).

[Crear borrador] deja el plan en la bandeja (`en_revision`): el moderador ajusta lo que haga falta y lo aprueba.
Al aprobarlo se avisa a los interesados como con cualquier plan nuevo (A10).
"""

from datetime import datetime, timezone
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Query
from pydantic import BaseModel, ConfigDict, Field, StringConstraints
from sqlalchemy.orm import Session

from app import sugerencias
from app.db import get_db
from app.errores import ErrorApi
from app.modelos import Evento
from app.rutas.eventos import _comprobar_fechas, _con_zona, _ficha
from app.rutas.importar import _municipio
from app.seguridad import exigir_moderador

router = APIRouter(prefix="/api/v1/admin", tags=["admin"], dependencies=[Depends(exigir_moderador)])

Texto = Annotated[str, StringConstraints(strip_whitespace=True, min_length=1)]


def reloj() -> datetime:
    """Separado para que los tests fijen «ahora»."""
    return datetime.now(timezone.utc)


class BorradorSugerencia(BaseModel):
    """components/schemas/BorradorSugerencia (SugerenciaPlan + fecha_inicio)."""

    model_config = ConfigDict(extra="ignore")

    titulo: Annotated[str, StringConstraints(strip_whitespace=True, min_length=1, max_length=120)]
    descripcion: str | None = None
    categoria: Literal["deportiva", "cultural", "fiestas", "gastronomia", "ludica", "comercio"]
    municipio: Texto
    fecha_aproximada: str | None = None
    motivo: Texto
    basado_en: list[str] = Field(default_factory=list)
    fecha_inicio: datetime


@router.get("/sugerencias")
def ver_sugerencias(
    municipio: str | None = None,
    limite: int = Query(3, ge=1, le=3),
    db: Session = Depends(get_db),
):
    return sugerencias.sugerir(db, reloj(), municipio=municipio, limite=limite)


@router.post("/sugerencias/borrador", status_code=201)
def crear_borrador(datos: BorradorSugerencia, revisor: str = Depends(exigir_moderador), db: Session = Depends(get_db)):
    municipio = _municipio(db, datos.municipio)
    if municipio is None:
        raise ErrorApi(422, "municipio_no_encontrado", "Ese municipio no está en la plataforma", {"campo": "municipio"})
    base = db.get(Evento, datos.basado_en[0]) if datos.basado_en else None
    origen = f"«{base.titulo}»" if base is not None else "los planes con más participación"
    evento = Evento(
        titulo=datos.titulo,
        descripcion=datos.descripcion or datos.motivo,
        categoria=datos.categoria,
        municipio=municipio.nombre,
        lat=municipio.lat,
        lon=municipio.lon,
        fecha_inicio=_con_zona(datos.fecha_inicio),
        etiquetas=list(base.etiquetas or []) if base is not None else [],
        estado="en_revision",
        origen_canal="panel",
        motivo_moderacion=f"Propuesto por la IA a partir de {origen}: {datos.motivo}"[:500],
    )
    _comprobar_fechas(evento)
    db.add(evento)
    db.commit()
    return _ficha(db, evento, privados=True)
