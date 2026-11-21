"""Tareas programadas: lo que la plataforma hace sola, sin que nadie escriba (pedido por Francisco, sáb 21/11).

Una vuelta cada `TAREAS_CADA_MIN` minutos (app/main.py). Cada aviso sale una sola vez por persona: antes de crearlo
se mira si ya existe uno igual (mismo usuario, plan y marca al principio del texto). Todos pasan por
`notificar` → bot `POST /notify`, como el resto de avisos, y se reintentan si el bot está caído.

1. **Recordatorio 24 h antes** (`anuncio`, con `evento_id`): a quien está `confirmada` en un plan publicado que
   empieza dentro de 22–26 h. «⏰ Mañana a las 9:00 tienes «Ruta…» en Velefique (Plaza de la iglesia).»
2. **«¿Qué tal fue?»** (`anuncio`, con `evento_id`): a quien fue (`confirmada` o `asistio`) a un plan que terminó
   en las últimas 24 h. El bot pone botones y deja la respuesta como comentario del plan.
4. **«Quedan pocas plazas»** (`recomendacion`, con `evento_id`: el bot pone [Apuntarme]; solo a quien acepta avisos):
   un plan publicado de los próximos 14 días al que le quedan pocas plazas (`POCAS_PLAZAS`: 3 o menos, o el 20 % o
   menos del aforo) avisa una vez a quien le interesa (mismos criterios que el aviso de plan nuevo, A10) y aún no está
   apuntado. «⏳ Quedan 2 plazas para «Ruta…» en Velefique, el sábado 28 a las 9:00. Te gustan las rutas.»
3. **Resumen semanal por pueblo** (`recomendacion`, sin `evento_id`; solo a quien acepta avisos, D1): el día y hora
   de `RESUMEN_DIA_SEMANA`/`RESUMEN_HORA`, los planes de los próximos 7 días en su pueblo (o en su pueblo
   favorito, o cerca de donde vive), como mucho 5.
"""

import logging
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from sqlalchemy import or_, select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import Evento, Inscripcion, Notificacion, Usuario
from app.notificaciones import enviar_avisos, notificar
from app.recomendador import ESTADOS_HISTORIAL, RADIO_POR_DEFECTO_KM, _origen, pueblos_favoritos
from app.rutas.publico import distancia_km

log = logging.getLogger(__name__)

MARCA_RECORDATORIO = "⏰"
MARCA_QUE_TAL = "¿Qué tal fue"  # el bot la reconoce para poner los botones de valoración
MARCA_RESUMEN = "📅 Esta semana"
MARCA_POCAS_PLAZAS = "⏳"  # «⏳ Quedan 3 plazas…» o «⏳ Queda 1 plaza…»
POCAS_PLAZAS_MIN, POCAS_PLAZAS_PCT = 3, 0.2
POCAS_PLAZAS_DIAS = 14
DURACION_POR_DEFECTO = timedelta(hours=3)  # si el plan no tiene fecha_fin
MAX_PLANES_RESUMEN = 5
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _local(fecha: datetime) -> datetime:
    return fecha.astimezone(ZoneInfo(get_settings().zona_horaria))


def _ya_avisado(db: Session, usuario_id: str, evento_id: str | None, marca: str, desde: datetime | None = None) -> bool:
    consulta = select(Notificacion.id).where(Notificacion.usuario_id == usuario_id,
                                             Notificacion.texto.startswith(marca))
    if evento_id is not None:
        consulta = consulta.where(Notificacion.evento_id == evento_id)
    if desde is not None:
        consulta = consulta.where(Notificacion.creado_en >= desde)
    return db.scalar(consulta.limit(1)) is not None


def _inscritos(db: Session, evento: Evento, estados: tuple[str, ...]) -> list[Usuario]:
    return list(db.scalars(
        select(Usuario).join(Inscripcion, Inscripcion.usuario_id == Usuario.id)
        .where(Inscripcion.evento_id == evento.id, Inscripcion.estado.in_(estados))
    ).all())


