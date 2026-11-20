"""Tablas de la API. Los nombres de los campos siguen contracts/schemas/*.json.

- IDs: UUID v4 como texto (igual en SQLite y PostgreSQL).
- Enums: texto con CHECK (no tipos nativos), para que SQLite y PostgreSQL se comporten igual.
- Fechas: con zona; se guardan en UTC y la API las devuelve en Europe/Madrid.
- Las preferencias del usuario (gustos, radio, formato de aviso) viven en la tabla usuarios.
"""

import uuid
from datetime import datetime, timezone

from zoneinfo import ZoneInfo

from sqlalchemy import JSON, Boolean, CheckConstraint, DateTime, Enum, Float, ForeignKey, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship
from sqlalchemy.types import TypeDecorator

from app.db import Base

# Valores de contracts/enums.md
CATEGORIAS = ("deportiva", "cultural", "fiestas", "gastronomia", "ludica", "comercio")
ESTADOS_EVENTO = (
    "borrador", "pendiente_confirmacion", "en_revision", "publicado",
    "rechazado", "cancelado", "finalizado", "archivado",
)
ESTADOS_PUBLICADOR = ("solicitado", "whatsapp_verificado", "aprobado", "rechazado", "pausado")
TIPOS_PUBLICADOR = ("asociacion", "ayuntamiento", "bar_restaurante", "comercio", "otro")
ROLES = ("vecino", "publicador", "moderador")
ROLES_AUTOR = ROLES + ("ia",)
ESTADOS_INSCRIPCION = ("confirmada", "lista_espera", "cancelada", "asistio", "no_asistio")
CANALES = ("whatsapp", "web", "panel", "facebook", "instagram", "web_externa", "manual", "telegram")
TIPOS_NOTIFICACION = ("recomendacion", "cambio_evento", "anuncio", "respuesta", "moderacion", "confirmacion")
FORMATOS_AVISO = ("texto", "audio")
TIPOS_MENSAJE = ("pregunta", "respuesta", "anuncio", "comentario")
TIPOS_LUGAR = ("ruta", "sitio_interes", "comercio", "alojamiento", "servicio")
ESTADOS_ENVIO = ("pendiente", "enviada", "fallida")


class FechaUTC(TypeDecorator):
    """Fecha con zona. Se guarda en UTC y se lee siempre con zona (SQLite no guarda la zona por sí solo).
    Una fecha sin zona se interpreta como hora de Madrid."""

    impl = DateTime(timezone=True)
    cache_ok = True

    def process_bind_param(self, valor, dialect):
        if valor is None:
            return None
        if valor.tzinfo is None:
            valor = valor.replace(tzinfo=ZoneInfo("Europe/Madrid"))
        return valor.astimezone(timezone.utc)

    def process_result_value(self, valor, dialect):
        if valor is None:
            return None
        return valor.replace(tzinfo=timezone.utc) if valor.tzinfo is None else valor.astimezone(timezone.utc)


def _enum(nombre: str, valores: tuple[str, ...]) -> Enum:
    return Enum(*valores, name=nombre, native_enum=False, create_constraint=True, length=32)


def nuevo_id() -> str:
    return str(uuid.uuid4())


def ahora() -> datetime:
    return datetime.now(timezone.utc)


def _id() -> Mapped[str]:
    return mapped_column(String(36), primary_key=True, default=nuevo_id)


def _creado() -> Mapped[datetime]:
    return mapped_column(FechaUTC(), default=ahora, nullable=False)


class Municipio(Base):
    __tablename__ = "municipios"

    nombre: Mapped[str] = mapped_column(String(80), primary_key=True)
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)


class Lugar(Base):
    __tablename__ = "lugares"

    id: Mapped[str] = _id()
    nombre: Mapped[str] = mapped_column(String(200), nullable=False)
    tipo: Mapped[str] = mapped_column(_enum("tipo_lugar", TIPOS_LUGAR), nullable=False, index=True)
    municipio: Mapped[str] = mapped_column(ForeignKey("municipios.nombre"), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    direccion: Mapped[str | None] = mapped_column(String(300))
    telefono: Mapped[str | None] = mapped_column(String(40))
    web: Mapped[str | None] = mapped_column(String(500))
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    coordenadas_exactas: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ruta: Mapped[dict | None] = mapped_column(JSON)
    fuentes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)


class Usuario(Base):
    __tablename__ = "usuarios"

    id: Mapped[str] = _id()
    nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    rol: Mapped[str] = mapped_column(_enum("rol", ROLES), default="vecino", nullable=False)
    telefono: Mapped[str | None] = mapped_column(String(16), unique=True)
    whatsapp_verificado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    email: Mapped[str | None] = mapped_column(String(254), unique=True)
    google_sub: Mapped[str | None] = mapped_column(String(64), unique=True)  # login con Google (H3)
    telegram_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)  # chat_id (app/canales.py)
    municipio: Mapped[str | None] = mapped_column(ForeignKey("municipios.nombre"))
    lat: Mapped[float | None] = mapped_column(Float)
    lon: Mapped[float | None] = mapped_column(Float)
    gustos: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    etiquetas_interes: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    formato_aviso: Mapped[str] = mapped_column(_enum("formato_aviso", FORMATOS_AVISO), default="texto", nullable=False)
    acepta_avisos: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    radio_km: Mapped[float | None] = mapped_column(Float)
    publicador_id: Mapped[str | None] = mapped_column(ForeignKey("publicadores.id", use_alter=True))
    creado_en: Mapped[datetime] = _creado()


