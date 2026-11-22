"""«¿Qué hay este finde en Senés?» → filtros para GET /api/v1/eventos.

Búsqueda con lenguaje natural: «algo para ir con niños el domingo por la tarde cerca de Tahal».
- Lo concreto, por reglas (sin tokens): pueblo, tipo, día (también «el domingo»), franja («por la tarde»),
  «cerca de <pueblo>» (radio alrededor de ese pueblo) y «gratis».
- Lo blando («con niños», «al aire libre», «tranquilo», «con perro»…), con IA sobre los planes encontrados (FreeLLM
  primero, cadena de las tareas N): elige los que encajan y dice por qué, sin inventar. Sin IA, palabras clave."""

import json
import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from pydantic import BaseModel, Field

from app.agentes import extractor

RADIO_CERCA_KM = 15
DIAS = ("lunes", "martes", "miercoles", "jueves", "viernes", "sabado", "domingo")
DIAS_TILDE = ("lunes", "martes", "miércoles", "jueves", "viernes", "sábado", "domingo")
FRANJAS = {  # (hora desde, hora hasta, texto)
    "manana": (6, 14, "por la mañana"), "mediodia": (12, 16, "a mediodía"), "tarde": (14, 21, "por la tarde"),
    "noche": (19, 24, "por la noche"),
}
# Criterios blandos: clave → (palabras del mensaje, palabras que lo cumplen en la ficha, frase)
CRITERIOS = {
    "ninos": (r"ninos|peques|crios|nietos|hijos|familia|infantil|chiquillos|criaturas",
              r"nino|infantil|familia|familiar|peque|crio|escolar|todas las edades|cuentacuentos|juegos",
              "para ir con niños"),
    "aire_libre": (r"aire libre|al campo|naturaleza|por el monte|de campo",
                   r"ruta|senderismo|aire libre|campo|monte|sierra|plaza|excursion|paseo", "al aire libre"),
    "tranquilo": (r"tranquilo|mayores|sin andar mucho|sin caminar|accesible|para abuelos",
                  r"mayores|charla|cine|teatro|taller|exposicion|concierto|tertulia|tranquil", "tranquilos"),
    "perro": (r"perro|perros|mascota|mascotas", r"perro|mascota", "con perro"),
}


@dataclass
class Consulta:
    municipio: str | None = None
    categorias: list[str] = field(default_factory=list)
    desde: datetime | None = None
    hasta: datetime | None = None
    cerca: bool = False
    periodo: str = "los próximos días"
    franja: str | None = None  # clave de FRANJAS
    cerca_de: str | None = None  # «cerca de Tahal»: radio alrededor de ese pueblo
    gratis: bool = False
    criterios: list[str] = field(default_factory=list)  # claves de CRITERIOS
    centro: tuple[float, float] | None = None  # coordenadas de cerca_de (las pone vecino con la API)

    def parametros(self, lat: float | None = None, lon: float | None = None) -> dict:
        p: dict = {"size": 30 if (self.franja or self.gratis or self.criterios) else 10}
        if self.municipio:
            p["municipio"] = self.municipio
        if len(self.categorias) == 1:
            p["categoria"] = self.categorias[0]
        if self.desde:
            p["desde"] = self.desde.isoformat()
        if self.hasta:
            p["hasta"] = self.hasta.isoformat()
        if self.cerca_de and self.centro:
            p.update(lat=self.centro[0], lon=self.centro[1], radio_km=RADIO_CERCA_KM)
        elif self.cerca and lat is not None and lon is not None and not self.municipio:
            p.update(lat=lat, lon=lon, radio_km=RADIO_CERCA_KM)
        return p

    @property
    def detallada(self) -> bool:
        """Pide algo concreto: no se responde con las recomendaciones genéricas."""
        return bool(self.franja or self.cerca_de or self.gratis or self.criterios)

    def descripcion(self) -> str:
        """«para ir con niños el domingo 22/11 por la tarde cerca de Tahal», para la cabecera."""
        partes = [CRITERIOS[k][2] for k in self.criterios]
        if self.gratis:
            partes.append("gratis")
        partes.append(self.periodo)
        if self.franja:
            partes.append(FRANJAS[self.franja][2])
        if self.cerca_de:
            partes.append(f"cerca de {self.cerca_de}")
        elif self.municipio:
            partes.append(f"en {self.municipio}")
        return " ".join(partes)


