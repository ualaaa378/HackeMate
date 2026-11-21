"""N7/N8 (contrato, antes de CP3): ejemplos de lo que devuelven GET /admin/sugerencias y bot POST /ai/sugerir-eventos."""

from tests.test_estadisticas import _validador

SUGERENCIAS = _validador("/components/schemas/Sugerencias")
SUGERENCIA = _validador("/components/schemas/SugerenciaPlan")
RESPUESTA_BOT = _validador("/paths/~1ai~1sugerir-eventos/post/responses/200/content/application~1json/schema")
PETICION_BOT = _validador("/paths/~1ai~1sugerir-eventos/post/requestBody/content/application~1json/schema")

RUTA = "1e5d0000-0000-4000-8000-000000000001"
PARTICIPACION = {
    "evento_id": RUTA,
    "titulo": "II Ruta Solidaria Sierra de Velefique",
    "categoria": "deportiva",
    "municipio": "Velefique",
    "fecha_inicio": "2026-11-29T09:00:00+01:00",
    "estado": "publicado",
    "plazas_totales": 40,
    "inscritos": 40,
    "lista_espera": 6,
    "asistencias": 0,
    "ocupacion": 1.0,
    "preguntas_chat": 3,
}
PROPUESTA = {
    "titulo": "III Ruta Solidaria Sierra de Velefique",
    "descripcion": None,
    "categoria": "deportiva",
    "municipio": "Velefique",
    "fecha_sugerida": "2027-04-18T09:00:00+02:00",
    "fecha_texto": "en primavera",
    "motivo": "La II Ruta Solidaria se llenó (40 de 40) y hubo 6 personas en lista de espera",
    "basado_en": [RUTA],
}


def _errores(validador, dato) -> list[str]:
    return [e.message for e in validador.iter_errors(dato)]


def test_ejemplo_de_respuesta_de_la_api_cumple_el_contrato():
    assert not _errores(SUGERENCIAS, {"items": [PROPUESTA], "basado_en": [PARTICIPACION], "proveedor_ia": "freellm:qwen"})
    assert not _errores(SUGERENCIAS, {"items": [], "basado_en": [], "proveedor_ia": "reglas"})


def test_ejemplo_del_bot_cumple_el_contrato():
    assert not _errores(PETICION_BOT, {"planes": [PARTICIPACION], "max_sugerencias": 3, "hoy": "2026-11-21T18:00:00+01:00"})
    assert not _errores(RESPUESTA_BOT, {"sugerencias": [PROPUESTA], "proveedor_ia": "nim:nemotron"})


def test_una_propuesta_sin_planes_que_la_justifiquen_no_vale():
    """Sin inventar: cada propuesta dice en qué planes se basa."""
    assert _errores(SUGERENCIA, PROPUESTA | {"basado_en": []})
    assert _errores(SUGERENCIA, {k: v for k, v in PROPUESTA.items() if k != "motivo"})
    assert _errores(PETICION_BOT, {"planes": []})
    assert _errores(RESPUESTA_BOT, {"sugerencias": [PROPUESTA] * 4, "proveedor_ia": "reglas"})