def recordatorios(db: Session, ahora: datetime) -> list[Notificacion]:
    eventos = db.scalars(select(Evento).where(
        Evento.estado == "publicado",
        Evento.fecha_inicio >= ahora + timedelta(hours=22), Evento.fecha_inicio <= ahora + timedelta(hours=26),
    )).all()
    avisos = []
    for evento in eventos:
        local = _local(evento.fecha_inicio)
        cuando = "Mañana" if (local.date() - _local(ahora).date()).days == 1 else f"El {DIAS[local.weekday()]}"
        donde = evento.municipio + (f" ({evento.lugar})" if getattr(evento, "lugar", None) else "")
        texto = (f"{MARCA_RECORDATORIO} {cuando} a las {local:%H:%M} tienes «{evento.titulo}» en {donde}. "
                 "¡Nos vemos allí! Si al final no puedes ir, escríbeme «desapúntame» y dejas la plaza a otra persona.")
        for usuario in _inscritos(db, evento, ("confirmada",)):
            if not _ya_avisado(db, usuario.id, evento.id, MARCA_RECORDATORIO):
                avisos.append(notificar(db, tipo="anuncio", texto=texto, usuario=usuario, evento_id=evento.id,
                                        enviar=False))
    return avisos


def que_tal_fue(db: Session, ahora: datetime) -> list[Notificacion]:
    eventos = db.scalars(select(Evento).where(
        Evento.estado.in_(("publicado", "finalizado")),
        Evento.fecha_inicio >= ahora - timedelta(days=2), Evento.fecha_inicio <= ahora,
    )).all()
    avisos = []
    for evento in eventos:
        fin = evento.fecha_fin or (evento.fecha_inicio + DURACION_POR_DEFECTO)
        if not (ahora - timedelta(hours=24) <= fin <= ahora):
            continue  # aún no ha terminado, o hace más de un día
        texto = (f"{MARCA_QUE_TAL} «{evento.titulo}»? 😊 Cuéntamelo con un botón o en un mensaje: se lo paso a "
                 "quienes lo organizaron para que el próximo salga aún mejor.")
        for usuario in _inscritos(db, evento, ("confirmada", "asistio")):
            if not _ya_avisado(db, usuario.id, evento.id, MARCA_QUE_TAL):
                avisos.append(notificar(db, tipo="anuncio", texto=texto, usuario=usuario, evento_id=evento.id,
                                        enviar=False))
    return avisos


def _pueblo_de(db: Session, usuario: Usuario) -> str | None:
    if usuario.municipio:
        return usuario.municipio
    filas = db.execute(
        select(Inscripcion.evento_id, Inscripcion.estado, Evento.municipio)
        .join(Evento, Evento.id == Inscripcion.evento_id).where(Inscripcion.usuario_id == usuario.id)
    ).all()
    por_pueblo: dict[str, set[str]] = {}
    for evento_id, estado, municipio in filas:
        if estado in ESTADOS_HISTORIAL:
            por_pueblo.setdefault(municipio, set()).add(evento_id)
    favoritos = pueblos_favoritos(por_pueblo)
    return max(favoritos, key=favoritos.get) if favoritos else None


