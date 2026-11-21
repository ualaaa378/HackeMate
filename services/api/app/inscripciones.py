"""Inscripciones (H3.2) y avisos por cambios en un evento (H3.5).

Plazas: `eventos.plazas_libres` es el contador que manda. Se toma con un UPDATE condicional
(`plazas_libres = plazas_libres - n WHERE plazas_libres >= n`) y se mira `rowcount`: la comprobación y el
descuento son una sola sentencia, así dos peticiones a la vez nunca venden la misma plaza (en PostgreSQL la
segunda espera al bloqueo de fila y vuelve a evaluar el WHERE; en SQLite las escrituras van en serie).
Nunca se lee el contador para escribirlo después.

Estado de una inscripción: igual. Se cambia con `cambiar_estado` (UPDATE … WHERE estado = <el leído>) y solo
quien consigue el cambio (`rowcount == 1`) toca las plazas. Así seis cancelaciones a la vez de la misma
inscripción devuelven una sola plaza, y seis reinscripciones a la vez descuentan una sola.

Ninguna función hace commit: lo hace la ruta, y los avisos (creados con `enviar=False`) salen después.
"""

from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import case, func, or_, select, update
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import Evento, Inscripcion, Notificacion, Usuario, ahora
from app.notificaciones import notificar
from app.serializar import fecha_iso

ACTIVAS = ("confirmada", "lista_espera")
# Quien se inscribió a un plan (aunque luego faltara): puede subir fotos al chat cuando ya ha pasado.
INSCRITOS_DEL_PLAN = ("confirmada", "asistio", "no_asistio")


def plan_terminado(evento: Evento) -> bool:
    """`finalizado`, o publicado y ya pasado (fecha_fin o, si no hay, fecha_inicio). Un cancelado no cuenta."""
    if evento.estado == "finalizado":
        return True
    return evento.estado == "publicado" and (evento.fecha_fin or evento.fecha_inicio) <= ahora()


def estuvo_inscrito(db: Session, evento: Evento, usuario: Usuario) -> bool:
    return db.scalar(
        select(Inscripcion.id).where(
            Inscripcion.evento_id == evento.id, Inscripcion.usuario_id == usuario.id,
            Inscripcion.estado.in_(INSCRITOS_DEL_PLAN),
        )
    ) is not None
DIAS = ("lun", "mar", "mié", "jue", "vie", "sáb", "dom")


def inscripcion_a_dict(i: Inscripcion, usuario: Usuario | None = None) -> dict:
    """contracts/schemas/inscripcion.json. `usuario_nombre` solo llega a quien puede verlo (el propio
    vecino, el organizador o el moderador): son las únicas personas que llegan a estas rutas. Nunca teléfonos."""
    return {
        "id": i.id,
        "evento_id": i.evento_id,
        "usuario_id": i.usuario_id,
        "usuario_nombre": usuario.nombre if usuario is not None else None,
        "estado": i.estado,
        "posicion_espera": i.posicion_espera if i.estado == "lista_espera" else None,
        "plazas": i.plazas,
        "canal": i.canal,
        "creado_en": fecha_iso(i.creado_en),
        "actualizado_en": fecha_iso(i.actualizado_en),
    }


def fecha_corta(valor: datetime) -> str:
    """«sáb 29 a las 10:00», en hora de Madrid."""
    local = valor.astimezone(ZoneInfo(get_settings().zona_horaria))
    return f"{DIAS[local.weekday()]} {local.day} a las {local:%H:%M}"


# --- Plazas ---------------------------------------------------------------------------------------


def tomar_plazas(db: Session, evento: Evento, n: int) -> bool:
    """Descuenta `n` plazas si quedan. Eventos sin límite (`plazas_totales` null): siempre True."""
    if evento.plazas_totales is None:
        return True
    resultado = db.execute(
        update(Evento)
        .where(Evento.id == evento.id, Evento.plazas_libres >= n)
        .values(plazas_libres=Evento.plazas_libres - n)
        .execution_options(synchronize_session=False)
    )
    db.expire(evento, ["plazas_libres", "actualizado_en"])
    return resultado.rowcount == 1


