"""Cifras del panel (GET /estadisticas, components/schemas/Estadisticas) y coste de la IA (POST /metrics/tokens).

Criterios (docs/PLAN_FLUJO_A.md H4):
- Actividades: eventos `publicado` o `finalizado` que tocan el periodo (los que aún no han terminado en `desde`
  y empiezan antes de `hasta`, igual que GET /eventos). `municipio` filtra por el pueblo del evento.
- `pct_importadas_auto` y `pct_otro_pueblo` van en porcentaje (0-100, un decimal); la ocupación, en 0-1 como
  dice el contrato.
- Inscripciones y asistencias cuentan personas (suma de `plazas`): inscritas = `confirmada`, `asistio` o
  `no_asistio` (no cuentan la lista de espera ni las canceladas); asistencias = `asistio`.
- `pct_otro_pueblo`: personas inscritas cuyo pueblo (el del usuario) no es el del evento, sobre las que tienen
  pueblo conocido.
- Ocupación por categoría: (plazas_totales - plazas_libres) / plazas_totales sumando los eventos con aforo.
- Solapamiento: dos actividades de pueblos distintos cuyas franjas se cruzan, si son de la misma categoría o
  alguna es un evento grande (fiestas). Sin `fecha_fin` se supone que dura DURACION_POR_DEFECTO, o el día entero
  si empieza a las 00:00 (los eventos «sin hora»). Con `municipio`, solo los pares en los que está ese pueblo.
  Sin `desde`, solo los planes que aún no han terminado (N5a): un choque que ya pasó no le sirve al moderador.
  Con `desde`, todos los del periodo (para mirar el histórico).
- Tokens: llamadas, tokens y coste por proveedor de las métricas con `ts` en el periodo (sin filtro de pueblo).
"""

from collections import defaultdict
from dataclasses import dataclass
from datetime import datetime, time, timedelta, timezone
from zoneinfo import ZoneInfo

from sqlalchemy import and_, case, func, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import Evento, Inscripcion, MetricaTokens, Usuario

ESTADOS_ACTIVIDAD = ("publicado", "finalizado")
ESTADOS_INSCRITO = ("confirmada", "asistio", "no_asistio")
CATEGORIAS_GRANDES = ("fiestas",)
DURACION_POR_DEFECTO = timedelta(hours=2)


# --- Coste de la IA -------------------------------------------------------------------------------


def precio(proveedor: str, modelo: str | None) -> tuple[float, float]:
    """(€/millón de tokens de entrada, de salida). «proveedor:modelo» manda sobre «proveedor»; si no está, 0."""
    tabla = get_settings().precios_tokens_eur_mtok
    fila = (modelo and tabla.get(f"{proveedor}:{modelo}")) or tabla.get(proveedor) or {}
    return float(fila.get("entrada", 0.0)), float(fila.get("salida", 0.0))


def coste_eur(proveedor: str, modelo: str | None, entrada: int, salida: int) -> float:
    p_entrada, p_salida = precio(proveedor, modelo)
    return (entrada * p_entrada + salida * p_salida) / 1_000_000


def tokens(db: Session, desde: datetime | None = None, hasta: datetime | None = None) -> dict:
    consulta = select(
        MetricaTokens.proveedor,
        MetricaTokens.modelo,
        func.count(),
        func.coalesce(func.sum(MetricaTokens.tokens_entrada), 0),
        func.coalesce(func.sum(MetricaTokens.tokens_salida), 0),
    ).group_by(MetricaTokens.proveedor, MetricaTokens.modelo)
    if desde:
        consulta = consulta.where(MetricaTokens.ts >= desde)
    if hasta:
        consulta = consulta.where(MetricaTokens.ts <= hasta)

    por_proveedor: dict[str, dict] = defaultdict(lambda: {"llamadas": 0, "entrada": 0, "salida": 0, "coste_eur": 0.0})
    for proveedor, modelo, llamadas, entrada, salida in db.execute(consulta):
        fila = por_proveedor[proveedor]
        fila["llamadas"] += int(llamadas)
        fila["entrada"] += int(entrada)
        fila["salida"] += int(salida)
        fila["coste_eur"] += coste_eur(proveedor, modelo, int(entrada), int(salida))
    for fila in por_proveedor.values():
        fila["coste_eur"] = round(fila["coste_eur"], 6)
    total = round(sum(f["coste_eur"] for f in por_proveedor.values()), 6)
    return {"por_proveedor": dict(sorted(por_proveedor.items())), "coste_total_eur": total}


# --- Solapamientos ------------------------------------------------------------------------------


@dataclass
class Franja:
    id: str
    titulo: str
    municipio: str
    categoria: str
    inicio: datetime
    fin: datetime


def fin_estimado(inicio: datetime, fin: datetime | None, zona: ZoneInfo) -> datetime:
    if fin is not None and fin > inicio:
        return fin
    local = inicio.astimezone(zona)
    if local.time() == time(0, 0):
        siguiente = datetime.combine(local.date() + timedelta(days=1), time(0, 0), tzinfo=zona)
        return siguiente.astimezone(timezone.utc)
    return inicio + DURACION_POR_DEFECTO


