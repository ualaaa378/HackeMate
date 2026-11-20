"""Núcleo de moderación: puntuación de spam, niveles de confianza y decisión de estado (H2.4).

La IA (bot /ai/spam) propone una puntuación; aquí se decide el estado. Si el bot no responde,
se usan reglas locales baratas. Nada de esto lanza excepciones hacia la ruta que lo llama.
"""

import logging
import re
import unicodedata

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import get_settings
from app.modelos import Evento, Publicador

log = logging.getLogger(__name__)

TIMEOUT_BOT_S = 2.0

# Frases en minúsculas y sin tildes (el texto se normaliza igual antes de buscar).
_FRASES_SPAM = (
    "apuesta", "casino", "bitcoin", "cripto", "gana dinero", "ganar dinero", "dinero facil",
    "haz clic", "haz click", "pincha aqui", "prestamo", "credito rapido", "credito sin aval",
    "inversion garantizada", "rentabilidad garantizada", "trading", "tragaperras", "ruleta",
    "bono de bienvenida", "sin riesgo",
)
_ACORTADORES = ("bit.ly", "tinyurl", "goo.gl", "t.co/", "cutt.ly", "is.gd", "ow.ly", "rebrand.ly", "shorturl")
_PALABRAS_VENTA = ("llama ya", "llamanos ya", "oferta", "promocion", "compra", "descuento", "ultimas unidades")

_RE_URL = re.compile(r"(https?://\S+|www\.\S+|\b[a-z0-9-]+\.(?:com|es|net|org|ly|io|info|xyz|link)/\S*)", re.I)
_RE_TELEFONO = re.compile(r"(?:\+34\s?)?\b[6789]\d{2}[\s.-]?\d{3}[\s.-]?\d{3}\b")
_RE_EXCLAMACIONES = re.compile(r"[!¡]{2,}")


def _normalizar(texto: str) -> str:
    sin_tildes = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode("ascii")
    return sin_tildes.lower()


def puntuar_spam_reglas(texto: str | None) -> tuple[float, list[str]]:
    """Puntuación 0–1 sin IA y las razones legibles que la explican."""
    if not texto or not texto.strip():
        return 0.0, []
    norm = _normalizar(texto)
    score = 0.0
    razones: list[str] = []

    frases = [f for f in _FRASES_SPAM if f in norm]
    if frases:
        score += min(0.35 * len(frases), 0.7)
        razones.append("palabras típicas de spam: " + ", ".join(f"«{f}»" for f in frases))

    urls = _RE_URL.findall(texto)
    acortadores = [a for a in _ACORTADORES if a in norm]
    if acortadores:
        score += 0.3
        razones.append("enlace acortado (" + ", ".join(a.rstrip("/") for a in acortadores) + ")")
    if len(urls) >= 2:
        score += 0.2
        razones.append(f"varios enlaces ({len(urls)})")

    palabras = re.findall(r"[A-Za-zÁÉÍÓÚÜÑáéíóúüñ]{3,}", texto)
    en_mayusculas = [p for p in palabras if p.isupper()]
    if len(en_mayusculas) >= 2 and len(en_mayusculas) >= 0.2 * len(palabras):
        score += 0.2
        razones.append("exceso de MAYÚSCULAS")

    if len(_RE_EXCLAMACIONES.findall(texto)) >= 1 or texto.count("!") >= 4:
        score += 0.15
        razones.append("exceso de exclamaciones")

    if _RE_TELEFONO.search(texto) and any(p in norm for p in _PALABRAS_VENTA):
        score += 0.25
        razones.append("teléfono con reclamo de venta")

    return round(min(score, 1.0), 2), razones


