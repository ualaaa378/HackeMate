"""Ingesta: el bot entrega lo que la IA ha sacado de un post, cartel o audio (E1.6, adelanto de H2.1).

El evento se crea en `pendiente_confirmacion`: no lo ve nadie hasta que el publicador confirma (H2.3).
La IA propone; aquí se valida cada campo y lo que no sirve cuenta como que falta. Al confirmar,
la moderación automática (H2.4) decide si pasa a `publicado` o a `en_revision`.
"""

from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, BackgroundTasks, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.canales import buscar_publicador_por_contacto, buscar_usuario_por_contacto, validar_contacto
from app.db import get_db
from app.duplicados import buscar_posible_duplicado
from app.errores import ErrorApi
from app.modelos import CANALES, CATEGORIAS, Evento, Fuente, Municipio, Publicador, ahora
from app.moderacion import clasificar_spam, decidir_estado, motivo_con_duplicado
from app.avisos_planes import avisar_interesados
from app.notificaciones import enviar_en_segundo_plano, notificar_moderadores
from app.rutas.eventos import (
    Categoria,
    DatosAyuntamiento,
    EnteroNoNegativo,
    FrasePortada,
    NoNegativo,
    Titulo,
    _buscar,
    _comprobar_fechas,
    _con_zona,
    _ficha,
    comprobar_puede_publicar,
    normalizar_extras,
)
from app.rutas.publico import es_uuid
from app.seguridad import exigir_token_interno
from app.texto import plegar

router = APIRouter(prefix="/api/v1", tags=["ingesta"])

# Sin estos no se puede publicar. Si la IA no los trae, el evento se guarda con un valor provisional
# (las columnas no admiten null) y el campo queda en `faltan` hasta que el publicador lo confirme.
OBLIGATORIOS = ("titulo", "categoria", "municipio", "fecha_inicio")
TITULO_PROVISIONAL = "Evento sin titulo"
CATEGORIA_PROVISIONAL = "cultural"


class CampoExtraido(BaseModel):
    model_config = ConfigDict(extra="ignore")

    valor: Any = None
    confianza: Literal["alta", "media", "baja", "falta"]


class Tokens(BaseModel):
    model_config = ConfigDict(extra="ignore")

    entrada: Annotated[int, Field(ge=0)] | None = None
    salida: Annotated[int, Field(ge=0)] | None = None


class ExtraccionEvento(BaseModel):
    """contracts/schemas/extraccion_evento.json."""

    model_config = ConfigDict(extra="ignore")

    campos: dict[str, CampoExtraido]
    faltan: list[str]
    es_evento: bool
    proveedor_ia: str
    tokens: Tokens | None = None


class Origen(BaseModel):
    """components/schemas/Origen."""

    model_config = ConfigDict(extra="ignore")

    canal: Literal[CANALES]
    url: str | None = None
    importado_auto: bool


# El contrato no cierra additionalProperties y admite campos opcionales nuevos: lo desconocido se ignora.
class ImportarEvento(BaseModel):
    """components/schemas/ImportarEvento."""

    model_config = ConfigDict(extra="ignore")

    extraccion: ExtraccionEvento
    contacto_publicador: str | None = None
    # Compatibilidad: además de E.164 admite `tg:<chat_id>` (lo que envía hoy el bot de Telegram).
    telefono_publicador: str | None = None
    publicador_id: str | None = None
    origen: Origen

    @field_validator("contacto_publicador", "telefono_publicador")
    @classmethod
    def _contacto(cls, valor: str | None) -> str | None:
        return None if valor is None else validar_contacto(valor)

    @property
    def contacto(self) -> str | None:
        """Dirección del remitente en su canal (`+34…` o `tg:…`)."""
        return self.contacto_publicador or self.telefono_publicador


# --- Lectura defensiva de lo que propone la IA (un valor que no encaja es como si faltara) ------------


def _valor(campos: dict[str, CampoExtraido], nombre: str) -> Any:
    campo = campos.get(nombre)
    if campo is None or campo.confianza == "falta":
        return None
    return campo.valor


def _texto(valor: Any) -> str | None:
    return valor.strip() or None if isinstance(valor, str) else None


def _fecha(valor: Any) -> datetime | None:
    if not isinstance(valor, str):
        return None
    try:
        return _con_zona(datetime.fromisoformat(valor.strip()))
    except ValueError:
        return None


def _numero(valor: Any) -> float | None:
    if isinstance(valor, bool) or not isinstance(valor, (int, float)) or valor < 0:
        return None
    return float(valor)


def _entero(valor: Any) -> int | None:
    numero = _numero(valor)
    return int(numero) if numero is not None and numero == int(numero) else None