class Publicador(Base):
    __tablename__ = "publicadores"
    __table_args__ = (CheckConstraint("nivel_confianza IN (0, 1, 2)", name="nivel_confianza"),)

    id: Mapped[str] = _id()
    nombre: Mapped[str] = mapped_column(String(160), nullable=False)
    tipo: Mapped[str] = mapped_column(_enum("tipo_publicador", TIPOS_PUBLICADOR), nullable=False)
    municipio: Mapped[str] = mapped_column(ForeignKey("municipios.nombre"), nullable=False, index=True)
    descripcion: Mapped[str | None] = mapped_column(Text)
    telefono: Mapped[str | None] = mapped_column(String(16), index=True)
    email: Mapped[str | None] = mapped_column(String(254))
    telegram_id: Mapped[str | None] = mapped_column(String(32), unique=True, index=True)  # chat_id (app/canales.py)
    estado: Mapped[str] = mapped_column(
        _enum("estado_publicador", ESTADOS_PUBLICADOR), default="solicitado", nullable=False, index=True
    )
    nivel_confianza: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    aprobaciones: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    automatizaciones_pausadas: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    categorias_habituales: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id"))
    creado_en: Mapped[datetime] = _creado()

    fuentes: Mapped[list["Fuente"]] = relationship(
        back_populates="publicador", cascade="all, delete-orphan", order_by="Fuente.creado_en"
    )


class Fuente(Base):
    """Página de Facebook, Instagram o web que el bot vigila en nombre de un publicador."""

    __tablename__ = "fuentes"

    id: Mapped[str] = _id()
    publicador_id: Mapped[str] = mapped_column(ForeignKey("publicadores.id", ondelete="CASCADE"), nullable=False)
    canal: Mapped[str] = mapped_column(_enum("canal_fuente", CANALES), nullable=False)
    url: Mapped[str] = mapped_column(String(500), nullable=False, unique=True)
    activa: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    creado_en: Mapped[datetime] = _creado()

    publicador: Mapped[Publicador] = relationship(back_populates="fuentes")


class Evento(Base):
    __tablename__ = "eventos"

    id: Mapped[str] = _id()
    titulo: Mapped[str] = mapped_column(String(120), nullable=False)
    descripcion: Mapped[str | None] = mapped_column(Text)
    categoria: Mapped[str] = mapped_column(_enum("categoria", CATEGORIAS), nullable=False, index=True)
    etiquetas: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    municipio: Mapped[str] = mapped_column(ForeignKey("municipios.nombre"), nullable=False, index=True)
    lugar: Mapped[str | None] = mapped_column(String(300))
    lat: Mapped[float] = mapped_column(Float, nullable=False)
    lon: Mapped[float] = mapped_column(Float, nullable=False)
    fecha_inicio: Mapped[datetime] = mapped_column(FechaUTC(), nullable=False, index=True)
    fecha_fin: Mapped[datetime | None] = mapped_column(FechaUTC())
    precio_eur: Mapped[float | None] = mapped_column(Float)
    es_gratuito: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    plazas_totales: Mapped[int | None] = mapped_column(Integer)
    plazas_libres: Mapped[int | None] = mapped_column(Integer)
    estado: Mapped[str] = mapped_column(
        _enum("estado_evento", ESTADOS_EVENTO), default="borrador", nullable=False, index=True
    )
    publicador_id: Mapped[str | None] = mapped_column(ForeignKey("publicadores.id"), index=True)
    imagen_url: Mapped[str | None] = mapped_column(String(500))
    # origen
    origen_canal: Mapped[str] = mapped_column(_enum("canal_origen", CANALES), default="manual", nullable=False)
    origen_url: Mapped[str | None] = mapped_column(String(500), index=True)  # duplicados (H2)
    importado_auto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # moderacion
    motivo_moderacion: Mapped[str | None] = mapped_column(Text)
    score_spam: Mapped[float | None] = mapped_column(Float)
    revisado_por: Mapped[str | None] = mapped_column(String(120))
    # Lo que propuso la IA al importar y lo que aún falta (H2)
    extraccion: Mapped[dict | None] = mapped_column(JSON)
    faltan: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    creado_en: Mapped[datetime] = _creado()
    actualizado_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora, onupdate=ahora, nullable=False)

    publicador: Mapped[Publicador | None] = relationship()


