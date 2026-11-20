"""Eventos: agenda y mapa (GET), ficha, alta a mano (POST) y edición (PATCH)."""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.config import get_settings
from app.errores import ErrorApi
from app.modelos import CATEGORIAS, ESTADOS_EVENTO, Evento, Municipio, Publicador
from app.paginacion import Pagina, pagina, paginar, paginar_lista
from app.rutas.publico import dentro_del_radio, en_caja, es_uuid, hay_radio
from app.chat import anuncio_automatico
from app.inscripciones import avisar_inscritos, promocionar, texto_cambio
from app.notificaciones import enviar_en_segundo_plano
from app.seguridad import Quien, es_servicio_interno, exigir_token_interno, puede_gestionar, quien_llama
from app.serializar import evento_a_dict, eventos_a_dict, inscritos_por_evento

router = APIRouter(prefix="/api/v1", tags=["eventos"])

Categoria = Literal[CATEGORIAS]
EstadoEvento = Literal[ESTADOS_EVENTO]
Titulo = Annotated[str, Field(min_length=3, max_length=120)]
NoNegativo = Annotated[float, Field(ge=0)]
EnteroNoNegativo = Annotated[int, Field(ge=0)]

# Estados cuya ficha puede ver cualquiera (un inscrito tiene que poder ver que se ha cancelado).
VISIBLES_EN_FICHA = ("publicado", "cancelado", "finalizado")


class EventoCrear(BaseModel):
    """components/schemas/EventoCrear de openapi.yaml."""

    model_config = ConfigDict(extra="forbid")

    titulo: Titulo
    descripcion: str | None = None
    categoria: Categoria
    etiquetas: list[str] = []
    municipio: str
    lugar: str | None = None
    lat: float | None = None
    lon: float | None = None
    fecha_inicio: datetime
    fecha_fin: datetime | None = None
    precio_eur: NoNegativo | None = None
    es_gratuito: bool | None = None
    plazas_totales: EnteroNoNegativo | None = None
    imagen_url: str | None = None
    publicador_id: str | None = None


class EventoEditar(BaseModel):
    """components/schemas/EventoEditar. Solo se aplican los campos enviados.
    Los que el contrato no deja a null llevan None de valor por defecto pero no lo admiten si se envía."""

    model_config = ConfigDict(extra="forbid")

    titulo: Titulo = None
    descripcion: str = None
    categoria: Categoria = None
    etiquetas: list[str] = None
    lugar: str | None = None
    lat: float | None = None
    lon: float | None = None
    fecha_inicio: datetime = None
    fecha_fin: datetime | None = None
    precio_eur: NoNegativo | None = None
    es_gratuito: bool = None
    plazas_totales: EnteroNoNegativo | None = None
    imagen_url: str | None = None
    estado: Literal["cancelado", "archivado"] = None


def _error_validacion(code: str, message: str, campo: str) -> ErrorApi:
    return ErrorApi(422, code, message, {"campo": campo})


def _buscar(db: Session, id: str) -> Evento:
    evento = db.get(Evento, id, options=[selectinload(Evento.publicador)]) if es_uuid(id) else None
    if evento is None:
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return evento


def _ficha(db: Session, evento: Evento) -> dict:
    return evento_a_dict(evento, inscritos_por_evento(db, [evento.id]).get(evento.id, 0))


def _ocupadas(db: Session, evento_id: str) -> int:
    return inscritos_por_evento(db, [evento_id]).get(evento_id, 0)


def _comprobar_fechas(evento: Evento) -> None:
    if evento.fecha_fin is not None and evento.fecha_fin < evento.fecha_inicio:
        raise _error_validacion("fechas_invalidas", "fecha_fin no puede ser anterior a fecha_inicio", "fecha_fin")


def _con_zona(valor: datetime | None) -> datetime | None:
    """Una fecha sin zona se entiende en hora de Madrid (igual que FechaUTC al guardarla)."""
    if valor is None or valor.tzinfo is not None:
        return valor
    return valor.replace(tzinfo=ZoneInfo(get_settings().zona_horaria))


def _escapar_like(texto: str) -> str:
    return texto.replace("\\", "\\\\").replace("%", "\\%").replace("_", "\\_")


@router.get("/eventos")
def listar_eventos(
    municipio: str | None = None,
    categoria: Categoria | None = None,
    desde: datetime | None = None,
    hasta: datetime | None = None,
    lat: float | None = None,
    lon: float | None = None,
    radio_km: float | None = Query(None, ge=0),
    q: str | None = None,
    estado: EstadoEvento = "publicado",
    publicador_id: str | None = None,
    p: Pagina = Depends(pagina),
    x_internal_token: str | None = Header(None),
    db: Session = Depends(get_db),
):
    # Hasta que haya login (H3) solo los servicios internos pueden pedir otro estado; el público ve `publicado`.
    if not es_servicio_interno(x_internal_token):
        estado = "publicado"
    consulta = (
        select(Evento)
        .options(selectinload(Evento.publicador))
        .where(Evento.estado == estado)
        .order_by(Evento.fecha_inicio, Evento.id)
    )
    if municipio:
        consulta = consulta.where(Evento.municipio == municipio)
    if categoria:
        consulta = consulta.where(Evento.categoria == categoria)
    if desde:
        # Entra lo que aún no ha terminado en `desde` (un evento de varios días que ya empezó sigue saliendo).
        consulta = consulta.where(func.coalesce(Evento.fecha_fin, Evento.fecha_inicio) >= desde)
    if hasta:
        consulta = consulta.where(Evento.fecha_inicio <= hasta)
    if q and q.strip():
        patron = f"%{_escapar_like(q.strip())}%"
        consulta = consulta.where(
            or_(Evento.titulo.ilike(patron, escape="\\"), Evento.descripcion.ilike(patron, escape="\\"))
        )
    if publicador_id:
        consulta = consulta.where(Evento.publicador_id == publicador_id)

    if not hay_radio(lat, lon, radio_km):
        resultado = paginar(db, consulta, p, lambda e: e)
        resultado["items"] = eventos_a_dict(db, resultado["items"])
        return resultado
    filas = dentro_del_radio(db.scalars(en_caja(consulta, Evento, lat, lon, radio_km)).all(), lat, lon, radio_km)
    pagina_eventos = paginar_lista(filas, p)
    pagina_eventos["items"] = eventos_a_dict(db, pagina_eventos["items"])
    return pagina_eventos


