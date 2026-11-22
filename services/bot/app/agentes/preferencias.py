"""«Me gustan las rutas y las fiestas» → gustos estructurados (POST /ai/preferencias).
Reglas primero; la IA solo si las reglas no encuentran ninguna categoría."""

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.agentes import extractor
from app.llm import router
from app.schemas import Categoria


class Preferencias(BaseModel):
    gustos: list[Categoria] = Field(default_factory=list)
    etiquetas_interes: list[str] = Field(default_factory=list, description="Gustos más finos: senderismo, teatro…")
    municipio: Optional[str] = None
    formato_aviso: Optional[Literal["texto", "audio"]] = None
    proveedor_ia: str = "reglas"


class _PrefLLM(BaseModel):
    gustos: list[Categoria] = Field(default_factory=list,
                                    description="deportiva, cultural, fiestas, gastronomia, ludica o comercio")
    etiquetas_interes: list[str] = Field(default_factory=list)
    municipio: Optional[str] = None
    formato_aviso: Optional[Literal["texto", "audio"]] = None


SYSTEM = """Convierte lo que dice un vecino sobre sus gustos en preferencias para una agenda de pueblos de Almería
(Lucainena de las Torres, Senés, Velefique, Uleila del Campo, Tahal).
Categorías: deportiva (rutas, senderismo, bici, fútbol), cultural (teatro, música, museos, charlas, talleres),
fiestas, gastronomia (comidas, tapas, migas), ludica (juegos, actividades infantiles), comercio (ofertas).
formato_aviso = "audio" solo si pide que le avisen con audios o notas de voz. No inventes."""


def _por_reglas(texto: str) -> Preferencias:
    t = extractor._normalizar(texto)
    gustos = [c for c, palabras in extractor.PALABRAS_CATEGORIA.items()
              if any(re.search(rf"\b{re.escape(p)}", t) for p in palabras)]
    etiquetas = [p for palabras in extractor.PALABRAS_CATEGORIA.values() for p in palabras
                 if len(p) > 3 and re.search(rf"\b{re.escape(p)}", t)]
    formato = "audio" if re.search(r"\b(audio|audios|nota de voz|notas de voz|por voz)\b", t) else None
    return Preferencias(gustos=gustos, etiquetas_interes=etiquetas[:5],
                        municipio=extractor.buscar_municipio(t), formato_aviso=formato)


def interpretar(texto: str) -> Preferencias:
    base = _por_reglas(texto)
    if base.gustos:
        return base  # las reglas ya lo han entendido: no gastamos tokens
    res = router.estructurado(
        tarea="preferencias", system=SYSTEM, texto=texto, salida=_PrefLLM,
        reglas=lambda _t: _PrefLLM(**base.model_dump(exclude={"proveedor_ia"})),
    )
    if res.proveedor == "reglas":
        return base
    ia = res.salida
    return Preferencias(gustos=ia.gustos, etiquetas_interes=ia.etiquetas_interes[:5],
                        municipio=extractor.buscar_municipio(ia.municipio or "") or base.municipio,
                        formato_aviso=ia.formato_aviso or base.formato_aviso, proveedor_ia=res.proveedor)