def _motivo(a: Franja, b: Franja, zona: ZoneInfo) -> str:
    dia = max(a.inicio, b.inicio).astimezone(zona).strftime("%d/%m/%Y")
    if a.categoria in CATEGORIAS_GRANDES and b.categoria not in CATEGORIAS_GRANDES:
        a, b = b, a  # «el cine coincide con las fiestas», no al revés
    texto = f"«{a.titulo}» ({a.municipio}) coincide con «{b.titulo}» ({b.municipio}) el {dia}"
    if b.categoria in CATEGORIAS_GRANDES:
        return f"{texto}: {b.categoria}, evento grande"
    return f"{texto}: misma categoría ({a.categoria}) a la misma hora"


def solapamientos(franjas: list[Franja], municipio: str | None = None) -> list[dict]:
    zona = ZoneInfo(get_settings().zona_horaria)
    ordenadas = sorted(franjas, key=lambda f: (f.inicio, f.id))
    pares = []
    for i, a in enumerate(ordenadas):
        for b in ordenadas[i + 1:]:
            if b.inicio >= a.fin:
                break  # ordenadas por inicio: ninguna de las siguientes se cruza con `a`
            if a.municipio == b.municipio:
                continue
            if a.categoria != b.categoria and not {a.categoria, b.categoria} & set(CATEGORIAS_GRANDES):
                continue
            if municipio and municipio not in (a.municipio, b.municipio):
                continue
            pares.append({"evento_a": a.id, "evento_b": b.id, "motivo": _motivo(a, b, zona)})
    return pares


# --- Panel --------------------------------------------------------------------------------------


def _utc(fecha: datetime) -> datetime:
    """SQLite devuelve las fechas sin zona (guardadas en UTC)."""
    return fecha if fecha.tzinfo else fecha.replace(tzinfo=timezone.utc)


def _pct(parte: float, total: float) -> float:
    return round(100 * parte / total, 1) if total else 0.0


def _condiciones_evento(desde: datetime | None, hasta: datetime | None, municipio: str | None) -> list:
    condiciones = [Evento.estado.in_(ESTADOS_ACTIVIDAD)]
    if desde:
        condiciones.append(func.coalesce(Evento.fecha_fin, Evento.fecha_inicio) >= desde)
    if hasta:
        condiciones.append(Evento.fecha_inicio <= hasta)
    if municipio:
        condiciones.append(Evento.municipio == municipio)
    return condiciones


def calcular(
    db: Session,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    municipio: str | None = None,
    ahora: datetime | None = None,
) -> dict:
    del_periodo = and_(*_condiciones_evento(desde, hasta, None))
    filtro = and_(*_condiciones_evento(desde, hasta, municipio))

    actividades, importadas = db.execute(
        select(func.count(), func.coalesce(func.sum(case((Evento.importado_auto, 1), else_=0)), 0)).where(filtro)
    ).one()

    pueblo_conocido = Usuario.municipio.is_not(None)
    de_otro_pueblo = and_(pueblo_conocido, Usuario.municipio != Evento.municipio)
    inscritas, asistencias, con_pueblo, otro_pueblo = db.execute(
        select(
            func.coalesce(func.sum(Inscripcion.plazas), 0),
            func.coalesce(func.sum(case((Inscripcion.estado == "asistio", Inscripcion.plazas), else_=0)), 0),
            func.coalesce(func.sum(case((pueblo_conocido, Inscripcion.plazas), else_=0)), 0),
            func.coalesce(func.sum(case((de_otro_pueblo, Inscripcion.plazas), else_=0)), 0),
        )
        .select_from(Inscripcion)
        .join(Evento, Evento.id == Inscripcion.evento_id)
        .outerjoin(Usuario, Usuario.id == Inscripcion.usuario_id)
        .where(filtro, Inscripcion.estado.in_(ESTADOS_INSCRITO))
    ).one()

    ocupacion = {}
    for categoria, totales, ocupadas in db.execute(
        select(
            Evento.categoria,
            func.sum(Evento.plazas_totales),
            func.sum(Evento.plazas_totales - func.coalesce(Evento.plazas_libres, Evento.plazas_totales)),
        )
        .where(filtro, Evento.plazas_totales > 0)
        .group_by(Evento.categoria)
        .order_by(Evento.categoria)
    ):
        if totales:
            ocupacion[categoria] = round(min(1.0, max(0.0, ocupadas / totales)), 3)

    zona = ZoneInfo(get_settings().zona_horaria)
    franjas = [
        Franja(id_, titulo, mun, cat, inicio, fin_estimado(inicio, fin, zona))
        for id_, titulo, mun, cat, inicio, fin in db.execute(
            select(
                Evento.id, Evento.titulo, Evento.municipio, Evento.categoria, Evento.fecha_inicio, Evento.fecha_fin
            ).where(del_periodo)
        )
    ]
    if desde is None:
        limite = ahora or datetime.now(timezone.utc)
        franjas = [f for f in franjas if _utc(f.fin) >= limite]

    return {
        "periodo": {
            "desde": desde.isoformat() if desde else None,
            "hasta": hasta.isoformat() if hasta else None,
        },
        "actividades": int(actividades),
        "pct_importadas_auto": _pct(int(importadas), int(actividades)),
        "inscripciones": int(inscritas),
        "asistencias": int(asistencias),
        "ocupacion_por_categoria": ocupacion,
        "pct_otro_pueblo": _pct(int(otro_pueblo), int(con_pueblo)),
        "solapamientos": solapamientos(franjas, municipio),
        "tokens": tokens(db, desde, hasta),
    }
