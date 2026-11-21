"""Aviso de planes nuevos a quien le pueden interesar (D1, tarea A10).

Cuando un plan pasa a `publicado` (lo publica una asociación en automática, lo aprueba el moderador o lo crea el
propio moderador), la API avisa con `tipo: recomendacion` y el `evento_id` (el bot añade [Apuntarme] [Más info]) a
cada persona que:

- ha aceptado los avisos (`acepta_avisos`, A8) y tiene a dónde avisarle (teléfono o Telegram);
- tiene interés: la categoría está en sus `gustos`, alguna etiqueta del plan está en sus `etiquetas_interes`, o ya
  se apuntó a planes de esa categoría o con esas etiquetas (quien fue a una liga de futbolín se entera de la
  siguiente aunque la IA la clasifique en otra categoría);
- está cerca: es en su pueblo o a menos de su `radio_km` (30 km si no tiene). Si no sabemos dónde vive, cuenta;
- no es quien lo publica, no está ya apuntada y no ha recibido ya este aviso (máximo uno por persona y plan).

El motivo sale del recomendador (`componer_motivo`) y el formato (texto o audio) del `formato_aviso` de cada
persona. Los avisos se crean con `enviar=False`: quien llama los manda tras el commit con `enviar_en_segundo_plano`.
"""

import logging
from datetime import datetime
from zoneinfo import ZoneInfo

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import Evento, Inscripcion, Notificacion, Usuario, ahora as ahora_utc
from app.notificaciones import notificar
from app.recomendador import (
    ESTADOS_HISTORIAL,
    NOMBRE_CATEGORIA,
    PESO_HISTORIAL,
    RADIO_POR_DEFECTO_KM,
    Razon,
    _frase_etiqueta,
    _origen,
    _razon_distancia,
    _razon_fecha,
    _razon_gustos,
    _razon_plazas,
    componer_motivo,
    normalizar,
)
from app.rutas.publico import distancia_km

log = logging.getLogger(__name__)

TIPO = "recomendacion"
DIAS = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")


def _cuando(evento: Evento) -> str:
    local = evento.fecha_inicio.astimezone(ZoneInfo(get_settings().zona_horaria))
    texto = f"el {DIAS[local.weekday()]} {local:%d/%m}"
    return texto if (local.hour, local.minute) == (0, 0) else f"{texto} a las {local:%H:%M}"


def _historial(db: Session, usuario: Usuario) -> tuple[set[str], set[str], set[str]]:
    """(eventos a los que está apuntada, categorías y etiquetas normalizadas de los planes a los que fue)."""
    filas = db.execute(
        select(Inscripcion.evento_id, Inscripcion.estado, Evento.categoria, Evento.etiquetas)
        .join(Evento, Evento.id == Inscripcion.evento_id)
        .where(Inscripcion.usuario_id == usuario.id)
    ).all()
    apuntada = {evento_id for evento_id, estado, _, _ in filas if estado != "cancelada"}
    categorias = {categoria for _, estado, categoria, _ in filas if estado in ESTADOS_HISTORIAL}
    etiquetas = {normalizar(e) for _, estado, _, ets in filas if estado in ESTADOS_HISTORIAL for e in ets or []}
    return apuntada, categorias, etiquetas


def _razon_historial(evento: Evento, categorias: set[str], etiquetas: set[str]) -> Razon | None:
    if evento.categoria in categorias:
        tema = NOMBRE_CATEGORIA.get(evento.categoria, evento.categoria)
        return Razon("historial", PESO_HISTORIAL, f"ya te has apuntado a otros planes de {tema}")
    comunes = [e for e in evento.etiquetas or [] if normalizar(e) in etiquetas]
    if comunes:
        return Razon("historial", PESO_HISTORIAL, f"ya te has apuntado a otros planes de {_frase_etiqueta(comunes[0])}")
    return None


def _ya_avisada(db: Session, usuario: Usuario, evento: Evento) -> bool:
    return db.scalar(
        select(Notificacion.id).where(
            Notificacion.usuario_id == usuario.id, Notificacion.evento_id == evento.id, Notificacion.tipo == TIPO
        ).limit(1)
    ) is not None


def interesa(db: Session, usuario: Usuario, evento: Evento, ahora: datetime) -> str | None:
    """El motivo del aviso si a `usuario` hay que avisarle de `evento`; None si no."""
    if not usuario.acepta_avisos or not (usuario.telefono or usuario.telegram_id):
        return None
    if evento.publicador_id and usuario.publicador_id == evento.publicador_id:
        return None
    apuntada, categorias, etiquetas = _historial(db, usuario)
    if evento.id in apuntada:
        return None
    gustos = _razon_gustos(usuario, evento)
    historial = _razon_historial(evento, categorias, etiquetas)
    if gustos is None and historial is None:
        return None
    origen = _origen(db, usuario)
    km = distancia_km(origen[0], origen[1], evento.lat, evento.lon) if origen else None
    en_su_pueblo = usuario.municipio is not None and usuario.municipio == evento.municipio
    if km is not None and not en_su_pueblo and km > (usuario.radio_km or RADIO_POR_DEFECTO_KM):
        return None
    if _ya_avisada(db, usuario, evento):
        return None
    razones = [r for r in (gustos, _razon_distancia(usuario, evento, km), _razon_fecha(evento, ahora),
                           _razon_plazas(evento), historial) if r is not None]
    return componer_motivo(razones)


def avisar_interesados(db: Session, evento: Evento, ahora: datetime | None = None) -> list[Notificacion]:
    """Crea (sin enviar) un aviso para cada persona interesada en `evento`, recién publicado. No lanza."""
    ahora = ahora or ahora_utc()
    try:
        if evento.estado != "publicado" or evento.fecha_inicio < ahora:
            return []
        avisos = []
        for usuario in db.scalars(select(Usuario).where(Usuario.acepta_avisos.is_(True)).order_by(Usuario.creado_en)):
            motivo = interesa(db, usuario, evento, ahora)
            if motivo is None:
                continue
            texto = (f"🔔 Plan nuevo que te puede gustar: «{evento.titulo}» en {evento.municipio}, "
                     f"{_cuando(evento)}. {motivo}.")
            avisos.append(notificar(db, tipo=TIPO, texto=texto, usuario=usuario, evento_id=evento.id, enviar=False))
        return avisos
    except Exception:  # noqa: BLE001 — avisar nunca hace fallar la publicación
        log.exception("no se pudo avisar a los interesados en %s", evento.id)
        return []