def devolver_plazas(db: Session, evento: Evento, n: int) -> None:
    if evento.plazas_totales is None:
        return
    db.execute(
        update(Evento)
        .where(Evento.id == evento.id, Evento.plazas_libres.is_not(None))
        .values(plazas_libres=Evento.plazas_libres + n)
        .execution_options(synchronize_session=False)
    )
    db.expire(evento, ["plazas_libres", "actualizado_en"])


def cambiar_estado(db: Session, inscripcion: Inscripcion, desde: str, **valores) -> bool:
    """Pasa `inscripcion` de `desde` a `valores` solo si en la base sigue en `desde`. True si la ha cambiado esta
    llamada. La inscripción queda expirada: al leerla se recarga con lo que hay en la base."""
    resultado = db.execute(
        update(Inscripcion)
        .where(Inscripcion.id == inscripcion.id, Inscripcion.estado == desde)
        .values(**valores)
        .execution_options(synchronize_session=False)
    )
    db.expire(inscripcion)
    return resultado.rowcount == 1


def cancelar(db: Session, evento: Evento, inscripcion: Inscripcion) -> tuple[bool, list[Notificacion]]:
    """Cancela una inscripción activa: devuelve sus plazas y promociona la lista de espera (o renumera la espera).
    (la ha cancelado esta llamada, avisos sin enviar). Si otra petición se ha adelantado (ya está cancelada o
    ya tiene la asistencia marcada), (False, []) sin tocar plazas."""
    for _ in range(3):  # si cambia de estado a la vez (p. ej. la promocionan), se reintenta con el nuevo
        leido = inscripcion.estado
        if leido not in ACTIVAS:
            return False, []
        if cambiar_estado(db, inscripcion, leido, estado="cancelada", posicion_espera=None):
            break
    else:
        return False, []
    if leido == "confirmada":
        devolver_plazas(db, evento, inscripcion.plazas)
        return True, promocionar(db, evento)
    renumerar_espera(db, evento.id)
    return True, []


def reactivar(db: Session, evento: Evento, inscripcion: Inscripcion, plazas: int, canal: str) -> bool:
    """Vuelve a apuntar a quien había cancelado: confirmada si hay plazas, si no a la lista de espera.
    False si otra petición ya la ha reactivado (y entonces no toca plazas)."""
    if not cambiar_estado(db, inscripcion, "cancelada", estado="confirmada", posicion_espera=None,
                          plazas=plazas, canal=canal):
        return False
    if not tomar_plazas(db, evento, plazas):
        posicion = siguiente_posicion(db, evento.id)
        cambiar_estado(db, inscripcion, "confirmada", estado="lista_espera", posicion_espera=posicion)
    return True


def _lista_espera(db: Session, evento_id: str) -> list[Inscripcion]:
    return list(
        db.scalars(
            select(Inscripcion)
            .where(Inscripcion.evento_id == evento_id, Inscripcion.estado == "lista_espera")
            .order_by(Inscripcion.posicion_espera.is_(None), Inscripcion.posicion_espera, Inscripcion.creado_en)
        ).all()
    )


def renumerar_espera(db: Session, evento_id: str) -> None:
    """Posiciones 1..k sin huecos, en el orden en que se apuntaron."""
    for posicion, i in enumerate(_lista_espera(db, evento_id), start=1):
        if i.posicion_espera != posicion:
            i.posicion_espera = posicion
    db.flush()


def siguiente_posicion(db: Session, evento_id: str) -> int:
    maxima = db.scalar(
        select(func.max(Inscripcion.posicion_espera)).where(
            Inscripcion.evento_id == evento_id, Inscripcion.estado == "lista_espera"
        )
    )
    return (maxima or 0) + 1