def _imagen(valor: Any) -> str | None:
    """Una imagen que no es URL http(s) ni data URL válida es como si faltara."""
    texto = _texto(valor)
    if texto is None:
        return None
    try:
        return normalizar_extras({"imagen_url": texto})["imagen_url"]
    except ErrorApi:
        return None


def _frase(valor: Any) -> str | None:
    texto = _texto(valor)
    return texto[:90].strip() if texto else None


def _municipio(db: Session, valor: Any) -> Municipio | None:
    nombre = _texto(valor)
    if nombre is None:
        return None
    exacto = db.get(Municipio, nombre)
    if exacto is not None:
        return exacto
    buscado = plegar(nombre)
    return next((m for m in db.scalars(select(Municipio)).all() if plegar(m.nombre) == buscado), None)


# --- Publicador -------------------------------------------------------------------------------------


def _publicador_por_fuente(db: Session, url: str | None) -> Publicador | None:
    """La fuente registrada cuya URL es la del post o un prefijo suyo (la página de la que cuelga)."""
    if not url:
        return None
    mejor: Fuente | None = None
    for fuente in db.scalars(select(Fuente).where(Fuente.activa.is_(True))).all():
        base = fuente.url.rstrip("/")
        if url.rstrip("/") == base or url.startswith(base + "/"):
            if mejor is None or len(fuente.url) > len(mejor.url):
                mejor = fuente
    return mejor.publicador if mejor else None


def _primero_con_url(db: Session, url: str, excluir_id: str | None = None) -> Evento | None:
    """El evento más antiguo con ese origen_url (desempate por id: dos peticiones a la vez eligen el mismo)."""
    consulta = select(Evento).where(Evento.origen_url == url)
    if excluir_id is not None:
        consulta = consulta.where(Evento.id != excluir_id)
    return db.scalar(consulta.order_by(Evento.creado_en, Evento.id).limit(1))


def _usuario_del_contacto(db: Session, datos: ImportarEvento) -> str | None:
    if datos.contacto is None:
        return None
    usuario = buscar_usuario_por_contacto(db, datos.contacto)
    return usuario.id if usuario is not None else None


def _asociar_publicador(db: Session, datos: ImportarEvento) -> Publicador | None:
    """Orden: fuente conocida (origen.url) -> publicador_id -> contacto del remitente en su canal
    (teléfono o telegram_id; en Telegram, también el teléfono del usuario vinculado)."""
    publicador = _publicador_por_fuente(db, datos.origen.url)
    if publicador is None and datos.publicador_id is not None:
        publicador = db.get(Publicador, datos.publicador_id) if es_uuid(datos.publicador_id) else None
        if publicador is None:
            raise ErrorApi(422, "publicador_no_encontrado", "No existe ese publicador", {"campo": "publicador_id"})
    if publicador is None and datos.contacto is not None:
        publicador = buscar_publicador_por_contacto(db, datos.contacto)
    comprobar_puede_publicar(publicador)
    # H2.4: según el estado y el nivel de confianza del publicador se decidirá luego la moderación.
    return publicador


def _resultado(
    db: Session, evento: Evento, duplicado: bool, status: int, posible_duplicado_de: str | None = None
) -> JSONResponse:
    cuerpo = {
        "evento": _ficha(db, _buscar(db, evento.id)),
        "faltan": list(evento.faltan or []),
        "duplicado": duplicado,
        "posible_duplicado_de": posible_duplicado_de,
    }
    return JSONResponse(cuerpo, status_code=status)


