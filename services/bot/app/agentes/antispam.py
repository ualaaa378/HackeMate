"""Antispam y antifraude (POST /ai/spam, tarea N9). Reglas baratas primero; la IA solo cuando las reglas dudan.
El bot solo puntúa: la API decide con su umbral (MODERACION_UMBRAL_SPAM) y el moderador ve el motivo.

`tipo` distingue `spam` (publicidad ajena, apuestas, cadenas…) de `fraude` (pago por adelantado, Bizum o datos
bancarios, precios irreales, suplantar a un ayuntamiento…). En un pueblo es normal que un bar o una asociación pida
«la inscripción por Bizum»: por eso una sola señal de pago solo levanta la duda y decide la IA; varias juntas
(pago + urgencia, pago + suplantación, enlaces de fuera…) ya son fraude por reglas."""

import re
import unicodedata
from typing import Literal, Optional

from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm import router

DUDA_MIN, DUDA_MAX = 0.3, 0.7  # entre estos valores, se pregunta a la IA
Tipo = Literal["ninguno", "spam", "fraude"]


class ResultadoSpam(BaseModel):
    score_spam: float = Field(ge=0, le=1)
    es_spam: bool
    motivo: Optional[str] = None
    proveedor_ia: str = "reglas"
    tipo: Tipo = "ninguno"


class _SpamLLM(BaseModel):
    tipo: Tipo = Field(description="ninguno = legítimo; spam = publicidad ajena o basura; fraude = intenta sacar "
                                   "dinero o datos con engaño")
    score_spam: float = Field(ge=0, le=1, description="0 = contenido legítimo del pueblo, 1 = spam o fraude seguro")
    motivo: str = Field(description="Una frase en español para el moderador")


SYSTEM = """Eres el filtro antispam y antifraude de una agenda de actividades de pueblos de Almería.
Es legítimo («ninguno»): eventos, ofertas de negocios locales, avisos del ayuntamiento, preguntas sobre un evento.
También lo es que una asociación o un bar del pueblo cobre una inscripción o una reserva pequeña (por Bizum o en
mano) por un plan concreto con fecha y lugar.
Es «spam»: publicidad ajena a los pueblos, cripto, apuestas, enlaces sospechosos, cadenas, insultos, contenido sexual
o mensajes repetidos sin relación.
Es «fraude»: pide pagar por adelantado algo que no existe o no se puede comprobar, pide datos bancarios, números de
tarjeta o códigos, precios irreales (móviles a 20 €), urgencia artificial («solo hoy»), se hace pasar por el
ayuntamiento o una asociación para cobrar, o manda a pagar en enlaces de fuera.
Devuelve tipo, score_spam (0-1, alto si es spam o fraude) y un motivo breve. No inventes datos que no estén."""

_ACORTADORES = r"\b(bit\.ly|tinyurl|goo\.gl|t\.co|cutt\.ly|is\.gd|shorturl)\b"
_PALABRAS = ["cripto", "bitcoin", "inversion garantizada", "gana dinero", "casino", "apuestas", "prestamo rapido",
             "haz clic", "click aqui", "premio", "has ganado", "sorteo exclusivo", "viagra", "contactame por privado",
             "trabaja desde casa", "forex", "onlyfans"]
_PUEBLO = ["lucainena", "senes", "velefique", "uleila", "tahal", "plaza", "ayuntamiento", "asociacion", "fiesta",
           "ruta", "vecinos", "iglesia", "polideportivo"]

# Señales de fraude: (patrón, peso, motivo). Una sola señal de pago queda en la zona de duda (decide la IA)
_FRAUDE = [
    (r"\bpag(a|o|ar|ue|ad)\b.{0,25}\b(por )?(adelantado|anticipado)\b|\b(fianza|deposito|senal) (previa|antes)\b",
     0.35, "pide pagar por adelantado"),
    (r"\bbizum\b|\btransferencia\b|\bingreso en (la )?cuenta\b|\bwestern union\b|\bpaypal (amigos|familiares)\b",
     0.3, "pago por Bizum o transferencia"),
    (r"\biban\b|\bes\d{2}[\s\d]{12,}|\bnumero de (cuenta|tarjeta)\b|\bdatos bancarios\b|\bcvv\b|"
     r"\bcodigo (de )?(verificacion|sms|seguridad)\b", 0.5, "pide datos bancarios o códigos"),
    (r"\b(iphone|ps5|playstation|portatil|televisor|movil|smartphone)\b.{0,40}\b\d{1,2} ?(€|euros?)\b|"
     r"\b(8\d|9\d)% (de )?descuento\b|\b(gratis|regalamos)\b.{0,30}\b(iphone|ps5|movil|portatil)\b",
     0.45, "precio irreal"),
    (r"\bsolo (por )?hoy\b|\bhoy mismo\b|\bultimas? (\d+ )?horas\b|\bantes de que se agoten\b|\burgente\b|"
     r"\b(las )?plazas (vuelan|se agotan)\b", 0.15, "urgencia artificial"),
    (r"\b(os|te|le) (paso|mando|envio) (la|el|mi) (cuenta|numero de cuenta|iban)\b|\bpor privado\b.{0,40}"
     r"\b(cuenta|pago|bizum|transferencia)\b|\b(cuenta|pago|bizum|transferencia)\b.{0,40}\bpor privado\b",
     0.25, "pide pagar fuera de la plataforma, por privado"),
    (r"\ben nombre del ayuntamiento\b|\b(soy|somos) (del|el|la) (ayuntamiento|alcald\w*)\b|"
     r"\b(el )?ayuntamiento (te )?(pide|solicita|necesita)\b.{0,60}\b(pago|bizum|datos|ingreso|cuenta)\b",
     0.4, "se hace pasar por el ayuntamiento"),
]
_DOMINIOS_DE_CONFIANZA = r"(facebook\.com|fb\.me|instagram\.com|almeria|dipalme\.org|\.gob\.es|juntadeandalucia\.es|" \
                         r"hackemate|trycloudflare\.com)"


