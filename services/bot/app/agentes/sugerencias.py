"""Sugerencias de planes nuevos para los administradores (POST /ai/sugerir-eventos, tarea N8; la usa la API en N7).

Recibe los planes con más participación y propone de 1 a 3 planes nuevos. La IA solo propone: cada propuesta dice en
qué planes se basa y por qué, con las cifras que llegan (no inventa ninguna). Se descarta lo que no cuadre (categoría
o pueblo que no existen, planes en que se basa que no se han mandado). Sin IA, propuestas por reglas: repetir los
planes que más se llenaron."""

import json
from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm import router
from app.schemas import MUNICIPIOS

CATEGORIAS = ("deportiva", "cultural", "fiestas", "gastronomia", "ludica", "comercio")
MESES = ["enero", "febrero", "marzo", "abril", "mayo", "junio", "julio", "agosto", "septiembre", "octubre",
         "noviembre", "diciembre"]


class PlanParticipacion(BaseModel):
    evento_id: Optional[str] = None
    titulo: str
    categoria: str
    municipio: str
    fecha_inicio: datetime
    plazas_totales: Optional[int] = Field(default=None, ge=0)
    inscritos: int = Field(ge=0)
    lista_espera: int = Field(default=0, ge=0)
    preguntas_chat: int = Field(default=0, ge=0)


class PeticionSugerencias(BaseModel):
    planes: list[PlanParticipacion] = Field(min_length=1, max_length=20)
    maximo: int = Field(default=3, ge=1, le=3)


class Propuesta(BaseModel):
    titulo: str = Field(max_length=120)
    categoria: str
    municipio: str
    fecha_aproximada: Optional[str] = None
    motivo: str
    basado_en: list[str] = Field(default_factory=list)


class Sugerencias(BaseModel):
    propuestas: list[Propuesta] = Field(default_factory=list)
    proveedor_ia: str = "reglas"


class _SugerenciasLLM(BaseModel):
    propuestas: list[Propuesta] = Field(default_factory=list, description="De 1 a 3 propuestas")


SYSTEM = """Ayudas a los administradores de una agenda de actividades de cinco pueblos de Almería ({municipios}).
Recibes en JSON los planes que más participación tuvieron (inscritos, plazas, lista de espera, preguntas en el chat).
Propón de 1 a {maximo} planes NUEVOS que merezca la pena organizar: repetir uno que se llenó, hacer una versión en otro
pueblo cercano, otra fecha para quienes se quedaron en lista de espera…
Reglas: usa solo las categorías {categorias} y los pueblos de la lista. En «motivo» explica el porqué con las cifras
del JSON (no inventes cifras ni datos). En «basado_en» pon los evento_id de los planes en que te basas.
«fecha_aproximada» es texto libre y prudente («primavera», «el próximo mes»). Título breve y concreto, en español."""


def _ocupacion(p: PlanParticipacion) -> float | None:
    return p.inscritos / p.plazas_totales if p.plazas_totales else None


def _interes(p: PlanParticipacion) -> float:
    """Para ordenar: lo que se llenó y dejó gente fuera, primero."""
    ocupacion = _ocupacion(p)
    return (ocupacion if ocupacion is not None else min(p.inscritos / 30, 1)) + p.lista_espera * 0.15 + \
        p.preguntas_chat * 0.05


def _motivo(p: PlanParticipacion) -> str:
    partes = []
    if p.plazas_totales:
        partes.append(f"{p.inscritos} de {p.plazas_totales} plazas ocupadas" +
                      (" (se llenó)" if p.inscritos >= p.plazas_totales else ""))
    else:
        partes.append(f"{p.inscritos} inscritos")
    if p.lista_espera:
        partes.append(f"{p.lista_espera} en lista de espera")
    if p.preguntas_chat:
        partes.append(f"{p.preguntas_chat} preguntas en el chat")
    return f"«{p.titulo}» tuvo mucha participación: " + ", ".join(partes) + "."


def con_reglas(peticion: PeticionSugerencias) -> Sugerencias:
    ordenados = sorted(peticion.planes, key=_interes, reverse=True)
    propuestas = []
    for p in ordenados[:peticion.maximo]:
        if p.categoria not in CATEGORIAS or p.municipio not in MUNICIPIOS:
            continue
        cuando = None
        if p.lista_espera:
            cuando = "pronto, para quienes se quedaron en lista de espera"
        propuestas.append(Propuesta(
            titulo=f"Otra edición: {p.titulo}"[:120], categoria=p.categoria, municipio=p.municipio,
            fecha_aproximada=cuando, motivo=_motivo(p), basado_en=[p.evento_id] if p.evento_id else []))
    return Sugerencias(propuestas=propuestas)


def _validas(propuestas: list[Propuesta], peticion: PeticionSugerencias) -> list[Propuesta]:
    ids = {p.evento_id for p in peticion.planes if p.evento_id}
    buenas = []
    for pr in propuestas:
        if pr.categoria not in CATEGORIAS or pr.municipio not in MUNICIPIOS or not pr.titulo.strip() \
                or not pr.motivo.strip():
            continue
        pr.basado_en = [i for i in pr.basado_en if i in ids]  # nada que no se haya mandado
        buenas.append(pr)
    return buenas[:peticion.maximo]


def sugerir(peticion: PeticionSugerencias) -> Sugerencias:
    datos = [{**p.model_dump(mode="json"), "ocupacion": round(_ocupacion(p), 2) if _ocupacion(p) is not None else None,
              "mes": MESES[p.fecha_inicio.month - 1]} for p in peticion.planes]
    res = router.estructurado(
        tarea="sugerir_eventos",
        system=SYSTEM.format(municipios=", ".join(MUNICIPIOS), maximo=peticion.maximo,
                             categorias=", ".join(CATEGORIAS)),
        texto=json.dumps(datos, ensure_ascii=False),
        salida=_SugerenciasLLM,
        reglas=lambda _t: _SugerenciasLLM(propuestas=con_reglas(peticion).propuestas),
        cadena=get_settings().proveedores_tareas_n,  # N8: FreeLLM primero
    )
    if res.proveedor == "reglas":
        return con_reglas(peticion)
    buenas = _validas(res.salida.propuestas, peticion)
    if not buenas:  # la IA no dio nada que valga: mejor las reglas que nada
        return con_reglas(peticion)
    return Sugerencias(propuestas=buenas, proveedor_ia=res.proveedor)