@router.post(
    "/eventos/importar",
    status_code=201,
    dependencies=[Depends(exigir_token_interno)],
    responses={200: {"description": "Ya existía (mismo origen.url)"}},
)
def importar_evento(datos: ImportarEvento, db: Session = Depends(get_db)):
    extraccion = datos.extraccion
    if not extraccion.es_evento:
        raise ErrorApi(422, "no_es_evento", "La extracción indica que el contenido no es un evento", {"campo": "es_evento"})

    publicador = _asociar_publicador(db, datos)

    url = (datos.origen.url or "").strip() or None
    if url is not None:
        existente = _primero_con_url(db, url)
        if existente is not None:
            return _resultado(db, existente, duplicado=True, status=200)

    campos = extraccion.campos
    titulo = _texto(_valor(campos, "titulo"))
    titulo = titulo[:120] if titulo and len(titulo) >= 3 else None
    categoria = _valor(campos, "categoria")
    categoria = categoria if categoria in CATEGORIAS else None
    municipio = _municipio(db, _valor(campos, "municipio"))
    fecha_inicio = _fecha(_valor(campos, "fecha_inicio"))
    fecha_fin = _fecha(_valor(campos, "fecha_fin"))
    if fecha_fin is not None and fecha_inicio is not None and fecha_fin < fecha_inicio:
        fecha_fin = None
    precio = _numero(_valor(campos, "precio_eur"))
    es_gratuito = _valor(campos, "es_gratuito")
    if not isinstance(es_gratuito, bool):
        es_gratuito = precio == 0
    plazas = _entero(_valor(campos, "plazas_totales"))
    etiquetas = _valor(campos, "etiquetas")
    etiquetas = [e for e in etiquetas if isinstance(e, str)] if isinstance(etiquetas, list) else []

    faltan = list(dict.fromkeys(extraccion.faltan))
    validos = {"titulo": titulo, "categoria": categoria, "municipio": municipio, "fecha_inicio": fecha_inicio}
    faltan += [c for c in OBLIGATORIOS if validos[c] is None and c not in faltan]

    # H2.2: sin mismo origen.url, uno parecido (título + fecha + municipio) se señala pero se crea igualmente.
    # Solo con valores reales: con los provisionales todo se parecería a todo.
    parecido = None
    if titulo is not None and fecha_inicio is not None and municipio is not None:
        parecido = buscar_posible_duplicado(db, titulo, fecha_inicio, municipio.nombre)

    # Valores provisionales para lo obligatorio que falta (ver OBLIGATORIOS). El municipio, el del
    # publicador o, si no hay, el primero de la plataforma.
    if municipio is None and publicador is not None:
        municipio = db.get(Municipio, publicador.municipio)
    if municipio is None:
        municipio = db.scalars(select(Municipio).order_by(Municipio.nombre)).first()
    if municipio is None:
        raise ErrorApi(422, "municipio_no_encontrado", "No hay municipios en la plataforma", {"campo": "municipio"})
    if categoria is None and publicador is not None and publicador.categorias_habituales:
        categoria = publicador.categorias_habituales[0]

    evento = Evento(
        titulo=titulo or TITULO_PROVISIONAL,
        descripcion=_texto(_valor(campos, "descripcion")),
        categoria=categoria or CATEGORIA_PROVISIONAL,
        etiquetas=etiquetas,
        municipio=municipio.nombre,
        lugar=_texto(_valor(campos, "lugar")),
        lat=municipio.lat,
        lon=municipio.lon,
        fecha_inicio=fecha_inicio or ahora(),
        fecha_fin=fecha_fin,
        precio_eur=precio,
        es_gratuito=es_gratuito,
        plazas_totales=plazas,
        plazas_libres=plazas,
        imagen_url=_imagen(_valor(campos, "imagen_url")),
        frase_portada=_frase(_valor(campos, "frase_portada")),
        estado="pendiente_confirmacion",
        # P5a: quien lo manda por el bot (vecino o miembro de una asociación) es su dueño.
        propuesto_por_id=_usuario_del_contacto(db, datos),
        publicador_id=publicador.id if publicador else None,
        origen_canal=datos.origen.canal,
        origen_url=url,
        importado_auto=datos.origen.importado_auto,
        extraccion=extraccion.model_dump(mode="json"),
        faltan=faltan,
    )
    # H2.4: moderación y niveles de confianza (score_spam, en_revision/publicado) al confirmar (H2.3).
    db.add(evento)
    if url is not None:
        # El mismo post puede llegar dos veces casi a la vez (reintento del bot, dos webhooks). No hay índice
        # único en origen_url: se vuelve a mirar justo antes del commit y, ya guardado, se queda solo el más
        # antiguo; el que pierde se borra y responde como duplicado.
        try:
            db.flush()
            otro = _primero_con_url(db, url, excluir_id=evento.id)
            if otro is not None:
                db.rollback()
                return _resultado(db, otro, duplicado=True, status=200)
            db.commit()
        except IntegrityError:
            db.rollback()
            otro = _primero_con_url(db, url)
            if otro is None:
                raise
            return _resultado(db, otro, duplicado=True, status=200)
        primero = _primero_con_url(db, url)
        if primero is not None and primero.id != evento.id:
            db.delete(evento)
            db.commit()
            return _resultado(db, primero, duplicado=True, status=200)
    else:
        db.commit()
    return _resultado(db, evento, duplicado=False, status=201, posible_duplicado_de=parecido.id if parecido else None)


# --- Confirmación del publicador (H2.3) -------------------------------------------------------------


class CamposConfirmar(BaseModel):
    """`ConfirmarEvento.campos`: mismos nombres que EventoCrear, todos opcionales. Los que el contrato
    no deja a null llevan None por defecto pero no lo admiten si se envía. Lo desconocido se ignora
    (el contrato deja additionalProperties abierto)."""

    model_config = ConfigDict(extra="ignore")

    titulo: Titulo = None
    descripcion: str | None = None
    categoria: Categoria = None
    etiquetas: list[str] = None
    municipio: str = None
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


