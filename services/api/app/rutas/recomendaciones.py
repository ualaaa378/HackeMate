"""GET /recomendaciones: eventos recomendados con motivo legible (lógica en app/recomendador.py).

Quién puede pedirlas (openapi: bearer o interno):
- X-Internal-Token (el bot, para mandar la recomendación por WhatsApp/Telegram): cualquier `usuario_id`.
- Bearer: las suyas; un moderador, las de cualquiera. Otro usuario -> 403.
"""

import uuid
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, Header, Query
from sqlalchemy.orm import Session

from app.db import get_db
from app.errores import ErrorApi
from app.modelos import Usuario
from app.recomendador import recomendar
from app.seguridad import es_servicio_interno, usuario_actual
from app.serializar import eventos_a_dict

router = APIRouter(prefix="/api/v1", tags=["recomendaciones"])


def reloj() -> datetime:
    """Separado para que los tests fijen «ahora» (el seed tiene fechas reales)."""
    return datetime.now(timezone.utc)


@router.get("/recomendaciones")
def recomendaciones(
    usuario_id: uuid.UUID,
    limite: int = Query(5, ge=1, le=20),
    x_internal_token: str | None = Header(None),
    sesion: Usuario | None = Depends(usuario_actual),
    db: Session = Depends(get_db),
):
    usuario_id = str(usuario_id)
    if not es_servicio_interno(x_internal_token):
        if sesion is None:
            raise ErrorApi(401, "no_autenticado", "Hace falta iniciar sesión (o la cabecera X-Internal-Token)")
        if sesion.id != usuario_id and sesion.rol != "moderador":
            raise ErrorApi(403, "prohibido", "Solo puedes ver tus propias recomendaciones")
    usuario = db.get(Usuario, usuario_id)
    if usuario is None:
        raise ErrorApi(404, "usuario_no_encontrado", "No existe ese usuario")

    lista = recomendar(db, usuario, reloj(), limite)
    eventos = eventos_a_dict(db, [r.evento for r in lista])
    return {
        "items": [
            {"evento": evento, "puntuacion": r.puntuacion, "motivo": r.motivo, "distancia_km": r.distancia_km}
            for r, evento in zip(lista, eventos)
        ]
    }
