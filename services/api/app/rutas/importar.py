"""Ingesta: el bot entrega lo que la IA ha sacado de un post, cartel o audio (E1.6, adelanto de H2.1).

El evento se crea en `pendiente_confirmacion`: no lo ve nadie hasta que el publicador confirma (H2.3).
La IA propone; aquí se valida cada campo y lo que no sirve cuenta como que falta.
"""

import unicodedata
from datetime import datetime
from typing import Annotated, Any, Literal

from fastapi import APIRouter, Depends
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.canales import buscar_publicador_por_contacto, validar_contacto
from app.db import get_db
from app.errores import ErrorApi
from app.modelos import CANALES, CATEGORIAS, Evento, Fuente, Municipio, Publicador, ahora
from app.rutas.eventos import _buscar, _con_zona, _ficha
from app.rutas.publico import es_uuid
from app.seguridad import exigir_token_interno

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


def _plegar(texto: str) -> str:
    """Sin tildes ni mayúsculas: la IA puede escribir «Senes» o «SENÉS»."""
    return "".join(c for c in unicodedata.normalize("NFKD", texto) if not unicodedata.combining(c)).casefold().strip()


def _municipio(db: Session, valor: Any) -> Municipio | None:
    nombre = _texto(valor)
    if nombre is None:
        return None
    exacto = db.get(Municipio, nombre)
    if exacto is not None:
        return exacto
    buscado = _plegar(nombre)
    return next((m for m in db.scalars(select(Municipio)).all() if _plegar(m.nombre) == buscado), None)


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
    if publicador is not None and publicador.estado == "pausado":
        raise ErrorApi(403, "publicador_pausado", "El publicador está pausado y no puede publicar")
    # H2.4: según el estado y el nivel de confianza del publicador se decidirá luego la moderación.
    return publicador


def _resultado(db: Session, evento: Evento, duplicado: bool, status: int) -> JSONResponse:
    cuerpo = {
        "evento": _ficha(db, _buscar(db, evento.id)),
        "faltan": list(evento.faltan or []),
        "duplicado": duplicado,
        "posible_duplicado_de": None,
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
        existente = db.scalar(select(Evento).where(Evento.origen_url == url).order_by(Evento.creado_en))
        if existente is not None:
            return _resultado(db, existente, duplicado=True, status=200)
    # H2.2: si no hay mismo origen.url, buscar uno parecido (título + fecha + municipio) por encima de un
    # umbral y devolverlo en `posible_duplicado_de` (se crea igualmente).

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
        imagen_url=_texto(_valor(campos, "imagen_url")),
        estado="pendiente_confirmacion",
        publicador_id=publicador.id if publicador else None,
        origen_canal=datos.origen.canal,
        origen_url=url,
        importado_auto=datos.origen.importado_auto,
        extraccion=extraccion.model_dump(mode="json"),
        faltan=faltan,
    )
    # H2.4: moderación y niveles de confianza (score_spam, en_revision/publicado) al confirmar (H2.3).
    db.add(evento)
    db.commit()
    return _resultado(db, evento, duplicado=False, status=201)
