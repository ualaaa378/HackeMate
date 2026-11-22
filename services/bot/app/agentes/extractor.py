"""Extractor de eventos: texto de un post/mensaje → ExtraccionEvento validada."""

import re
import unicodedata
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

from app.config import get_settings
from app.llm import router
from app.schemas import MUNICIPIOS, ExtraccionEvento, FichaLLM, Tokens

SYSTEM = """Eres el extractor de eventos de una plataforma de los pueblos de Almería ({municipios}).
Recibes el texto de un post de Facebook, un cartel transcrito o un mensaje de WhatsApp.
Rellena la ficha SOLO con lo que diga el texto. Si un dato no aparece, déjalo a null: no lo inventes.
Si deduces un dato que no está explícito (p. ej. el año, o la categoría), añádelo a campos_dudosos.
Fechas en ISO 8601 con zona {zona} (hoy es {hoy}); si no se dice el año, usa la próxima fecha futura.
Categorías: deportiva, cultural, fiestas, gastronomia, ludica, comercio (ofertas y promociones de negocios).
Si el texto no anuncia nada concreto (un saludo, spam, una pregunta), pon es_evento=false.
El texto puede venir de una nota de voz transcrita o de un cartel leído por OCR: corrige nombres de pueblos
mal escritos (p. ej. «Belefique» es Velefique, «Senes» es Senés) y usa siempre el nombre oficial."""


def extraer(texto: str, hoy: date | None = None) -> ExtraccionEvento:
    s = get_settings()
    tz = ZoneInfo(s.zona_horaria)
    hoy = hoy or datetime.now(tz).date()
    system = SYSTEM.format(municipios=", ".join(MUNICIPIOS), zona=s.zona_horaria, hoy=hoy.isoformat())
    res = router.estructurado(
        tarea="extraer_evento",
        system=system,
        texto=texto,
        salida=FichaLLM,
        reglas=lambda t: extraer_con_reglas(t, hoy, tz),
    )
    confianza = "baja" if res.proveedor == "reglas" else "alta"
    return ExtraccionEvento.desde_ficha(
        res.salida,
        proveedor=res.proveedor,
        tokens=Tokens(entrada=res.tokens_entrada, salida=res.tokens_salida),
        confianza_base=confianza,
    )


# ---------- Plan C: reglas sin IA ----------

MESES = {m: i for i, m in enumerate(
    "enero febrero marzo abril mayo junio julio agosto septiembre octubre noviembre diciembre".split(), 1)}
DIAS_SEMANA = {d: i for i, d in enumerate("lunes martes miercoles jueves viernes sabado domingo".split())}

PALABRAS_CATEGORIA = {
    "deportiva": ["ruta", "senderismo", "carrera", "torneo", "futbol", "bici", "marcha", "padel", "deport"],
    "fiestas": ["fiesta", "verbena", "romeria", "patron", "feria", "procesion", "baile", "orquesta"],
    "gastronomia": ["migas", "comida", "degustacion", "tapa", "gastronom", "cena", "paella", "matanza"],
    "cultural": ["concierto", "teatro", "exposicion", "charla", "taller", "museo", "cine", "libro", "visita"],
    "ludica": ["juego", "infantil", "ninos", "bingo", "concurso", "gymkana", "castillo hinchable"],
    "comercio": ["oferta", "descuento", "promocion", "rebaja", "% ", "tienda", "2x1"],
}


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def buscar_municipio(texto: str) -> str | None:
    """Basta con la primera palabra del nombre: «uleila», «lucainena», «senes»…
    La b y la v se tratan igual: la transcripción de voz escribe «Belefique»."""
    t = _normalizar(texto).replace("v", "b")
    return next((m for m in MUNICIPIOS if re.search(rf"\b{_normalizar(m).split()[0].replace('v', 'b')}\b", t)), None)


def _fecha(t: str, hoy: date) -> date | None:
    if m := re.search(r"\b(\d{1,2})\s+de\s+(" + "|".join(MESES) + r")(?:\s+de\s+(\d{4}))?", t):
        dia, mes, ano = int(m[1]), MESES[m[2]], int(m[3]) if m[3] else hoy.year
        try:
            f = date(ano, mes, dia)
        except ValueError:
            return None
        return f if m[3] or f >= hoy else f.replace(year=ano + 1)
    if m := re.search(r"\b(\d{1,2})[/-](\d{1,2})(?:[/-](\d{2,4}))?\b", t):
        ano = int(m[3]) if m[3] else hoy.year
        ano = ano + 2000 if ano < 100 else ano
        try:
            return date(ano, int(m[2]), int(m[1]))
        except ValueError:
            return None
    if "pasado manana" in t:
        return hoy + timedelta(days=2)
    if "manana" in t and not re.search(r"\bpor la manana\b", t):
        return hoy + timedelta(days=1)
    if "hoy" in t or "esta noche" in t:
        return hoy
    for nombre, idx in DIAS_SEMANA.items():
        if re.search(rf"\b(este|el|proximo)\s+{nombre}\b", t):
            return hoy + timedelta(days=(idx - hoy.weekday()) % 7 or 7)
    return None


