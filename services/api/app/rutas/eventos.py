"""Eventos: agenda y mapa (GET), ficha, alta a mano (POST) y edición (PATCH).

Privacidad: `datos_ayuntamiento` solo sale hacia el organizador del evento o un moderador con sesión bearer
(`ve_datos_privados`). Las listas públicas, el bot (X-Internal-Token) y la IA nunca lo reciben.
"""

from datetime import datetime
from zoneinfo import ZoneInfo
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Header, Query
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db import get_db
from app.config import get_settings
from app.duplicados import buscar_posible_duplicado
from app.errores import ErrorApi
from app.imagenes import validar_imagen
from app.modelos import CATEGORIAS, ESTADOS_EVENTO, Evento, Municipio, Publicador, Usuario
from app.moderacion import clasificar_spam, decidir_estado, motivo_con_duplicado
from app.paginacion import Pagina, pagina, paginar, paginar_lista
from app.rutas.publico import dentro_del_radio, en_caja, es_uuid, hay_radio
from app.chat import anuncio_automatico
from app.inscripciones import avisar_inscritos, promocionar, texto_cambio
from app.notificaciones import enviar_en_segundo_plano, notificar_moderadores
from app.seguridad import (
    Quien,
    es_servicio_interno,
    puede_gestionar,
    quien_llama,
    usuario_actual,
    ve_datos_privados,
)
from app.serializar import evento_a_dict, eventos_a_dict, inscritos_por_evento

router = APIRouter(prefix="/api/v1", tags=["eventos"])

Categoria = Literal[CATEGORIAS]
EstadoEvento = Literal[ESTADOS_EVENTO]
Titulo = Annotated[str, Field(min_length=3, max_length=120)]
NoNegativo = Annotated[float, Field(ge=0)]
EnteroNoNegativo = Annotated[int, Field(ge=0)]

# Estados cuya ficha puede ver cualquiera (un inscrito tiene que poder ver que se ha cancelado).
VISIBLES_EN_FICHA = ("publicado", "cancelado", "finalizado")
# Estados que se pueden pedir en GET /eventos sin ser servicio interno: la agenda y los «Recuerdos».
VISIBLES_EN_LISTA = ("publicado", "finalizado")
# Foto o cartel del evento: data URL de hasta ~1,5 MB (de imagen decodificada).
MAX_BYTES_IMAGEN_EVENTO = 1536 * 1024
FrasePortada = Annotated[str, Field(max_length=90)]


class DatosAyuntamiento(BaseModel):
    """components/schemas/DatosAyuntamiento (PRIVADO). Lo desconocido se ignora (p. ej. `frase_portada`, que va
    en el evento)."""

    model_config = ConfigDict(extra="ignore")

    responsable: Annotated[str, Field(max_length=120)] = None
    telefono: Annotated[str, Field(max_length=20)] = None
    entidad: Literal["particular", "asociacion", "comercio", "otra"] = None
    entidad_nombre: Annotated[str, Field(max_length=120)] | None = None
    publico: Literal["todos", "infantil", "adultos", "mayores"] = None
    necesidades: list[
        Literal["espacio", "calle", "material", "luz", "musica", "comida", "seguridad", "limpieza", "difusion"]
    ] = None
    seguro_rc: Literal["si", "no", "nose"] = None
    observaciones: Annotated[str, Field(max_length=1000)] | None = None


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
    frase_portada: FrasePortada | None = None
    datos_ayuntamiento: DatosAyuntamiento | None = None
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
    frase_portada: FrasePortada | None = None
    datos_ayuntamiento: DatosAyuntamiento | None = None
    estado: Literal["cancelado", "archivado"] = None


def _error_validacion(code: str, message: str, campo: str) -> ErrorApi:
    return ErrorApi(422, code, message, {"campo": campo})


def _buscar(db: Session, id: str) -> Evento:
    evento = db.get(Evento, id, options=[selectinload(Evento.publicador)]) if es_uuid(id) else None
    if evento is None:
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return evento


def _ficha(db: Session, evento: Evento, privados: bool = False) -> dict:
    """`privados`: incluir `datos_ayuntamiento` (ver `ve_datos_privados`)."""
    return evento_a_dict(evento, inscritos_por_evento(db, [evento.id]).get(evento.id, 0), privados)


