"""Compartir coche (idea 6 de las tareas nocturnas, 22/11).

Cuando dos o más vecinos del mismo pueblo están apuntados (`confirmada`) a un plan de **otro** pueblo, la tarea
programada les propone ir juntos. Doble consentimiento: el contacto solo se pasa entre quienes dicen que sí, y
solo cuando hay al menos dos. Quien dice que no, o no contesta, nunca aparece en ningún mensaje.

- Propuesta (`anuncio` con `evento_id`, empieza por `MARCA_COCHE`): el bot pone [Sí, vamos juntos] [No, gracias].
- Respuesta: `POST /api/v1/eventos/{id}/coche` (el bot con X-Internal-Token y `usuario_id`, o el vecino con sesión).
- Al decir que sí, si ya hay otro vecino del mismo pueblo que dijo que sí, se avisa a los dos con el contacto.

Ninguna función hace commit: lo hace la ruta o la tarea programada.
"""

from datetime import datetime, timedelta

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.modelos import CocheCompartido, Evento, Inscripcion, Notificacion, Usuario
from app.notificaciones import notificar

MARCA_COCHE = "🚗"  # el bot la reconoce para poner los botones de sí/no
MARCA_COCHE_HECHO = "✅🚗"  # no empieza por MARCA_COCHE: este aviso no lleva botones de sí/no
COCHE_DIAS = 7  # planes de la próxima semana
COCHE_HORAS_ANTES = 3  # con menos margen ya no da tiempo a organizarse


def _con_destino(u: Usuario) -> bool:
    return bool(u.telefono or u.telegram_id)


def _vecinos_del_pueblo(db: Session, evento: Evento, municipio: str) -> list[Usuario]:
    """Apuntados con plaza a `evento` que viven en `municipio` (distinto del pueblo del plan)."""
    return list(db.scalars(
        select(Usuario).join(Inscripcion, Inscripcion.usuario_id == Usuario.id)
        .where(Inscripcion.evento_id == evento.id, Inscripcion.estado == "confirmada", Usuario.municipio == municipio)
        .order_by(Inscripcion.creado_en)
    ).all())


def _respuesta(db: Session, evento_id: str, usuario_id: str) -> CocheCompartido | None:
    return db.get(CocheCompartido, (evento_id, usuario_id))


def contacto_visible(u: Usuario) -> str:
    """Lo que ve el otro vecino. Solo se usa tras el «sí» de los dos."""
    if u.telefono:
        return f"{u.nombre} ({u.telefono})"
    return f"{u.nombre} (escríbele por el chat del plan)"


def proponer(db: Session, ahora: datetime) -> list[Notificacion]:
    """Tarea programada: una propuesta por vecino y plan, cuando hay 2+ del mismo pueblo apuntados."""
    from app.avisos_planes import _cuando

    eventos = db.scalars(select(Evento).where(
        Evento.estado == "publicado",
        Evento.fecha_inicio >= ahora + timedelta(hours=COCHE_HORAS_ANTES),
        Evento.fecha_inicio <= ahora + timedelta(days=COCHE_DIAS),
    )).all()
    avisos: list[Notificacion] = []
    for evento in eventos:
        pueblos = db.scalars(
            select(Usuario.municipio).join(Inscripcion, Inscripcion.usuario_id == Usuario.id)
            .where(Inscripcion.evento_id == evento.id, Inscripcion.estado == "confirmada",
                   Usuario.municipio.is_not(None), Usuario.municipio != evento.municipio)
            .distinct()
        ).all()
        for pueblo in pueblos:
            vecinos = [u for u in _vecinos_del_pueblo(db, evento, pueblo) if _con_destino(u)]
            if len(vecinos) < 2:
                continue
            for u in vecinos:
                if _respuesta(db, evento.id, u.id) is not None:
                    continue
                db.add(CocheCompartido(evento_id=evento.id, usuario_id=u.id, respuesta="pendiente"))
                otros = len(vecinos) - 1
                quien = "otro vecino" if otros == 1 else f"otros {otros} vecinos"
                texto = (f"{MARCA_COCHE} Hay {quien} de {pueblo} apuntados a «{evento.titulo}» en {evento.municipio}, "
                         f"{_cuando(evento)}. ¿Os apetece ir juntos en coche? Solo os paso el contacto si los dos "
                         "decís que sí.")
                avisos.append(notificar(db, tipo="anuncio", texto=texto, usuario=u, evento_id=evento.id, enviar=False))
    return avisos


class CocheNoDisponible(Exception):
    pass


def responder(db: Session, evento: Evento, usuario: Usuario, acepta: bool) -> tuple[dict, list[Notificacion]]:
    """Guarda el sí o el no. Con un sí, empareja con los del mismo pueblo que ya dijeron que sí.
    Devuelve (cuerpo de la respuesta, avisos sin enviar para los demás)."""
    inscrito = db.scalar(select(Inscripcion.id).where(
        Inscripcion.evento_id == evento.id, Inscripcion.usuario_id == usuario.id, Inscripcion.estado == "confirmada"))
    if inscrito is None or not usuario.municipio or usuario.municipio == evento.municipio:
        raise CocheNoDisponible()
    fila = _respuesta(db, evento.id, usuario.id)
    if fila is None:
        fila = CocheCompartido(evento_id=evento.id, usuario_id=usuario.id)
        db.add(fila)
    fila.respuesta = "si" if acepta else "no"
    db.flush()
    if not acepta:
        return {"respuesta": "no", "companeros": []}, []

    companeros = [u for u in _vecinos_del_pueblo(db, evento, usuario.municipio)
                  if u.id != usuario.id and (r := _respuesta(db, evento.id, u.id)) is not None and r.respuesta == "si"]
    avisos = [
        notificar(db, tipo="anuncio", usuario=u, evento_id=evento.id, enviar=False,
                  texto=(f"{MARCA_COCHE_HECHO} {usuario.nombre} también quiere compartir coche para «{evento.titulo}». "
                         f"Su contacto: {contacto_visible(usuario)}. ¡Buen viaje!"))
        for u in companeros
    ]
    return {"respuesta": "si", "companeros": [contacto_visible(u) for u in companeros]}, avisos