def _dia(d: date, tz: ZoneInfo, fin: bool = False) -> datetime:
    return datetime.combine(d, time(23, 59) if fin else time(0, 0), tzinfo=tz)


def interpretar(texto: str, ahora: datetime) -> Consulta:
    tz = ahora.tzinfo
    hoy = ahora.date()
    t = extractor._normalizar(texto)
    c = Consulta(municipio=extractor.buscar_municipio(t))
    # «con niños» o «tranquilo» son criterios blandos, no un tipo de plan: no deciden la categoría
    sin_criterios = t
    for dice, _, _ in CRITERIOS.values():
        sin_criterios = re.sub(rf"\b({dice})\b", " ", sin_criterios)
    c.categorias = [cat for cat, palabras in extractor.PALABRAS_CATEGORIA.items()
                    if any(re.search(rf"\b{re.escape(p)}", sin_criterios) for p in palabras)]
    # «cerca de Tahal» primero; «por Tahal» después («por la tarde» no es un sitio)
    for patron in (r"\b(?:cerca del?|alrededor de|por la zona de|por los alrededores de) ([a-z]+(?: [a-z]+){0,3})",
                   r"\bpor (?!la |el |los |las )([a-z]+(?: [a-z]+){0,3})"):
        m = re.search(patron, t)
        if m and (pueblo := extractor.buscar_municipio(m[1])):
            c.cerca_de, c.municipio = pueblo, None  # radio alrededor del pueblo, no solo el pueblo
            break
    c.cerca = not c.cerca_de and bool(re.search(r"\b(cerca|cercano|cercanos|alrededor|por aqui|mi zona)\b", t))
    c.gratis = bool(re.search(r"\b(gratis|gratuit[oa]s?|sin pagar|que no cueste|sin coste)\b", t))
    c.criterios = [k for k, (dice, _, _) in CRITERIOS.items() if re.search(rf"\b({dice})\b", t)]
    if re.search(r"\bpor la manana|de manana\b|\bmatinal\b", t):
        c.franja = "manana"
    elif re.search(r"\ba mediodia\b|\bal mediodia\b", t):
        c.franja = "mediodia"
    elif re.search(r"\bpor la tarde|esta tarde|de tarde\b", t):
        c.franja = "tarde"
    elif re.search(r"\bpor la noche|esta noche|de noche\b", t):
        c.franja = "noche"
    dia_semana = next((i for i, d in enumerate(DIAS) if re.search(rf"\b{d}\b", t)), None)

    if dia_semana is not None and not re.search(r"\b(finde|fin de semana)\b", t):
        # «el domingo»: el próximo (hoy, si es hoy y aún no ha pasado la franja)
        dias = (dia_semana - hoy.weekday()) % 7
        if dias == 0 and c.franja and ahora.hour >= FRANJAS[c.franja][1]:
            dias = 7  # «el sábado por la mañana» dicho el sábado por la tarde: el de la semana que viene
        d = hoy + timedelta(days=dias)
        inicio = ahora if dias == 0 else _dia(d, tz)
        c.desde, c.hasta = inicio, _dia(d, tz, True)
        c.periodo = "hoy" if dias == 0 else f"el {DIAS_TILDE[dia_semana]} {d.strftime('%d/%m')}"
    elif re.search(r"\b(finde|fin de semana)\b", t):
        sabado = hoy + timedelta(days=(5 - hoy.weekday()) % 7)
        viernes = sabado - timedelta(days=1)
        inicio = max(ahora, datetime.combine(viernes, time(15, 0), tzinfo=tz)) if hoy.weekday() <= 4 else ahora
        c.desde, c.hasta, c.periodo = inicio, _dia(sabado + timedelta(days=1), tz, fin=True), "este fin de semana"
    elif re.search(r"\bpasado manana\b", t):
        d = hoy + timedelta(days=2)
        c.desde, c.hasta, c.periodo = _dia(d, tz), _dia(d, tz, True), "pasado mañana"
    elif re.search(r"\bmanana\b", t) and not re.search(r"\bpor la manana\b", t):
        d = hoy + timedelta(days=1)
        c.desde, c.hasta, c.periodo = _dia(d, tz), _dia(d, tz, True), "mañana"
    elif re.search(r"\b(hoy|esta tarde|esta noche)\b", t):
        c.desde, c.hasta, c.periodo = ahora, _dia(hoy, tz, True), "hoy"
    elif re.search(r"\besta semana\b", t):
        domingo = hoy + timedelta(days=6 - hoy.weekday())
        c.desde, c.hasta, c.periodo = ahora, _dia(domingo, tz, True), "esta semana"
    elif re.search(r"\beste mes\b", t):
        c.desde, c.hasta, c.periodo = ahora, ahora + timedelta(days=30), "este mes"
    elif (d := extractor._fecha(t, hoy)) is not None:
        c.desde, c.hasta, c.periodo = _dia(d, tz), _dia(d, tz, True), f"el {d.strftime('%d/%m')}"
    else:
        c.desde, c.hasta = ahora, ahora + timedelta(days=30)
    return c