def normalizar_extras(cambios: dict) -> dict:
    """imagen_url, frase_portada y datos_ayuntamiento tal como se guardan: textos sin espacios sobrantes (vacío
    = null), la imagen validada (422 `imagen_invalida`) y los datos del ayuntamiento como dict JSON."""
    if "imagen_url" in cambios:
        imagen = (cambios["imagen_url"] or "").strip() or None
        if imagen is not None:
            validar_imagen(imagen, MAX_BYTES_IMAGEN_EVENTO, status_grande=422, code_grande="imagen_invalida")
        cambios["imagen_url"] = imagen
    if "frase_portada" in cambios:
        cambios["frase_portada"] = (cambios["frase_portada"] or "").strip() or None
    if "datos_ayuntamiento" in cambios:
        datos = cambios["datos_ayuntamiento"]
        if isinstance(datos, BaseModel):
            datos = datos.model_dump(exclude_unset=True)
        cambios["datos_ayuntamiento"] = datos or None
    return cambios


def comprobar_puede_publicar(publicador: Publicador | None) -> None:
    """403 si el publicador está pausado o su solicitud fue rechazada."""
    if publicador is None:
        return
    if publicador.estado == "pausado":
        raise ErrorApi(403, "publicador_pausado", "El publicador está pausado y no puede publicar")
    if publicador.estado == "rechazado":
        raise ErrorApi(403, "publicador_rechazado", "La solicitud del publicador fue rechazada: no puede publicar")


def quien_opcional(
    x_internal_token: str | None = Header(None), usuario: Usuario | None = Depends(usuario_actual)
) -> Quien:
    """Como `quien_llama`, pero sin exigir nada (rutas públicas que enseñan más a quien tiene permiso)."""
    return Quien(es_servicio_interno(x_internal_token), usuario)


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


def _quien_tolerante(
    x_internal_token: str | None = Header(None),
    authorization: str | None = Header(None),
    db: Session = Depends(get_db),
) -> Quien:
    """Como `quien_opcional`, pero una sesión caducada o mal firmada cuenta como anónima en vez de dar 401:
    la agenda es pública y el contrato de `GET /eventos` solo prevé 200/422."""
    try:
        usuario = usuario_actual(authorization, db)
    except ErrorApi:
        usuario = None
    return Quien(es_servicio_interno(x_internal_token), usuario)


def _publicadores_del_usuario(db: Session, usuario: Usuario) -> list[str]:
    """Entidades de las que el usuario es organizador (como en `es_organizador`)."""
    ids = set(db.scalars(select(Publicador.id).where(Publicador.usuario_id == usuario.id)).all())
    if usuario.publicador_id is not None:
        ids.add(usuario.publicador_id)
    return sorted(ids)


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
    quien: Quien = Depends(_quien_tolerante),
    db: Session = Depends(get_db),
):
    # `publicado` (agenda) y `finalizado` («Recuerdos») los ve cualquiera. Los demás estados:
    # - token interno o moderador con sesión: todos los eventos de ese estado;
    # - publicador con sesión: solo los de sus entidades (si pide otro `publicador_id`, la lista sale vacía:
    #   el contrato solo prevé 200/422 en esta ruta, así que no se responde 403);
    # - vecino o sin sesión: se cambia por `publicado`, como antes.
    # `datos_ayuntamiento` nunca sale en esta lista (el contrato lo dice así): se ve en la ficha o en /moderacion.
    solo_de: list[str] | None = None
    if estado not in VISIBLES_EN_LISTA and not quien.interno:
        u = quien.usuario
        if u is not None and u.rol == "moderador":
            pass
        elif u is not None and (ids := _publicadores_del_usuario(db, u)):
            solo_de = ids
        else:
            estado = "publicado"
    consulta = (
        select(Evento)
        .options(selectinload(Evento.publicador))
        .where(Evento.estado == estado)
        .order_by(Evento.fecha_inicio, Evento.id)
    )
    if solo_de is not None:
        consulta = consulta.where(Evento.publicador_id.in_(solo_de))
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
def ver_evento(id: str, quien: Quien = Depends(quien_opcional), db: Session = Depends(get_db)):
    evento = _buscar(db, id)
    # Borradores, pendientes, en revisión, rechazados y archivados no existen para el público; sí para el bot,
    # el organizador del evento y los moderadores.
    if evento.estado not in VISIBLES_EN_FICHA and not puede_gestionar(quien, evento):
        raise ErrorApi(404, "evento_no_encontrado", "No existe ese evento")
    return _ficha(db, evento, ve_datos_privados(quien, evento))