def _hora(t: str) -> tuple[int, int] | None:
    if m := re.search(r"\b(?:a las\s+)?(\d{1,2})[:.h](\d{2})\s*(?:h|horas)?\b", t):
        h, mi = int(m[1]), int(m[2])
    elif m := re.search(r"\b(?:a|desde|de) las\s+(\d{1,2})(?:\s*(?:h|horas))?(?:\s+de la\s+(manana|tarde|noche))?", t):
        h, mi = int(m[1]), 0
        if m[2] in ("tarde", "noche") and h < 12:
            h += 12
    elif m := re.search(r"\b(\d{1,2})\s*(?:h|horas)\b", t):
        h, mi = int(m[1]), 0
    else:
        return None
    return (h, mi) if 0 <= h < 24 and 0 <= mi < 60 else None


_DIAS = r"(?:lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo|dia|día|\d)"
_PUEBLOS = "|".join(re.escape(m.split()[0]) for m in MUNICIPIOS) + "|" + "|".join(
    re.escape(_normalizar(m).split()[0]) for m in MUNICIPIOS)
# Dónde termina el nombre del plan: « en Senés», « el sábado», « este domingo», « a las 11», «, …»
_DIA_SEMANA = r"(?:lunes|martes|miercoles|miércoles|jueves|viernes|sabado|sábado|domingo)"
_FIN_TITULO = re.compile(rf"\s+en\s+(?:{_PUEBLOS})\b|\s+(?:el|este|esta|los|las|del|de este)\s+{_DIAS}|"
                         rf"\s+{_DIA_SEMANA}\b|\s+a las\s+\d|\s+[-–—]\s+|,\s", re.IGNORECASE)
# «Este sábado…», «Mañana a las 10…»: el cuándo va delante del qué
_CUANDO_DELANTE = re.compile(rf"^(?:(?:este|esta|el|el proximo|el próximo)\s+{_DIA_SEMANA}|mañana|manana|hoy|"
                             rf"este fin de semana|este finde)\s*(?:,?\s*a las\s+[\d:.]+(?:\s*h)?)?\s*,?\s*",
                             re.IGNORECASE)
_SALUDO = re.compile(r"^(hola|buenas|buenos dias|buenos días|buenas tardes|atención|atencion|ojo|aviso)\b",
                     re.IGNORECASE)


def titulo_por_reglas(texto: str) -> str | None:
    """Sin IA: el nombre del plan, no el post entero. Primera frase de la primera línea, cortada antes
    del pueblo, el día o la hora. «Taller de esparto en Senés el sábado 28…» → «Taller de esparto»."""
    linea = next((l.strip() for l in texto.splitlines() if l.strip()), "")
    frases = [f.strip(" .!¡¿?") for f in re.split(r"(?<=[.!?])\s+", linea) if f.strip(" .!¡¿?")]
    while len(frases) > 1 and (_SALUDO.match(frases[0]) and len(frases[0]) < 25):
        frases.pop(0)  # «¡Hola vecinos! Taller de…»
    frase = _CUANDO_DELANTE.sub("", frases[0] if frases else "")
    for m in _FIN_TITULO.finditer(frase):
        if len(frase[:m.start()].strip()) >= 6:  # que no se quede en una palabra suelta
            frase = frase[:m.start()]
            break
    frase = frase.strip(" .,:;-")
    if len(frase) > 80:
        frase = frase[:80].rsplit(" ", 1)[0]
    return (frase[:1].upper() + frase[1:]) if frase else None


def extraer_con_reglas(texto: str, hoy: date, tz: ZoneInfo) -> FichaLLM:
    t = _normalizar(texto)
    dudosos: list[str] = []

    municipio = buscar_municipio(t)

    categoria = None
    # Palabra clave al inicio de palabra: «polideportivo» no cuenta como deportiva
    puntos = {c: sum(bool(re.search(rf"\b{re.escape(p)}", t)) for p in ps) for c, ps in PALABRAS_CATEGORIA.items()}
    if max(puntos.values()) > 0:
        categoria = max(puntos, key=puntos.get)
        dudosos.append("categoria")

    fecha_inicio = None
    if f := _fecha(t, hoy):
        h, mi = _hora(t) or (0, 0)
        fecha_inicio = datetime(f.year, f.month, f.day, h, mi, tzinfo=tz).isoformat()

    es_gratuito = True if re.search(r"\b(gratis|gratuit[oa]|entrada libre)\b", t) else None
    precio = None
    if m := re.search(r"(\d+(?:[.,]\d{1,2})?)\s*(?:€|euros?|eur)\b", t):
        precio = float(m[1].replace(",", "."))
        es_gratuito = False

    plazas = None
    if m := re.search(r"\b(\d+)\s+plazas\b", t) or re.search(r"\bplazas\s*:?\s*(\d+)\b", t):
        plazas = int(m[1])

    titulo = titulo_por_reglas(texto)
    if titulo:
        dudosos.append("titulo")

    es_evento = fecha_inicio is not None or categoria is not None
    return FichaLLM(
        es_evento=es_evento,
        titulo=titulo if es_evento else None,
        descripcion=texto.strip()[:300] if es_evento else None,
        categoria=categoria,
        municipio=municipio,
        fecha_inicio=fecha_inicio,
        precio_eur=precio,
        es_gratuito=es_gratuito,
        plazas_totales=plazas,
        campos_dudosos=dudosos,
    )
