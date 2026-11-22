"""Idea 5: asistente del moderador.

- `resumen`: qué hay en la bandeja de un vistazo («1 posible fraude, 1 apelación…») y qué conviene hacer con cada
  plan. Por reglas, sin tokens: se lee del motivo que pone la API.
- `motivo_rechazo`: la IA redacta un motivo de rechazo amable y concreto para quien propuso el plan, a partir del
  motivo de la moderación (FreeLLM primero, como las tareas N). Sin IA, una plantilla por tipo de motivo. El moderador
  lo lee antes de enviarlo y puede escribir otro: la IA propone y una persona decide.
"""

from pydantic import BaseModel, Field

from app.config import get_settings
from app.llm import router

TIPOS = (  # (clave, empieza el motivo de la API por…, nombre en el resumen, plural)
    ("fraude", ("posible fraude", "editado después de publicarse. posible fraude"), "posible fraude", "posibles fraudes"),
    ("spam", ("posible spam", "editado después de publicarse. posible spam"), "posible spam", "posibles spam"),
    ("apelacion", ("apelación",), "apelación", "apelaciones"),
    ("duplicado", ("posible duplicado",), "posible duplicado", "posibles duplicados"),
    ("importado", ("importado",), "importado de Facebook", "importados de Facebook"),
)


def tipo_de(motivo: str | None) -> str:
    m = (motivo or "").strip().lower()
    return next((clave for clave, prefijos, _, _ in TIPOS if m.startswith(prefijos)), "a_mano")


def sugerencia(motivo: str | None) -> str:
    return {
        "fraude": "💡 Sugerencia: rechazar (pide pagos o datos fuera de la plataforma).",
        "spam": "💡 Sugerencia: rechazar si no es un plan del pueblo.",
        "apelacion": "💡 Sugerencia: lee el motivo de la apelación; si lo corrige, apruébalo. Un segundo rechazo es definitivo.",
        "duplicado": "💡 Sugerencia: comprueba si es el mismo plan; si lo es, recházalo.",
        "importado": "💡 Sugerencia: revisa la fecha y el lugar que ha sacado la IA y apruébalo.",
    }.get(tipo_de(motivo), "💡 Sugerencia: revisa que tenga fecha, lugar y descripción clara, y apruébalo.")


def resumen(motivos: list[str | None]) -> str:
    """«3 pendientes: 1 posible fraude, 1 apelación y 1 importado de Facebook. Empieza por el fraude.»"""
    cuentas = {clave: 0 for clave, *_ in TIPOS} | {"a_mano": 0}
    for m in motivos:
        cuentas[tipo_de(m)] += 1
    partes = [f"{n} {singular if n == 1 else plural}" for clave, _, singular, plural in TIPOS
              if (n := cuentas[clave])]
    if cuentas["a_mano"]:
        partes.append(f"{cuentas['a_mano']} para revisar a mano")
    total = len(motivos)
    texto = f"Tienes {total} pendiente(s): " + (", ".join(partes[:-1]) + " y " + partes[-1] if len(partes) > 1
                                                else partes[0]) + "."
    if cuentas["fraude"]:
        texto += " Empieza por el posible fraude ⚠️"
    elif cuentas["apelacion"]:
        texto += " Hay apelaciones esperando una segunda revisión."
    return texto


# --- Motivo de rechazo -------------------------------------------------------------------------------------------

class _Motivo(BaseModel):
    texto: str = Field(description="Mensaje breve (2 frases, máx. 280 caracteres) para quien propuso el plan")


SYSTEM = """Eres el asistente del ayuntamiento en una agenda de planes de pueblos de Almería.
El moderador va a rechazar un plan. Escribe a quien lo propuso un mensaje breve, amable y concreto (2 frases, máximo
280 caracteres, de tú, en español): por qué no se publica y qué puede hacer (corregirlo y volver a enviarlo, o apelar
si cree que es un error). No inventes datos que no estén. No culpes ni acuses a nadie; si hay sospecha de fraude,
explícalo como una norma de seguridad (no se publican pagos por adelantado ni fuera de la plataforma)."""

PLANTILLAS = {
    "fraude": ("Por seguridad no publicamos planes que piden pagos por adelantado o datos fuera de la plataforma. "
               "Si es un error, puedes apelar y explicar cómo se paga."),
    "spam": ("Parece publicidad ajena a los pueblos, así que no lo publicamos. Si es un plan del pueblo, apela y "
             "cuéntanos de qué se trata."),
    "duplicado": "Ya hay un plan igual en la agenda, así que no lo publicamos dos veces. Si es otro distinto, apela y explica la diferencia.",
    "apelacion": "Lo hemos revisado otra vez y seguimos sin poder publicarlo. Esta decisión es definitiva; gracias por entenderlo.",
}
GENERICO = ("Le faltan datos para publicarlo (fecha, lugar o una descripción clara). Corrígelo y vuelve a enviarlo, "
            "o apela si crees que es un error.")


def motivo_rechazo(titulo: str, motivo_moderacion: str | None) -> tuple[str, str]:
    """(texto, proveedor). Nunca lanza: sin IA, una plantilla según el motivo."""
    plantilla = PLANTILLAS.get(tipo_de(motivo_moderacion), GENERICO)
    try:
        res = router.estructurado(
            tarea="motivo_rechazo",
            system=SYSTEM,
            texto=f"Plan: «{titulo}»\nMotivo de la moderación: {motivo_moderacion or 'sin motivo'}",
            salida=_Motivo,
            reglas=lambda _t: _Motivo(texto=plantilla),
            cadena=get_settings().proveedores_tareas_n,
        )
        texto = (res.salida.texto or "").strip()[:400]
        return (texto or plantilla), res.proveedor
    except Exception:  # noqa: BLE001 — el moderador siempre tiene un texto que enviar
        return plantilla, "reglas"
