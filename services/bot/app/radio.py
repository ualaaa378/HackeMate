"""«La radio del pueblo» (tareas nocturnas 22/11): el resumen semanal del lunes (tarea programada 3 de la API, texto
que empieza por `MARCA`) llega además como nota de voz con tono de locutor de radio local.

La IA convierte la lista de planes en un guion corto de radio; sin IA, una plantilla. La voz la hace el mismo TTS
gratis que las demás notas de voz (agentes/voz.py). Si la voz falla, la persona se queda con el texto, que ya le
ha llegado: nunca se pierde el resumen. Va en segundo plano para que `/notify` conteste al momento (la API espera
como mucho unos segundos y, si no, reintenta, lo que duplicaría el aviso)."""

import logging
import re

from pydantic import BaseModel, Field

from app import canales
from app.agentes import voz
from app.config import get_settings
from app.llm import router

log = logging.getLogger(__name__)

MARCA = "📅 Esta semana"  # = MARCA_RESUMEN de services/api/app/tareas_programadas.py
MAX_GUION = 650

SYSTEM = """Eres el locutor de «La radio del pueblo», una emisora local de los pueblos de Almería.
Convierte la lista de planes de la semana en un guion para leer en voz alta: saludo cercano de lunes por la
mañana, los planes uno a uno (día, hora, qué es y dónde) con frases cortas y alegres, y una despedida.
Máximo 600 caracteres, en español, de tú o de vosotros, sin emojis, sin enlaces y sin inventar nada que no
esté en la lista."""


class _Guion(BaseModel):
    texto: str = Field(description="Guion de radio para leer en voz alta (máx. 600 caracteres)")


def es_resumen(texto: str) -> bool:
    return (texto or "").startswith(MARCA)


def _plantilla(texto: str) -> str:
    cabecera, *lineas = texto.splitlines()
    zona = cabecera.removeprefix(MARCA).strip(" :")
    planes = [re.sub(r"^[•\-\s]+", "", l).replace(" · ", ", ") for l in lineas if l.strip().startswith("•")]
    cuerpo = ". ".join(planes)
    return (f"¡Buenos días y feliz lunes! Esto es La radio del pueblo, con los planes de esta semana {zona}. "
            f"{cuerpo}. ¡Os esperamos, y que paséis una buena semana!")


def guion(texto: str) -> tuple[str, str]:
    """(guion, proveedor). Nunca lanza."""
    try:
        r = router.estructurado(tarea="radio_pueblo", system=SYSTEM, texto=texto, salida=_Guion,
                                reglas=lambda t: _Guion(texto=_plantilla(t)),
                                cadena=get_settings().proveedores_tareas_n)
        g = (r.salida.texto or "").strip()
        return (g[:MAX_GUION] if g else _plantilla(texto)), r.proveedor
    except Exception:  # noqa: BLE001
        return _plantilla(texto), "reglas"


def emitir(destino: str, texto: str) -> bool:
    """Genera y manda la nota de voz. True si ha salido."""
    g, proveedor = guion(texto)
    ogg = voz.sintetizar(voz.texto_para_voz([g]))
    if not ogg:
        log.info("Radio del pueblo sin voz (%s): se queda el texto", proveedor)
        return False
    return bool(canales.enviar_voz(destino, ogg))