def resumen_semanal(db: Session, ahora: datetime) -> list[Notificacion]:
    ajustes = get_settings()
    local = _local(ahora)
    if local.weekday() != ajustes.resumen_dia_semana or local.hour < ajustes.resumen_hora:
        return []
    inicio_semana = (local - timedelta(days=local.weekday())).replace(hour=0, minute=0, second=0, microsecond=0)
    proximos = db.scalars(select(Evento).where(
        Evento.estado == "publicado", Evento.fecha_inicio >= ahora, Evento.fecha_inicio <= ahora + timedelta(days=7),
    ).order_by(Evento.fecha_inicio)).all()
    if not proximos:
        return []
    avisos = []
    usuarios = db.scalars(select(Usuario).where(
        Usuario.acepta_avisos.is_(True), or_(Usuario.telefono.is_not(None), Usuario.telegram_id.is_not(None)),
    )).all()
    for usuario in usuarios:
        if _ya_avisado(db, usuario.id, None, MARCA_RESUMEN, desde=inicio_semana.astimezone(ahora.tzinfo)):
            continue
        pueblo = _pueblo_de(db, usuario)
        origen = _origen(db, usuario)
        radio = usuario.radio_km or RADIO_POR_DEFECTO_KM
        suyos = [e for e in proximos if (pueblo and e.municipio == pueblo) or (
            origen and distancia_km(origen[0], origen[1], e.lat, e.lon) <= radio)][:MAX_PLANES_RESUMEN]
        if not suyos:
            continue
        lineas = [f"• {DIAS[_local(e.fecha_inicio).weekday()].capitalize()} {_local(e.fecha_inicio):%d/%m %H:%M} · "
                  f"{e.titulo} ({e.municipio})" for e in suyos]
        zona = f"en {pueblo} y alrededores" if pueblo else "cerca de ti"
        texto = (f"{MARCA_RESUMEN} {zona}:\n" + "\n".join(lineas) +
                 "\n\nEscríbeme el nombre de uno para apuntarte o «¿qué hay este finde?» para ver más.")
        avisos.append(notificar(db, tipo="recomendacion", texto=texto, usuario=usuario, enviar=False))
    return avisos


def _pocas(evento: Evento) -> bool:
    if not evento.plazas_totales or evento.plazas_libres is None or evento.plazas_libres <= 0:
        return False
    return evento.plazas_libres <= max(POCAS_PLAZAS_MIN, int(evento.plazas_totales * POCAS_PLAZAS_PCT))


def pocas_plazas(db: Session, ahora: datetime) -> list[Notificacion]:
    """Idea 7: a quien le interesa un plan casi lleno y no se ha apuntado, una vez por persona y plan."""
    from app.avisos_planes import _cuando, interesa

    eventos = [e for e in db.scalars(select(Evento).where(
        Evento.estado == "publicado", Evento.fecha_inicio >= ahora + timedelta(hours=2),
        Evento.fecha_inicio <= ahora + timedelta(days=POCAS_PLAZAS_DIAS),
    )).all() if _pocas(e)]
    if not eventos:
        return []
    usuarios = db.scalars(select(Usuario).where(Usuario.acepta_avisos.is_(True)).order_by(Usuario.creado_en)).all()
    avisos = []
    for evento in eventos:
        quedan = "Queda 1 plaza" if evento.plazas_libres == 1 else f"Quedan {evento.plazas_libres} plazas"
        for usuario in usuarios:
            if _ya_avisado(db, usuario.id, evento.id, MARCA_POCAS_PLAZAS):
                continue
            motivo = interesa(db, usuario, evento, ahora, repetir=True)
            if motivo is None:
                continue
            texto = (f"{MARCA_POCAS_PLAZAS} {quedan} para «{evento.titulo}» en {evento.municipio}, {_cuando(evento)}. {motivo}. "
                     "Si te apetece, apúntate antes de que se acaben.")
            avisos.append(notificar(db, tipo="recomendacion", texto=texto, usuario=usuario, evento_id=evento.id,
                                    enviar=False))
    return avisos


def ciclo_tareas(fabrica=None, ahora: datetime | None = None) -> int:
    """Una vuelta: crea los avisos que toquen, hace commit y los envía. No lanza nunca. Devuelve cuántos salen."""
    from app.modelos import ahora as ahora_utc

    try:
        if fabrica is None:
            from app.db import _fabrica_sesiones

            fabrica = _fabrica_sesiones()
        momento = ahora or ahora_utc()
        with fabrica() as db:
            avisos = (recordatorios(db, momento) + que_tal_fue(db, momento) + resumen_semanal(db, momento)
                      + pocas_plazas(db, momento))
            db.commit()
            ids = [n.id for n in avisos if n is not None and n.estado_envio == "pendiente"]
            if avisos:
                log.info("Tareas programadas: %s avisos nuevos", len(avisos))
            return enviar_avisos(db.get_bind(), ids) if ids else 0
    except Exception:  # noqa: BLE001 — una tarea de fondo nunca tumba la API
        log.exception("fallo en las tareas programadas")
        return 0