def _normalizar(t: str) -> str:
    t = unicodedata.normalize("NFD", t.lower())
    return "".join(c for c in t if unicodedata.category(c) != "Mn")


def _senales_fraude(t: str) -> tuple[float, list[str]]:
    puntos, motivos = 0.0, []
    for patron, peso, motivo in _FRAUDE:
        if re.search(patron, t):
            puntos += peso
            motivos.append(motivo)
    externos = [u for u in re.findall(r"https?://[^\s)]+", t) if not re.search(_DOMINIOS_DE_CONFIANZA, u)]
    if externos and motivos:  # un enlace de fuera solo cuenta si además pide dinero o datos
        puntos += 0.25
        motivos.append("manda a pagar o a dar datos en un enlace de fuera")
    return puntos, motivos


def puntuar_con_reglas(texto: str) -> ResultadoSpam:
    t = _normalizar(texto)
    puntos, motivos = 0.0, []
    if re.search(_ACORTADORES, t):
        puntos += 0.4
        motivos.append("enlace acortado")
    enlaces = len(re.findall(r"https?://", t))
    if enlaces >= 3:
        puntos += 0.3
        motivos.append(f"{enlaces} enlaces")
    if palabras := [p for p in _PALABRAS if p in t]:
        puntos += min(0.6, 0.3 * len(palabras))
        motivos.append("palabras típicas de spam: " + ", ".join(palabras[:3]))
    letras = [c for c in texto if c.isalpha()]
    if len(letras) > 20 and sum(c.isupper() for c in letras) / len(letras) > 0.7:
        puntos += 0.2
        motivos.append("casi todo en mayúsculas")
    if re.search(r"(.)\1{6,}", t) or texto.count("!") > 8:
        puntos += 0.1
        motivos.append("caracteres repetidos")
    if re.search(r"\b\d{9,}\b", t) and "whatsapp" in t:
        puntos += 0.1
        motivos.append("pide escribir a otro número")
    del_pueblo = any(p in t for p in _PUEBLO)
    if del_pueblo:
        puntos -= 0.2  # habla de los pueblos: menos probable que sea spam

    fraude, motivos_fraude = _senales_fraude(t)
    if motivos_fraude:
        # Cualquier señal de pago o datos pasa por la IA, aunque hable del pueblo: «inscripción por Bizum» puede
        # ser legítima o un engaño, y eso no lo decide una regla
        fraude = max(fraude, DUDA_MIN)
    spam = round(max(0.0, min(1.0, puntos)), 2)
    fraude = round(max(0.0, min(1.0, fraude)), 2)
    if fraude >= DUDA_MAX or (fraude > spam and fraude >= DUDA_MIN):
        tipo: Tipo = "fraude" if fraude >= DUDA_MAX else "ninguno"
        return ResultadoSpam(score_spam=fraude, es_spam=fraude >= DUDA_MAX, tipo=tipo,
                             motivo="posible fraude: " + "; ".join(motivos_fraude))
    todos = motivos + motivos_fraude
    return ResultadoSpam(score_spam=spam, es_spam=spam >= DUDA_MAX, tipo="spam" if spam >= DUDA_MAX else "ninguno",
                         motivo="; ".join(todos) if todos else "sin señales de spam")


def puntuar(texto: str, contexto: Literal["evento", "mensaje"] = "evento") -> ResultadoSpam:
    base = puntuar_con_reglas(texto)
    if not DUDA_MIN <= base.score_spam < DUDA_MAX:
        return base  # las reglas están seguras: no gastamos tokens
    res = router.estructurado(
        tarea="antispam",
        system=SYSTEM,
        texto=f"Contexto: {contexto}\n\n{texto}",
        salida=_SpamLLM,
        reglas=lambda _t: _SpamLLM(tipo=base.tipo, score_spam=base.score_spam, motivo=base.motivo or ""),
        cadena=get_settings().proveedores_tareas_n,  # N9: FreeLLM primero
    )
    if res.proveedor == "reglas":
        return base
    ia = res.salida
    es = ia.tipo != "ninguno" and ia.score_spam >= 0.5
    prefijo = "Posible fraude: " if ia.tipo == "fraude" else ""
    return ResultadoSpam(score_spam=round(ia.score_spam, 2), es_spam=es, tipo=ia.tipo if es else "ninguno",
                         motivo=f"{prefijo}{ia.motivo} (reglas: {base.motivo})", proveedor_ia=res.proveedor)