class Inscripcion(Base):
    __tablename__ = "inscripciones"
    __table_args__ = (UniqueConstraint("evento_id", "usuario_id", name="uq_inscripciones_evento_usuario"),)

    id: Mapped[str] = _id()
    evento_id: Mapped[str] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), nullable=False, index=True)
    estado: Mapped[str] = mapped_column(_enum("estado_inscripcion", ESTADOS_INSCRIPCION), nullable=False)
    posicion_espera: Mapped[int | None] = mapped_column(Integer)
    plazas: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    canal: Mapped[str] = mapped_column(_enum("canal_inscripcion", CANALES), default="web", nullable=False)
    creado_en: Mapped[datetime] = _creado()
    actualizado_en: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora, onupdate=ahora, nullable=False)


class MensajeEvento(Base):
    __tablename__ = "mensajes_evento"

    id: Mapped[str] = _id()
    evento_id: Mapped[str] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"), nullable=False, index=True)
    autor_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    autor_nombre: Mapped[str] = mapped_column(String(120), nullable=False)
    autor_rol: Mapped[str] = mapped_column(_enum("autor_rol", ROLES_AUTOR), nullable=False)
    tipo: Mapped[str] = mapped_column(_enum("tipo_mensaje", TIPOS_MENSAJE), nullable=False)
    texto: Mapped[str] = mapped_column(String(1000), nullable=False)
    en_respuesta_a: Mapped[str | None] = mapped_column(ForeignKey("mensajes_evento.id", ondelete="SET NULL"))
    fijado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    oculto: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    respondido_por_ia: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    score_spam: Mapped[float | None] = mapped_column(Float)
    creado_en: Mapped[datetime] = _creado()


class Silenciado(Base):
    """Usuario silenciado en el chat de un evento (PATCH .../mensajes/{msg_id} con `silenciar_autor`).
    `por`: id del organizador o moderador que lo silencia (texto, sin FK: puede ser el bot)."""

    __tablename__ = "silenciados"

    evento_id: Mapped[str] = mapped_column(ForeignKey("eventos.id", ondelete="CASCADE"), primary_key=True)
    usuario_id: Mapped[str] = mapped_column(ForeignKey("usuarios.id", ondelete="CASCADE"), primary_key=True)
    creado_en: Mapped[datetime] = _creado()
    por: Mapped[str | None] = mapped_column(String(120))


class Notificacion(Base):
    """Cola de avisos: la API los pide al bot con POST /notify; si el bot está caído quedan pendientes (H4.5).
    Ver app/notificaciones.py."""

    __tablename__ = "notificaciones"

    id: Mapped[str] = _id()
    # Opcional en la tabla (usuarios solo de Telegram), pero el contrato de /notify lo exige para enviar.
    telefono: Mapped[str | None] = mapped_column(String(16))
    contacto: Mapped[str | None] = mapped_column(String(32))  # `+34…` o `tg:<chat_id>` (app/canales.py)
    tipo: Mapped[str] = mapped_column(_enum("tipo_notificacion", TIPOS_NOTIFICACION), nullable=False)
    texto: Mapped[str] = mapped_column(Text, nullable=False)
    formato: Mapped[str] = mapped_column(_enum("formato_notificacion", FORMATOS_AVISO), default="texto", nullable=False)
    usuario_id: Mapped[str | None] = mapped_column(ForeignKey("usuarios.id", ondelete="SET NULL"))
    evento_id: Mapped[str | None] = mapped_column(ForeignKey("eventos.id", ondelete="SET NULL"))
    botones: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    # Plantilla de WhatsApp para avisos fuera de la ventana de 24 h; se guarda para poder reintentar
    plantilla: Mapped[str | None] = mapped_column(String(64))
    parametros: Mapped[list | None] = mapped_column(JSON)
    estado_envio: Mapped[str] = mapped_column(
        _enum("estado_envio", ESTADOS_ENVIO), default="pendiente", nullable=False, index=True
    )
    intentos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    ultimo_error: Mapped[str | None] = mapped_column(Text)
    creado_en: Mapped[datetime] = _creado()
    enviada_en: Mapped[datetime | None] = mapped_column(FechaUTC())


class CodigoVerificacion(Base):
    """Código de un solo uso para verificar un teléfono (POST /auth/whatsapp/codigo y /verificar).
    Solo se guarda el HMAC del código (app/rutas/auth.py), nunca el código."""

    __tablename__ = "codigos_verificacion"

    id: Mapped[str] = _id()
    telefono: Mapped[str] = mapped_column(String(16), nullable=False, index=True)
    codigo_hash: Mapped[str] = mapped_column(String(64), nullable=False)
    expira_en: Mapped[datetime] = mapped_column(FechaUTC(), nullable=False)
    intentos: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    usado: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    creado_en: Mapped[datetime] = _creado()


class MetricaTokens(Base):
    """Una llamada a la IA registrada por el bot (POST /metrics/tokens)."""

    __tablename__ = "metricas_tokens"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    proveedor: Mapped[str] = mapped_column(String(40), nullable=False, index=True)
    modelo: Mapped[str | None] = mapped_column(String(80))
    tarea: Mapped[str] = mapped_column(String(60), nullable=False)
    tokens_entrada: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    tokens_salida: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    latencia_ms: Mapped[int | None] = mapped_column(Integer)
    ok: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    ts: Mapped[datetime] = mapped_column(FechaUTC(), default=ahora, nullable=False, index=True)
