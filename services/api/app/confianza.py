"""Revisión a mano o automática de los publicadores: DNI/NIE del responsable, actividad reciente y reglas
del nivel 2 (las mismas que `apps/web/src/admin/confianza.ts`).

- `actividad`: se cuenta por `Evento.creado_en` (cuándo se propuso el plan). «Aprobados» son los eventos que
  llegaron a publicarse y siguen contando aunque ya hayan pasado (`publicado` y `finalizado`).
- Nivel 2 = revisión automática. Solo lo da un moderador y solo si se cumplen todas las reglas; la subida
  automática por aprobaciones (`app/moderacion.registrar_aprobacion`) llega como mucho al nivel 1.
"""

import re
from collections.abc import Iterable
from datetime import datetime, timedelta, timezone

from sqlalchemy import and_, case, func, select, type_coerce
from sqlalchemy.orm import Session

from app.modelos import Evento, FechaUTC, Publicador

VENTANA_DIAS = 60
PLANES_MINIMOS = 3
DIAS_INACTIVIDAD = 90
ESTADOS_APROBADOS = ("publicado", "finalizado")

_LETRAS_DNI = "TRWAGMYFPDXBNJZSQVHLCKE"
_RE_DNI = re.compile(r"^(\d{8})([A-Z])$")
_RE_NIE = re.compile(r"^([XYZ])(\d{7})([A-Z])$")


def normalizar_dni(dni: str) -> str | None:
    """DNI (8 cifras + letra) o NIE (X/Y/Z + 7 cifras + letra) con la letra de control correcta.
    Devuelve el documento en mayúsculas y sin espacios ni guiones, o None si no es válido."""
    limpio = re.sub(r"[\s.-]", "", dni or "").upper()
    if m := _RE_DNI.match(limpio):
        numero, letra = int(m.group(1)), m.group(2)
    elif m := _RE_NIE.match(limpio):
        numero, letra = "XYZ".index(m.group(1)) * 10_000_000 + int(m.group(2)), m.group(3)
    else:
        return None
    return limpio if _LETRAS_DNI[numero % 23] == letra else None


def actividad_vacia() -> dict:
    return {"planes_60_dias": 0, "rechazados_60_dias": 0, "ultimo_plan": None}


def actividad_por_publicador(
    db: Session, ids: Iterable[str], ahora: datetime | None = None
) -> dict[str, dict]:
    """Una sola consulta agregada para todos los publicadores de la página.
    `ultimo_plan` es un datetime (el serializador lo pasa a ISO) o None."""
    ids = list(ids)
    if not ids:
        return {}
    ahora = ahora or datetime.now(timezone.utc)
    desde = ahora - timedelta(days=VENTANA_DIAS)
    aprobado = Evento.estado.in_(ESTADOS_APROBADOS)
    filas = db.execute(
        select(
            Evento.publicador_id,
            func.sum(case((and_(aprobado, Evento.creado_en >= desde), 1), else_=0)),
            func.sum(case((and_(Evento.estado == "rechazado", Evento.creado_en >= desde), 1), else_=0)),
            type_coerce(func.max(case((aprobado, Evento.creado_en), else_=None)), FechaUTC()),
        )
        .where(Evento.publicador_id.in_(ids))
        .group_by(Evento.publicador_id)
    ).all()
    resultado = {id: actividad_vacia() for id in ids}
    for publicador_id, planes, rechazados, ultimo in filas:
        resultado[publicador_id] = {
            "planes_60_dias": int(planes or 0),
            "rechazados_60_dias": int(rechazados or 0),
            "ultimo_plan": ultimo,
        }
    return resultado


def tiene_datos_responsable(publicador: Publicador) -> bool:
    r = publicador.responsable or {}
    return bool(r.get("dni") and r.get("residencia"))


def reglas_nivel_2_que_faltan(
    db: Session, publicador: Publicador, ahora: datetime | None = None
) -> list[str]:
    """Lista vacía si puede pasar a revisión automática; si no, las reglas que fallan
    (`identidad_verificada`, `planes_60_dias`, `rechazados_60_dias`, `ultimo_plan`)."""
    ahora = ahora or datetime.now(timezone.utc)
    a = actividad_por_publicador(db, [publicador.id], ahora)[publicador.id]
    faltan = []
    if not (tiene_datos_responsable(publicador) and publicador.identidad_verificada):
        faltan.append("identidad_verificada")
    if a["planes_60_dias"] < PLANES_MINIMOS:
        faltan.append("planes_60_dias")
    if a["rechazados_60_dias"] > 0:
        faltan.append("rechazados_60_dias")
    if a["ultimo_plan"] is None or a["ultimo_plan"] < ahora - timedelta(days=DIAS_INACTIVIDAD):
        faltan.append("ultimo_plan")
    return faltan