@router.get("/eventos/{id}")
def ver_evento(id: str, x_internal_token: str | None = Header(None), db: Session = Depends(get_db)):
    evento = _buscar(db, id)
    # Borradores, pendientes, en revisión, rechazados y archivados no existen para el público.
    if evento.estado not in VISIBLES_EN_FICHA and not es_servicio_interno(x_internal_token):
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return _ficha(db, evento)


@router.post("/eventos", status_code=201, dependencies=[Depends(exigir_token_interno)])
def crear_evento(datos: EventoCrear, db: Session = Depends(get_db)):
    # H3: con el JWT, publicador (sus eventos) o moderador. Hasta entonces solo servicios internos.
    municipio = db.get(Municipio, datos.municipio)
    if municipio is None:
        raise _error_validacion("municipio_no_encontrado", "Ese municipio no está en la plataforma", "municipio")
    if datos.publicador_id is not None:
        publicador = db.get(Publicador, datos.publicador_id) if es_uuid(datos.publicador_id) else None
        if publicador is None:
            raise _error_validacion("publicador_no_encontrado", "No existe ese publicador", "publicador_id")
        if publicador.estado == "pausado":
            raise ErrorApi(403, "publicador_pausado", "El publicador está pausado y no puede publicar")

    campos = datos.model_dump(exclude={"lat", "lon", "es_gratuito"})
    campos["fecha_inicio"], campos["fecha_fin"] = _con_zona(datos.fecha_inicio), _con_zona(datos.fecha_fin)
    evento = Evento(
        **campos,
        lat=datos.lat if datos.lat is not None else municipio.lat,
        lon=datos.lon if datos.lon is not None else municipio.lon,
        es_gratuito=datos.es_gratuito if datos.es_gratuito is not None else datos.precio_eur == 0,
        plazas_libres=datos.plazas_totales,
        # Sin moderación todavía (H2): lo creado a mano espera a que un moderador lo revise.
        estado="en_revision",
        origen_canal="manual",
    )
    _comprobar_fechas(evento)
    db.add(evento)
    db.commit()
    return _ficha(db, _buscar(db, evento.id))


@router.patch("/eventos/{id}")
def editar_evento(
    id: str,
    datos: EventoEditar,
    background_tasks: BackgroundTasks,
    quien: Quien = Depends(quien_llama),
    db: Session = Depends(get_db),
):
    """Servicio interno, organizador del evento o moderador. Si cambia la fecha, el lugar o se cancela, se avisa
    a los inscritos (confirmados y en lista de espera) después del commit."""
    evento = _buscar(db, id)
    if not puede_gestionar(quien, evento):
        raise ErrorApi(403, "prohibido", "Solo el organizador del evento o un moderador pueden editarlo")
    cambios = datos.model_dump(exclude_unset=True)
    for campo in ("fecha_inicio", "fecha_fin"):
        if campo in cambios:
            cambios[campo] = _con_zona(cambios[campo])
    fecha_anterior, lugar_anterior, estado_anterior = evento.fecha_inicio, evento.lugar, evento.estado

    for campo, valor in cambios.items():
        setattr(evento, campo, valor)
    if evento.lat is None or evento.lon is None:
        # Sin coordenadas: las del municipio, como al crear.
        municipio = db.get(Municipio, evento.municipio)
        evento.lat = evento.lat if evento.lat is not None else municipio.lat
        evento.lon = evento.lon if evento.lon is not None else municipio.lon
    _comprobar_fechas(evento)

    avisos = []
    if "plazas_totales" in cambios:
        total = cambios["plazas_totales"]
        evento.plazas_libres = None if total is None else max(0, total - _ocupadas(db, evento.id))
        db.flush()
        if evento.estado == "publicado":
            avisos += promocionar(db, evento)  # con más plazas, sube la lista de espera

    cancelado = evento.estado == "cancelado" and estado_anterior != "cancelado"
    texto = texto_cambio(evento, fecha_anterior, lugar_anterior, cancelado)
    if texto:
        avisos += avisar_inscritos(db, evento, "cambio_evento", texto)
        # Anuncio fijado en el chat con el mismo texto, en la misma transacción que el cambio.
        anuncio_automatico(db, evento, texto, quien.usuario)

    db.commit()
    enviar_en_segundo_plano(background_tasks, db, avisos)
    return _ficha(db, _buscar(db, evento.id))
