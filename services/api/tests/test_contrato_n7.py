"""N7 (contrato, antes de CP3): ejemplos de GET /admin/sugerencias y de cómo encaja con bot POST /ai/sugerir-eventos (N8)."""

from tests.test_estadisticas import _validador

SUGERENCIAS = _validador("/components/schemas/Sugerencias")
SUGERENCIA = _validador("/components/schemas/SugerenciaPlan")
BORRADOR = _validador("/components/schemas/BorradorSugerencia")
PETICION_BOT = _validador("/paths/~1ai~1sugerir-eventos/post/requestBody/content/application~1json/schema")
RESPUESTA_BOT = _validador("/paths/~1ai~1sugerir-eventos/post/responses/200/content/application~1json/schema")

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
    "categoria": "deportiva",
    "municipio": "Velefique",
    "fecha_aproximada": "en primavera",
    "motivo": "La II Ruta Solidaria se llenó (40 de 40) y hubo 6 personas en lista de espera",
    "basado_en": [RUTA],
}


def _errores(validador, dato) -> list[str]:
    return [e.message for e in validador.iter_errors(dato)]


def test_ejemplo_de_respuesta_de_la_api_cumple_el_contrato():
    assert not _errores(SUGERENCIAS, {"items": [PROPUESTA], "basado_en": [PARTICIPACION], "proveedor_ia": "freellm:qwen"})
    assert not _errores(SUGERENCIAS, {"items": [], "basado_en": [], "proveedor_ia": "reglas"})


def test_lo_que_la_api_manda_al_bot_y_lo_que_devuelve_encajan():
    """Los `ParticipacionPlan` de la API valen como `planes` del bot, y sus `propuestas` como `SugerenciaPlan`."""
    assert not _errores(PETICION_BOT, {"planes": [PARTICIPACION], "maximo": 3})
    respuesta = {"propuestas": [PROPUESTA], "proveedor_ia": "nim:nemotron"}
    assert not _errores(RESPUESTA_BOT, respuesta)
    assert all(not _errores(SUGERENCIA, p) for p in respuesta["propuestas"])


def test_crear_borrador_pide_la_fecha_que_elige_el_moderador():
    assert not _errores(BORRADOR, PROPUESTA | {"fecha_inicio": "2027-04-18T09:00:00+02:00"})
    assert _errores(BORRADOR, PROPUESTA)


def test_una_propuesta_sin_motivo_no_vale():
    assert _errores(SUGERENCIA, {k: v for k, v in PROPUESTA.items() if k != "motivo"})
    assert _errores(SUGERENCIAS, {"items": [PROPUESTA] * 4, "basado_en": [], "proveedor_ia": "reglas"})