class ConfirmarEvento(BaseModel):
    """components/schemas/ConfirmarEvento."""

    model_config = ConfigDict(extra="ignore")

    campos: CamposConfirmar = Field(default_factory=CamposConfirmar)
    confirmado_por: Literal["whatsapp", "web", "telegram"] | None = None


def _aplicar_campos(db: Session, evento: Evento, campos: CamposConfirmar) -> set[str]:
    """Aplica al evento los campos enviados y devuelve los que quedan rellenos (con un valor real)."""
    cambios = normalizar_extras(campos.model_dump(exclude_unset=True))
    for nombre in ("descripcion", "lugar"):
        if nombre in cambios:
            cambios[nombre] = _texto(cambios[nombre])
    for nombre in ("fecha_inicio", "fecha_fin"):
        if nombre in cambios:
            cambios[nombre] = _con_zona(cambios[nombre])

    rellenos = {c for c, v in cambios.items() if v is not None and v != []}

    if "municipio" in cambios:
        municipio = _municipio(db, cambios.pop("municipio"))
        if municipio is None:
            raise ErrorApi(422, "municipio_no_encontrado", "Ese municipio no está en la plataforma", {"campo": "municipio"})
        cambios["municipio"] = municipio.nombre
        # Las coordenadas eran las del municipio provisional: pasan a las del nuevo salvo que vengan.
        cambios.setdefault("lat", municipio.lat)
        cambios.setdefault("lon", municipio.lon)

    for nombre, valor in cambios.items():
        setattr(evento, nombre, valor)
    if "plazas_totales" in cambios:
        # Un evento pendiente de confirmar no tiene inscritos: todas las plazas están libres.
        evento.plazas_libres = cambios["plazas_totales"]
    if "precio_eur" in cambios and "es_gratuito" not in cambios and cambios["precio_eur"] is not None:
        evento.es_gratuito = cambios["precio_eur"] == 0
    if evento.lat is None or evento.lon is None:
        municipio = db.get(Municipio, evento.municipio)
        evento.lat = evento.lat if evento.lat is not None else municipio.lat
        evento.lon = evento.lon if evento.lon is not None else municipio.lon
    _comprobar_fechas(evento)
    return rellenos


@router.post("/eventos/{id}/confirmar", dependencies=[Depends(exigir_token_interno)])
def confirmar_evento(
    id: str, datos: ConfirmarEvento, background_tasks: BackgroundTasks, db: Session = Depends(get_db)
):
    # H3: JWT del publicador (solo sus eventos). Hasta entonces solo servicios internos (el bot).
    evento = _buscar(db, id)
    if evento.estado != "pendiente_confirmacion":
        raise ErrorApi(
            409, "estado_invalido", "El evento no está pendiente de confirmación", {"estado": evento.estado}
        )
    publicador = evento.publicador
    comprobar_puede_publicar(publicador)

    try:
        rellenos = _aplicar_campos(db, evento, datos.campos)
        # Lo que faltaba al importar (provisionales y lo que marcó la IA) y no se ha rellenado ahora.
        faltan = [c for c in (evento.faltan or []) if c not in rellenos]
        bloquean = [c for c in faltan if c in OBLIGATORIOS]
        if bloquean:
            raise ErrorApi(422, "faltan_campos", "Faltan datos obligatorios para confirmar el evento", {"faltan": bloquean})
    except ErrorApi:
        db.rollback()
        raise

    texto = "\n".join(t for t in (evento.titulo, evento.descripcion) if t)
    score, motivo_spam = clasificar_spam(texto, publicador)
    estado, motivo = decidir_estado(db, evento, publicador, score, motivo_spam)

    parecido = buscar_posible_duplicado(db, evento.titulo, evento.fecha_inicio, evento.municipio, excluir_id=evento.id)
    estado, motivo = motivo_con_duplicado(estado, motivo, parecido.titulo if parecido else None)

    evento.estado = estado
    evento.score_spam = score
    evento.motivo_moderacion = motivo
    # Solo pueden quedar opcionales (lugar, plazas…): no bloquean, pero el bot puede seguir pidiéndolos.
    evento.faltan = faltan
    avisos = []
    if estado == "en_revision":
        quien = publicador.nombre if publicador is not None else "sin publicador"
        avisos = notificar_moderadores(
            db, "moderacion", f"Evento para revisar: «{evento.titulo}» ({quien}). Motivo: {motivo}",
            evento_id=evento.id, enviar=False,
        )
    elif estado == "publicado":
        avisos = avisar_interesados(db, evento)  # A10
    db.commit()
    enviar_en_segundo_plano(background_tasks, db, avisos)
    return _resultado(db, evento, duplicado=False, status=200, posible_duplicado_de=parecido.id if parecido else None)
