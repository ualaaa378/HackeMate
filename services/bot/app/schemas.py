"""Modelos del bot. `ExtraccionEvento` sigue PLAN.md §5.2 hasta que exista
contracts/schemas/extraccion_evento.json; si el contrato cambia, se ajusta aquí."""

import re
import unicodedata
from typing import Any, Literal, Optional, get_args

from pydantic import BaseModel, Field, field_validator

Categoria = Literal["deportiva", "cultural", "fiestas", "gastronomia", "ludica", "comercio"]
CATEGORIAS = get_args(Categoria)
Confianza = Literal["alta", "media", "baja", "falta"]

MUNICIPIOS = ["Lucainena de las Torres", "Senés", "Velefique", "Uleila del Campo", "Tahal"]

# Campos que el bot intenta rellenar y, si faltan, pregunta al publicador
CAMPOS_EVENTO = [
    "titulo",
    "descripcion",
    "categoria",
    "municipio",
    "lugar",
    "fecha_inicio",
    "fecha_fin",
    "precio_eur",
    "es_gratuito",
    "plazas_totales",
]
CAMPOS_OBLIGATORIOS = ["titulo", "categoria", "municipio", "fecha_inicio"]


class FichaLLM(BaseModel):
    """Lo que le pedimos a la IA: plano y sencillo, para que valga como JSON Schema
    en las salidas estructuradas de Claude y de Gemini."""

    es_evento: bool = Field(description="True si el texto anuncia una actividad, oferta o evento concreto")
    titulo: Optional[str] = None
    descripcion: Optional[str] = Field(None, description="Resumen de 1-2 frases")
    categoria: Optional[Categoria] = None
    municipio: Optional[str] = Field(None, description="Uno de los municipios conocidos, si aparece")
    lugar: Optional[str] = Field(None, description="Sitio concreto dentro del pueblo")
    fecha_inicio: Optional[str] = Field(None, description="ISO 8601 con zona, p. ej. 2026-11-30T09:00:00+01:00")
    fecha_fin: Optional[str] = None
    precio_eur: Optional[float] = None
    es_gratuito: Optional[bool] = None
    plazas_totales: Optional[int] = None
    campos_dudosos: list[str] = Field(
        default_factory=list, description="Campos rellenados por deducción y no explícitos en el texto"
    )

    # Los modelos gratuitos a veces se salen un poco del esquema. Mejor normalizar
    # que tirar la ficha entera por una tilde o un «9€».
    @field_validator("categoria", mode="before")
    @classmethod
    def _categoria(cls, v):
        if not isinstance(v, str):
            return None
        v = "".join(c for c in unicodedata.normalize("NFD", v.lower().strip()) if unicodedata.category(c) != "Mn")
        return v if v in CATEGORIAS else None

    @field_validator("precio_eur", mode="before")
    @classmethod
    def _precio(cls, v):
        if isinstance(v, str):
            m = re.search(r"\d+(?:[.,]\d+)?", v)
            return float(m[0].replace(",", ".")) if m else None
        return v

    @field_validator("plazas_totales", mode="before")
    @classmethod
    def _plazas(cls, v):
        if isinstance(v, str):
            m = re.search(r"\d+", v)
            return int(m[0]) if m else None
        return v

    @field_validator("campos_dudosos", mode="before")
    @classmethod
    def _dudosos(cls, v):
        return v if isinstance(v, list) else []


class Campo(BaseModel):
    valor: Any = None
    confianza: Confianza = "falta"


class Tokens(BaseModel):
    entrada: int = 0
    salida: int = 0


class ExtraccionEvento(BaseModel):
    campos: dict[str, Campo]
    faltan: list[str]
    es_evento: bool
    proveedor_ia: str
    tokens: Tokens = Tokens()

    @classmethod
    def desde_ficha(cls, ficha: FichaLLM, proveedor: str, tokens: Tokens, confianza_base: Confianza = "alta"):
        datos = ficha.model_dump()
        campos: dict[str, Campo] = {}
        for nombre in CAMPOS_EVENTO:
            valor = datos.get(nombre)
            if valor is None:
                campos[nombre] = Campo(valor=None, confianza="falta")
            elif nombre in ficha.campos_dudosos:
                campos[nombre] = Campo(valor=valor, confianza="media")
            else:
                campos[nombre] = Campo(valor=valor, confianza=confianza_base)
        faltan = [n for n in CAMPOS_EVENTO if campos[n].confianza == "falta" and n not in ("fecha_fin", "es_gratuito")]
        # Si es gratis, no falta el precio
        if ficha.es_gratuito and "precio_eur" in faltan:
            faltan.remove("precio_eur")
        return cls(campos=campos, faltan=faltan, es_evento=ficha.es_evento, proveedor_ia=proveedor, tokens=tokens)

    def faltan_obligatorios(self) -> list[str]:
        return [c for c in CAMPOS_OBLIGATORIOS if c in self.faltan]


class MensajeEntrante(BaseModel):
    """Mensaje normalizado, venga de Twilio o de la consola."""

    canal: Literal["whatsapp", "telegram", "console"]
    de: str  # WhatsApp: teléfono E.164 con «+» (+34600000000) · Telegram: «tg:<chat_id>»
    nombre: Optional[str] = None  # nombre de perfil de WhatsApp, si lo da
    id_mensaje: Optional[str] = None  # para no procesar dos veces un reenvío del webhook
    texto: str = ""
    boton_id: Optional[str] = None  # id del botón pulsado (mensajes interactivos)
    media_url: Optional[str] = None  # Twilio: URL directa
    media_id: Optional[str] = None  # Meta: id que hay que descargar con el token
    media_tipo: Optional[str] = None
    lat: Optional[float] = None
    lon: Optional[float] = None