def promocionar(db: Session, evento: Evento) -> list[Notificacion]:
    """Sube a `confirmada` a los de la lista de espera que quepan, por orden (si el primero pide más plazas de
    las que hay, pasa el siguiente que sí quepa). Avisa a cada uno (`confirmacion`, sin enviar)."""
    avisos = []
    for i in _lista_espera(db, evento.id):
        if not tomar_plazas(db, evento, i.plazas):
            continue
        if not cambiar_estado(db, i, "lista_espera", estado="confirmada", posicion_espera=None):
            devolver_plazas(db, evento, i.plazas)  # otra petición la ha promocionado o cancelado antes
            continue
        usuario = db.get(Usuario, i.usuario_id)
        if usuario is not None:
            texto = (
                f"¡Buenas noticias! Se ha liberado una plaza y ya estás apuntado a «{evento.titulo}» "
                f"({fecha_corta(evento.fecha_inicio)}, {evento.municipio})."
            )
            avisos.append(notificar(db, tipo="confirmacion", texto=texto, usuario=usuario, evento_id=evento.id, enviar=False))
    db.flush()
    renumerar_espera(db, evento.id)
    return avisos


# --- Cambios en el evento (H3.5) ------------------------------------------------------------------


def texto_cambio(evento: Evento, fecha_anterior: datetime, lugar_anterior: str | None, cancelado: bool) -> str | None:
    """Texto del aviso a los inscritos, o None si no ha cambiado nada que les afecte."""
    if cancelado:
        return (
            f"Se ha cancelado «{evento.titulo}» ({fecha_corta(fecha_anterior)}, {evento.municipio}). "
            "Sentimos las molestias."
        )
    partes = []
    if evento.fecha_inicio != fecha_anterior:
        zona = ZoneInfo(get_settings().zona_horaria)
        mismo_dia = evento.fecha_inicio.astimezone(zona).date() == fecha_anterior.astimezone(zona).date()
        partes.append(f"cambia de {'hora' if mismo_dia else 'fecha'}: ahora el {fecha_corta(evento.fecha_inicio)}")
    if (evento.lugar or None) != (lugar_anterior or None) and evento.lugar:
        partes.append(f"cambia de lugar: ahora en {evento.lugar}")
    if not partes:
        return None
    return f"«{evento.titulo}» " + " y ".join(partes) + "."


def avisar_inscritos(db: Session, evento: Evento, tipo: str, texto: str) -> list[Notificacion]:
    """Un aviso (sin enviar) a cada inscrito `confirmada` o en `lista_espera`."""
    filas = db.execute(
        select(Inscripcion, Usuario)
        .join(Usuario, Usuario.id == Inscripcion.usuario_id)
        .where(Inscripcion.evento_id == evento.id, Inscripcion.estado.in_(ACTIVAS))
        .order_by(Inscripcion.creado_en)
    ).all()
    return [notificar(db, tipo=tipo, texto=texto, usuario=u, evento_id=evento.id, enviar=False) for _, u in filas]


def recalcular_plazas(db: Session) -> int:
    """N6: `plazas_libres = plazas_totales - inscritos en la plataforma` (suma de plazas de las inscripciones
    `confirmada`, las de la web y las del bot). Lo usan el seed y la migración 0009: los inscritos inventados de los
    fixtures dejan de contar. Solo planes con aforo que no han terminado (los `finalizado` guardan su ocupación
    histórica para las estadísticas). Devuelve cuántos planes cambian. No hace commit."""
    ocupadas = (
        select(func.coalesce(func.sum(Inscripcion.plazas), 0))
        .where(Inscripcion.evento_id == Evento.id, Inscripcion.estado == "confirmada")
        .scalar_subquery()
    )
    libres = case((Evento.plazas_totales - ocupadas < 0, 0), else_=Evento.plazas_totales - ocupadas)
    resultado = db.execute(
        update(Evento)
        .where(Evento.plazas_totales.is_not(None), Evento.estado != "finalizado",
               or_(Evento.plazas_libres.is_(None), Evento.plazas_libres != libres))
        .values(plazas_libres=libres)
        .execution_options(synchronize_session=False)
    )
    db.expire_all()
    return resultado.rowcount
