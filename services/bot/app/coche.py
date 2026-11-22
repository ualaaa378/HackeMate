"""Compartir coche (idea 6): la API propone ir juntos a los vecinos del mismo pueblo apuntados a un plan de otro
pueblo (aviso que empieza por `MARCA`). Aquí se ponen los botones y se manda la respuesta a la API, que es quien
decide a quién pasar el contacto (solo entre quienes dicen que sí)."""

import logging

from app import api_cliente
from app.api_cliente import ApiNoDisponible, ErrorApi

log = logging.getLogger(__name__)

MARCA = "🚗"  # = app/coche.py MARCA_COCHE de la API
NO_PUEDO = "Ahora mismo no puedo guardarlo 🙏 Inténtalo en un rato."


def es_propuesta(texto: str) -> bool:
    return (texto or "").startswith(MARCA)


def botones(evento_id: str) -> list[tuple[str, str]]:
    return [(f"coche:si:{evento_id}", "🚗 Sí, vamos juntos"), (f"coche:no:{evento_id}", "No, gracias")]


def responder(boton_id: str, usuario: dict | None) -> list[str]:
    _, decision, evento_id = boton_id.split(":", 2)
    if not (usuario or {}).get("id"):
        return [NO_PUEDO]
    try:
        res = api_cliente.responder_coche(evento_id, usuario["id"], decision == "si") or {}
    except ApiNoDisponible:
        return [NO_PUEDO]
    except ErrorApi as e:
        if e.status == 409:
            return ["Esto ya no está disponible: solo vale si sigues apuntado/a con plaza a ese plan."]
        log.warning("coche: la API respondió %s %s", e.status, e.code)
        return [NO_PUEDO]
    if decision != "si":
        return ["Vale, no paso tu contacto a nadie 👍"]
    companeros = res.get("companeros") or []
    if not companeros:
        return ["¡Apuntado! 🚗 En cuanto otro vecino de tu pueblo diga que sí, os paso el contacto a los dos."]
    return ["¡Hecho! 🚗 Podéis ir juntos. Contacto: " + ", ".join(companeros) + ". Ya le he avisado de que vas."]