def _publicador_de_la_peticion(db: Session, datos: EventoCrear, usuario: Usuario | None) -> Publicador | None:
    """Publicador del evento. `usuario`: el de la sesión (None si llama un servicio interno). Un usuario que no es
    moderador solo publica a nombre de su entidad (403 `prohibido` si manda otra); si no manda ninguna y es
    publicador, se usa la suya."""
    publicador = None
    if datos.publicador_id is not None:
        publicador = db.get(Publicador, datos.publicador_id) if es_uuid(datos.publicador_id) else None
        if publicador is None:
            raise _error_validacion("publicador_no_encontrado", "No existe ese publicador", "publicador_id")
        if usuario is not None and usuario.rol != "moderador":
            if usuario.publicador_id != publicador.id and publicador.usuario_id != usuario.id:
                raise ErrorApi(
                    403, "prohibido", "Solo puedes publicar a nombre de tu propia entidad", {"campo": "publicador_id"}
                )
    elif usuario is not None and usuario.rol != "moderador":
        if usuario.publicador_id is not None:
            publicador = db.get(Publicador, usuario.publicador_id)
        if publicador is None:
            publicador = db.scalar(
                select(Publicador).where(Publicador.usuario_id == usuario.id).order_by(Publicador.creado_en)
            )
    comprobar_puede_publicar(publicador)
    return publicador


@router.post("/eventos", status_code=201)
def crear_evento(
    datos: EventoCrear,
    background_tasks: BackgroundTasks,
    quien: Quien = Depends(quien_llama),
    db: Session = Depends(get_db),
):
    """Alta a mano. Según quién llama:
    - servicio interno (X-Internal-Token): queda `en_revision`, como siempre;
    - moderador (bearer): `publicado` directamente;
    - vecino o publicador (bearer, la web «Proponer»): moderación automática como al confirmar (spam y nivel de
      confianza del publicador; sin publicador, `en_revision`). Si queda en revisión se avisa a los moderadores.
    """
    usuario = None if quien.interno else quien.usuario
    municipio = db.get(Municipio, datos.municipio)
    if municipio is None:
        raise _error_validacion("municipio_no_encontrado", "Ese municipio no está en la plataforma", "municipio")
    publicador = _publicador_de_la_peticion(db, datos, usuario)

    campos = datos.model_dump(exclude={"lat", "lon", "es_gratuito", "publicador_id", "datos_ayuntamiento"})
    # Solo lo que se ha enviado de los datos para el ayuntamiento (sin rellenar con null lo que no viene).
    campos = normalizar_extras(campos | {"datos_ayuntamiento": datos.datos_ayuntamiento})
    campos["fecha_inicio"], campos["fecha_fin"] = _con_zona(datos.fecha_inicio), _con_zona(datos.fecha_fin)
    evento = Evento(
        **campos,
        publicador_id=publicador.id if publicador is not None else None,
        lat=datos.lat if datos.lat is not None else municipio.lat,
        lon=datos.lon if datos.lon is not None else municipio.lon,
        es_gratuito=datos.es_gratuito if datos.es_gratuito is not None else datos.precio_eur == 0,
        plazas_libres=datos.plazas_totales,
        estado="en_revision",
        origen_canal="manual" if usuario is None else "web",
    )
    _comprobar_fechas(evento)

    if usuario is not None and usuario.rol == "moderador":
        evento.estado, evento.revisado_por = "publicado", usuario.nombre
        evento.motivo_moderacion = "Publicado por el moderador"
    elif usuario is not None:
        texto = "\n".join(t for t in (evento.titulo, evento.descripcion) if t)
        score, motivo_spam = clasificar_spam(texto, publicador)
        estado, motivo = decidir_estado(db, evento, publicador, score, motivo_spam)
        parecido = buscar_posible_duplicado(db, evento.titulo, evento.fecha_inicio, evento.municipio)
        estado, motivo = motivo_con_duplicado(estado, motivo, parecido.titulo if parecido else None)
        evento.estado, evento.score_spam, evento.motivo_moderacion = estado, score, motivo
    db.add(evento)
    db.flush()

    avisos = []
    if usuario is not None and evento.estado == "en_revision":
        de = publicador.nombre if publicador is not None else f"propuesta de {usuario.nombre}"
        avisos = notificar_moderadores(
            db, "moderacion", f"Evento para revisar: «{evento.titulo}» ({de}). Motivo: {evento.motivo_moderacion}",
            evento_id=evento.id, enviar=False,
        )
    db.commit()
    enviar_en_segundo_plano(background_tasks, db, avisos)
    # Quien lo propone con su sesión ve lo que acaba de enviar, también los datos para el ayuntamiento.
    return _ficha(db, _buscar(db, evento.id), privados=usuario is not None)


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
    cambios = normalizar_extras(datos.model_dump(exclude_unset=True))
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
    evento = _buscar(db, evento.id)
    return _ficha(db, evento, ve_datos_privados(quien, evento))