# ---------- Filtros sobre los planes encontrados ----------

def en_franja(ev: dict, franja: str | None, tz: ZoneInfo) -> bool:
    if not franja:
        return True
    try:
        hora = datetime.fromisoformat(ev["fecha_inicio"]).astimezone(tz).hour
    except (KeyError, TypeError, ValueError):
        return False
    desde, hasta, _ = FRANJAS[franja]
    return desde <= hora < hasta


def es_gratis(ev: dict) -> bool:
    return bool(ev.get("es_gratuito")) or ev.get("precio_eur") in (0, 0.0)


class _Elegido(BaseModel):
    evento_id: str
    motivo: str = Field(description="Por qué encaja, en una frase corta, solo con lo que dice la ficha")


class _Afinado(BaseModel):
    elegidos: list[_Elegido] = Field(default_factory=list)


SYSTEM_AFINAR = """Ayudas a buscar planes en la agenda de unos pueblos de Almería.
Recibes lo que pide una persona y una lista de planes en JSON. Devuelve SOLO los que encajan con lo que pide
({criterios}), del que más al que menos, con un motivo breve basado únicamente en la ficha (título, descripción,
etiquetas, hora, precio). Si un plan no dice nada que lo relacione, no lo incluyas. No inventes datos."""


def _por_palabras(eventos: list[dict], criterios: list[str]) -> list[tuple[dict, str]]:
    elegidos = []
    for ev in eventos:
        texto = extractor._normalizar(" ".join([ev.get("titulo") or "", ev.get("descripcion") or "",
                                                " ".join(ev.get("etiquetas") or [])]))
        cumple = [CRITERIOS[k][2] for k in criterios if re.search(CRITERIOS[k][1], texto)]
        if len(cumple) == len(criterios):
            elegidos.append((ev, "Encaja: " + ", ".join(cumple)))
    return elegidos


def afinar(texto: str, eventos: list[dict], c: "Consulta") -> tuple[list[dict], dict[str, str], str]:
    """Criterios blandos sobre los planes ya filtrados: (planes que encajan, motivos por id, proveedor)."""
    from app.config import get_settings
    from app.llm import router

    if not c.criterios or not eventos:
        return eventos, {}, "reglas"
    candidatos = eventos[:15]
    datos = [{"evento_id": e["id"], "titulo": e.get("titulo"), "descripcion": (e.get("descripcion") or "")[:300],
              "etiquetas": e.get("etiquetas") or [], "categoria": e.get("categoria"),
              "fecha_inicio": e.get("fecha_inicio"), "gratis": es_gratis(e)} for e in candidatos]
    criterios = ", ".join(CRITERIOS[k][2] for k in c.criterios)

    def reglas(_t: str) -> _Afinado:
        return _Afinado(elegidos=[_Elegido(evento_id=e["id"], motivo=m) for e, m in _por_palabras(candidatos,
                                                                                                c.criterios)])

    res = router.estructurado(
        tarea="buscar_lenguaje_natural",
        system=SYSTEM_AFINAR.format(criterios=criterios),
        texto=f"Pide: {texto}\n\nPlanes:\n{json.dumps(datos, ensure_ascii=False)}",
        salida=_Afinado, reglas=reglas, cadena=get_settings().proveedores_tareas_n,
    )
    por_id = {e["id"]: e for e in candidatos}
    elegidos = [(por_id[x.evento_id], x.motivo) for x in res.salida.elegidos if x.evento_id in por_id]
    return [e for e, _ in elegidos], {e["id"]: m for e, m in elegidos}, res.proveedor
