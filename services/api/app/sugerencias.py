"""N7: la IA propone planes nuevos a los administradores a partir de los que tuvieron mucha participación.

1. `participacion`: los planes `publicado` o `finalizado` con más participación (ocupación, inscritos, lista de
   espera, asistencias y preguntas en el chat), como `ParticipacionPlan` del contrato.
2. `sugerir`: se los pasa a `bot POST /ai/sugerir-eventos` (N8) y devuelve sus `propuestas` como `SugerenciaPlan`.
   Si el bot no responde o no propone nada válido, propone por reglas (otra edición del plan que más participación
   tuvo). Nunca falla por la IA. No guarda nada: cada llamada calcula de nuevo.

La IA propone y una persona decide: una propuesta solo se convierte en plan con [Crear borrador], que lo deja en la
bandeja del moderador.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

import httpx
from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import CATEGORIAS, Evento, Inscripcion, MensajeEvento, Municipio

log = logging.getLogger(__name__)

ESTADOS_PLAN = ("publicado", "finalizado")
MAX_PLANES = 10  # los que se pasan a la IA (el contrato del bot admite hasta 20)
TIMEOUT_BOT_S = 30.0  # la IA puede tardar; el panel muestra «pensando…»
MESES = ("enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre")

# Transporte de httpx. None = red real; los tests ponen un httpx.MockTransport.
_transporte: httpx.BaseTransport | None = None


def _puntuacion(p: dict) -> float:
    return 3 * (p["ocupacion"] or 0) + 0.5 * p["lista_espera"] + 0.3 * p["preguntas_chat"] + 0.05 * p["inscritos"]


def participacion(db: Session, municipio: str | None = None, maximo: int = MAX_PLANES) -> list[dict]:
    """Los `maximo` planes con más participación, de más a menos. Los que no tuvieron ninguna no cuentan."""
    inscripciones = (
        select(
            Inscripcion.evento_id.label("evento_id"),
            func.coalesce(func.sum(case((Inscripcion.estado.in_(("confirmada", "asistio", "no_asistio")),
                                         Inscripcion.plazas), else_=0)), 0).label("inscritos"),
            func.coalesce(func.sum(case((Inscripcion.estado == "lista_espera", Inscripcion.plazas), else_=0)),
                          0).label("lista_espera"),
            func.coalesce(func.sum(case((Inscripcion.estado == "asistio", Inscripcion.plazas), else_=0)),
                          0).label("asistencias"),
        )
        .group_by(Inscripcion.evento_id)
        .subquery()
    )
    preguntas = (
        select(MensajeEvento.evento_id.label("evento_id"), func.count().label("preguntas"))
        .where(MensajeEvento.tipo == "pregunta")
        .group_by(MensajeEvento.evento_id)
        .subquery()
    )
    consulta = (
        select(Evento, inscripciones.c.inscritos, inscripciones.c.lista_espera, inscripciones.c.asistencias,
               preguntas.c.preguntas)
        .outerjoin(inscripciones, inscripciones.c.evento_id == Evento.id)
        .outerjoin(preguntas, preguntas.c.evento_id == Evento.id)
        .where(Evento.estado.in_(ESTADOS_PLAN))
    )
    if municipio:
        consulta = consulta.where(Evento.municipio == municipio)

    planes = []
    for evento, inscritos, lista_espera, asistencias, n_preguntas in db.execute(consulta):
        inscritos, lista_espera = int(inscritos or 0), int(lista_espera or 0)
        n_preguntas, asistencias = int(n_preguntas or 0), int(asistencias or 0)
        if not (inscritos or lista_espera or n_preguntas):
            continue
        ocupacion = None
        if evento.plazas_totales:
            # N5a: las plazas ocupadas del plan (como «Ocupación por tipo de plan» del panel), que en los planes ya
            # hechos incluyen a quien se apuntó fuera de la plataforma; nunca menos que los inscritos aquí.
            libres = evento.plazas_libres if evento.plazas_libres is not None else evento.plazas_totales
            ocupadas = max(inscritos, evento.plazas_totales - libres)
            ocupacion = round(min(1.0, ocupadas / evento.plazas_totales), 3)
        planes.append({
            "evento_id": evento.id,
            "titulo": evento.titulo,
            "categoria": evento.categoria,
            "municipio": evento.municipio,
            "fecha_inicio": evento.fecha_inicio.isoformat(),
            "estado": evento.estado,
            "plazas_totales": evento.plazas_totales,
            "inscritos": inscritos,
            "lista_espera": lista_espera,
            "asistencias": asistencias,
            "ocupacion": ocupacion,
            "preguntas_chat": n_preguntas,
        })
    planes.sort(key=lambda p: (-_puntuacion(p), p["fecha_inicio"], p["evento_id"]))
    return planes[:maximo]


def _cifras(p: dict) -> str:
    partes = []
    if p["ocupacion"] is not None and p["plazas_totales"]:
        ocupadas = round(p["ocupacion"] * p["plazas_totales"])
        if p["ocupacion"] >= 1:
            partes.append(f"se llenó ({p['plazas_totales']} de {p['plazas_totales']})")
        else:
            partes.append(f"se ocupó el {round(100 * p['ocupacion'])} % ({ocupadas} de {p['plazas_totales']} plazas)")
    elif p["inscritos"]:
        partes.append(f"se apuntaron {p['inscritos']} personas")
    if p["lista_espera"]:
        partes.append(f"hubo {p['lista_espera']} en lista de espera")
    if p["preguntas_chat"]:
        partes.append(f"{p['preguntas_chat']} preguntas en el chat")
    if not partes:
        return "tuvo participación"
    return partes[0] if len(partes) == 1 else ", ".join(partes[:-1]) + " y " + partes[-1]


def _fecha_aproximada(p: dict, ahora: datetime) -> str:
    """El mismo mes, el próximo año en que aún no haya pasado. Solo orientativa: el moderador pone la fecha."""
    inicio = datetime.fromisoformat(p["fecha_inicio"]).astimezone(ZoneInfo(get_settings().zona_horaria))
    ano = ahora.year if inicio.month > ahora.month else ahora.year + 1
    return f"en {MESES[inicio.month - 1]} de {ano}"


def por_reglas(planes: list[dict], maximo: int, ahora: datetime) -> list[dict]:
    """Sin IA: otra edición de los planes que más participación tuvieron."""
    return [
        {
            "titulo": f"Otra edición de «{p['titulo']}»"[:120],
            "descripcion": None,
            "categoria": p["categoria"],
            "municipio": p["municipio"],
            "fecha_aproximada": _fecha_aproximada(p, ahora),
            "motivo": f"«{p['titulo']}» {_cifras(p)}",
            "basado_en": [p["evento_id"]],
        }
        for p in planes[:maximo]
    ]


def _valida(db: Session, propuesta: dict, ids: set[str]) -> dict | None:
    """La propuesta del bot como SugerenciaPlan, o None si no cuadra (pueblo o categoría que no existen…)."""
    try:
        titulo = str(propuesta.get("titulo") or "").strip()[:120]
        motivo = str(propuesta.get("motivo") or "").strip()
        categoria, municipio = propuesta.get("categoria"), propuesta.get("municipio")
        if not titulo or not motivo or categoria not in CATEGORIAS or db.get(Municipio, municipio) is None:
            return None
        basado_en = [i for i in propuesta.get("basado_en") or [] if i in ids]
        return {
            "titulo": titulo,
            "descripcion": propuesta.get("descripcion") or None,
            "categoria": categoria,
            "municipio": municipio,
            "fecha_aproximada": propuesta.get("fecha_aproximada") or None,
            "motivo": motivo,
            "basado_en": basado_en,
        }
    except Exception:  # noqa: BLE001 — una propuesta rara se descarta, no tumba la respuesta
        return None


def _pedir_al_bot(planes: list[dict], maximo: int) -> tuple[list[dict], str] | None:
    ajustes = get_settings()
    if not ajustes.bot_url:
        return None
    try:
        with httpx.Client(transport=_transporte, timeout=TIMEOUT_BOT_S) as cliente:
            r = cliente.post(
                ajustes.bot_url.rstrip("/") + "/ai/sugerir-eventos",
                json={"planes": planes, "maximo": maximo},
                headers={"X-Internal-Token": ajustes.internal_token},
            )
        if r.status_code >= 400:
            log.info("sugerencias: el bot respondió %s", r.status_code)
            return None
        datos = r.json()
        return list(datos.get("propuestas") or []), str(datos.get("proveedor_ia") or "ia")
    except Exception as e:  # noqa: BLE001 — bot caído o respuesta rara: se propone por reglas
        log.info("sugerencias: el bot no responde (%s)", type(e).__name__)
        return None


def sugerir(db: Session, ahora: datetime, municipio: str | None = None, limite: int = 3) -> dict:
    """Respuesta de GET /admin/sugerencias (components/schemas/Sugerencias)."""
    planes = participacion(db, municipio)
    if not planes:
        return {"items": [], "basado_en": [], "proveedor_ia": "reglas"}
    ids = {p["evento_id"] for p in planes}
    del_bot = _pedir_al_bot(planes, limite)
    if del_bot is not None:
        propuestas, proveedor = del_bot
        validas = [v for v in (_valida(db, p, ids) for p in propuestas) if v is not None][:limite]
        if validas:
            return {"items": validas, "basado_en": planes, "proveedor_ia": proveedor}
    return {"items": por_reglas(planes, limite, ahora), "basado_en": planes, "proveedor_ia": "reglas"}
