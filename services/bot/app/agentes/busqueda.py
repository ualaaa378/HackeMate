"""«¿Qué hay este finde en Senés?» → filtros para GET /api/v1/eventos. Solo reglas (sin tokens)."""

import re
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from zoneinfo import ZoneInfo

from app.agentes import extractor

RADIO_CERCA_KM = 15


@dataclass
class Consulta:
    municipio: str | None = None
    categorias: list[str] = field(default_factory=list)
    desde: datetime | None = None
    hasta: datetime | None = None
    cerca: bool = False
    periodo: str = "los próximos días"

    def parametros(self, lat: float | None = None, lon: float | None = None) -> dict:
        p: dict = {"size": 10}
        if self.municipio:
            p["municipio"] = self.municipio
        if len(self.categorias) == 1:
            p["categoria"] = self.categorias[0]
        if self.desde:
            p["desde"] = self.desde.isoformat()
        if self.hasta:
            p["hasta"] = self.hasta.isoformat()
        if self.cerca and lat is not None and lon is not None and not self.municipio:
            p.update(lat=lat, lon=lon, radio_km=RADIO_CERCA_KM)
        return p


def _dia(d: date, tz: ZoneInfo, fin: bool = False) -> datetime:
    return datetime.combine(d, time(23, 59) if fin else time(0, 0), tzinfo=tz)


def interpretar(texto: str, ahora: datetime) -> Consulta:
    tz = ahora.tzinfo
    hoy = ahora.date()
    t = extractor._normalizar(texto)
    c = Consulta(municipio=extractor.buscar_municipio(t))
    c.categorias = [cat for cat, palabras in extractor.PALABRAS_CATEGORIA.items()
                    if any(re.search(rf"\b{re.escape(p)}", t) for p in palabras)]
    c.cerca = bool(re.search(r"\b(cerca|cercano|cercanos|alrededor|por aqui|mi zona)\b", t))

    if re.search(r"\b(finde|fin de semana)\b", t):
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