def _llamar_bot_spam(texto: str, publicador_id: str | None) -> tuple[float, str] | None:
    """POST {BOT_URL}/ai/spam. Devuelve (score, motivo) o None si el bot no está o responde mal."""
    ajustes = get_settings()
    if not ajustes.bot_url:
        return None
    try:
        r = httpx.post(
            ajustes.bot_url.rstrip("/") + "/ai/spam",
            json={"texto": texto, "contexto": "evento", "publicador_id": publicador_id},
            headers={"X-Internal-Token": ajustes.internal_token},
            timeout=TIMEOUT_BOT_S,
        )
        if r.status_code != 200:
            return None
        datos = r.json()
        score = datos.get("score_spam")
        if isinstance(score, bool) or not isinstance(score, (int, float)) or not 0 <= score <= 1:
            return None
        if not isinstance(datos.get("es_spam"), bool):
            return None
    except Exception as e:  # noqa: BLE001 — cualquier fallo del bot cae a reglas locales
        log.info("bot /ai/spam no disponible (%s); se usan reglas locales", type(e).__name__)
        return None
    proveedor = datos.get("proveedor_ia")
    fuente = f"IA ({proveedor})" if isinstance(proveedor, str) and proveedor else "IA"
    motivo = datos.get("motivo")
    detalle = motivo if isinstance(motivo, str) and motivo.strip() else ("parece spam" if datos["es_spam"] else "sin indicios")
    return round(float(score), 2), f"{fuente}: {detalle}"


def clasificar_spam(texto: str | None, publicador: Publicador | None = None) -> tuple[float, str]:
    """Puntuación de spam con su motivo. Primero la IA del bot; si falla, reglas locales.
    El motivo empieza por la fuente («IA…» o «reglas»). Nunca lanza."""
    texto = texto or ""
    try:
        resultado = _llamar_bot_spam(texto, publicador.id if publicador is not None else None)
        if resultado is not None:
            return resultado
    except Exception:  # noqa: BLE001
        log.exception("fallo inesperado al consultar /ai/spam")
    score, razones = puntuar_spam_reglas(texto)
    return score, "reglas: " + ("; ".join(razones) if razones else "sin indicios")


def _tiene_publicados_de_categoria(db: Session, publicador: Publicador, categoria: str, excluir_id: str | None) -> bool:
    consulta = select(Evento.id).where(
        Evento.publicador_id == publicador.id,
        Evento.categoria == categoria,
        Evento.estado == "publicado",
    )
    if excluir_id:
        consulta = consulta.where(Evento.id != excluir_id)
    return db.scalar(consulta.limit(1)) is not None


def decidir_estado(
    db: Session,
    evento: Evento,
    publicador: Publicador | None,
    score_spam: float | None,
    motivo_spam: str | None = None,
) -> tuple[str, str]:
    """Estado al que pasa un evento confirmado (`publicado` o `en_revision`) y el motivo legible.
    No modifica el evento: lo hace quien llama. `motivo_spam` es el que devuelve `clasificar_spam`."""
    umbral = get_settings().moderacion_umbral_spam
    score = score_spam or 0.0

    if publicador is None:
        return "en_revision", "Sin publicador identificado"
    if publicador.estado == "pausado":
        return "en_revision", "Publicador pausado"
    if publicador.automatizaciones_pausadas and evento.importado_auto:
        return "en_revision", "Automatizaciones del publicador pausadas"
    if score >= umbral:
        detalle = motivo_spam or "sin detalle"
        return "en_revision", f"Posible spam ({score:.2f}): {detalle}"

    nivel = publicador.nivel_confianza
    if nivel <= 0:
        return "en_revision", "Publicador nuevo (nivel 0)"
    if nivel == 1:
        habituales = publicador.categorias_habituales or []
        if evento.categoria in habituales or _tiene_publicados_de_categoria(db, publicador, evento.categoria, evento.id):
            return "publicado", "Publicador de nivel 1, categoría habitual"
        return "en_revision", f"Categoría fuera de lo habitual ({evento.categoria})"
    return "publicado", "Publicador de confianza (nivel 2)"


def registrar_aprobacion(publicador: Publicador) -> bool:
    """Suma una aprobación y sube de nivel cada N aprobaciones (N = MODERACION_APROBACIONES_SUBIR_NIVEL).

    `aprobaciones` es el total acumulado (como dice el schema) y no se reinicia: el tramo de cada nivel
    se cuenta con el módulo, así que sube al llegar a N, 2N… aprobaciones. Devuelve True si subió.
    No hace commit."""
    n = max(get_settings().moderacion_aprobaciones_subir_nivel, 1)
    publicador.aprobaciones = (publicador.aprobaciones or 0) + 1
    if publicador.nivel_confianza < 2 and publicador.aprobaciones % n == 0:
        publicador.nivel_confianza += 1
        return True
    return False
