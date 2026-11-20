"""Panel del moderador (H4): GET /estadisticas y registro del coste de la IA (POST /metrics/tokens).

- GET /estadisticas: moderador (Bearer) o servicio interno (X-Internal-Token). Lógica en app/estadisticas.py.
- POST /metrics/tokens: solo X-Internal-Token. El bot (services/bot/app/metrics.py) manda una llamada a la IA
  por petición; el coste en euros se calcula al consultar, con la tabla de precios de la configuración.
"""

from datetime import datetime, timezone
from zoneinfo import ZoneInfo

from fastapi import APIRouter, Depends, Response
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app import estadisticas
from app.config import get_settings
from app.db import get_db
from app.modelos import MetricaTokens
from app.seguridad import exigir_moderador, exigir_token_interno

router = APIRouter(prefix="/api/v1", tags=["estadisticas"])


class MetricaTokensEntrada(BaseModel):
    """components/schemas/MetricaTokens de openapi.yaml."""

    proveedor: str = Field(min_length=1)
    modelo: str | None = None
    tarea: str = Field(min_length=1)
    tokens_entrada: int = Field(ge=0)
    tokens_salida: int = Field(ge=0)
    latencia_ms: int | None = Field(None, ge=0)
    ok: bool = True
    ts: float | None = Field(None, ge=0, le=32503680000)  # epoch en segundos (hasta el año 3000)


def _cortar(texto: str | None, columna: str) -> str | None:
    """El modelo que manda el proxy (cabecera X-Routed-Via) puede ser largo: se recorta en vez de rechazarlo."""
    return texto[: MetricaTokens.__table__.c[columna].type.length] if texto else texto


@router.post("/metrics/tokens", status_code=202, dependencies=[Depends(exigir_token_interno)])
def registrar_tokens(datos: MetricaTokensEntrada, db: Session = Depends(get_db)):
    ts = datetime.fromtimestamp(datos.ts, timezone.utc) if datos.ts is not None else datetime.now(timezone.utc)
    db.add(
        MetricaTokens(
            proveedor=_cortar(datos.proveedor.strip().lower(), "proveedor"),
            modelo=_cortar(datos.modelo, "modelo"),
            tarea=_cortar(datos.tarea, "tarea"),
            tokens_entrada=datos.tokens_entrada,
            tokens_salida=datos.tokens_salida,
            latencia_ms=datos.latencia_ms,
            ok=datos.ok,
            ts=ts,
        )
    )
    db.commit()
    return Response(status_code=202)


def _con_zona(fecha: datetime | None) -> datetime | None:
    """Una fecha sin zona se entiende en hora de Madrid; la respuesta la devuelve también en esa zona."""
    if fecha is None:
        return None
    zona = ZoneInfo(get_settings().zona_horaria)
    return (fecha if fecha.tzinfo else fecha.replace(tzinfo=zona)).astimezone(zona)


@router.get("/estadisticas", dependencies=[Depends(exigir_moderador)])
def ver_estadisticas(
    desde: datetime | None = None,
    hasta: datetime | None = None,
    municipio: str | None = None,
    db: Session = Depends(get_db),
):
    return estadisticas.calcular(db, _con_zona(desde), _con_zona(hasta), (municipio or "").strip() or None)
