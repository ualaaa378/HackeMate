"""RAG del buscador (contrato): POST /buscar y cómo encaja con bot POST /ai/embeddings y /ai/responder-agenda."""

import json

from tests.test_contratos import FIXTURES
from tests.test_estadisticas import _validador

BUSQUEDA = _validador("/components/schemas/BusquedaIA")
RESPUESTA = _validador("/components/schemas/RespuestaBusqueda")
PLAN = _validador("/components/schemas/PlanContexto")
EMB_PETICION = _validador("/paths/~1ai~1embeddings/post/requestBody/content/application~1json/schema")
EMB_RESPUESTA = _validador("/paths/~1ai~1embeddings/post/responses/200/content/application~1json/schema")
AGENDA_PETICION = _validador("/paths/~1ai~1responder-agenda/post/requestBody/content/application~1json/schema")
AGENDA_RESPUESTA = _validador("/paths/~1ai~1responder-agenda/post/responses/200/content/application~1json/schema")

PREGUNTA = "¿qué hay este finde para niños cerca de Senés?"
PLAN_ID = "1e5d0000-0000-4000-8000-000000000001"
PLAN_EJEMPLO = {
    "evento_id": PLAN_ID,
    "titulo": "Taller de cuentos en la plaza",
    "categoria": "cultural",
    "municipio": "Senés",
    "lugar": "Plaza de la Iglesia",
    "fecha_inicio": "2026-11-28T11:00:00+01:00",
    "fecha_fin": "2026-11-28T13:00:00+01:00",
    "precio_eur": None,
    "es_gratuito": True,
    "plazas_libres": 12,
    "descripcion": "Cuentacuentos para niños de 4 a 10 años.",
}
EVENTO = json.loads((FIXTURES / "eventos.json").read_text(encoding="utf-8"))[0]


def _errores(validador, dato) -> list[str]:
    return [e.message for e in validador.iter_errors(dato)]


def test_peticion_y_respuesta_del_buscador_cumplen_el_contrato():
    assert not _errores(BUSQUEDA, {"pregunta": PREGUNTA})
    assert not _errores(BUSQUEDA, {"pregunta": PREGUNTA, "limite": 8})
    respuesta = {
        "respuesta": "Este sábado hay un taller de cuentos gratis en Senés para niños.",
        "items": [EVENTO],
        "citados": [EVENTO["id"]],
        "recuperados": 5,
        "proveedor_ia": "gemini:gemini-2.5-flash",
        "modo": "rag",
        "filtros": {
            "desde": "2026-11-28T00:00:00+01:00",
            "hasta": "2026-11-29T23:59:59+01:00",
            "municipio": "Senés",
            "categorias": ["cultural", "ludica"],
            "gratis": False,
            "ninos": True,
        },
    }
    assert not _errores(RESPUESTA, respuesta)
    sin_ia = {"respuesta": "No he encontrado nada.", "items": [], "citados": [], "recuperados": 0, "proveedor_ia": "reglas", "modo": "palabras"}
    assert not _errores(RESPUESTA, sin_ia)
    assert not _errores(RESPUESTA, sin_ia | {"filtros": {"desde": None, "hasta": None, "municipio": None}})


def test_embeddings_un_vector_por_texto():
    assert not _errores(EMB_PETICION, {"textos": [PREGUNTA], "tipo": "consulta"})
    assert not _errores(EMB_PETICION, {"textos": ["Taller de cuentos", "Ruta solidaria"]})
    assert not _errores(EMB_RESPUESTA, {"modelo": "gemini-embedding-001", "dimension": 3, "vectores": [[0.1, -0.2, 0.3]]})


def test_lo_que_la_api_manda_al_bot_y_lo_que_devuelve_encajan():
    assert not _errores(PLAN, PLAN_EJEMPLO)
    assert not _errores(PLAN, {k: PLAN_EJEMPLO[k] for k in ("evento_id", "titulo", "categoria", "municipio", "fecha_inicio")})
    assert not _errores(AGENDA_PETICION, {"pregunta": PREGUNTA, "planes": [PLAN_EJEMPLO], "hoy": "2026-11-26T10:00:00+01:00"})
    assert not _errores(AGENDA_PETICION, {"pregunta": PREGUNTA, "planes": []})
    respuesta = {"respuesta": "El sábado hay un taller de cuentos gratis en Senés.", "evento_ids": [PLAN_ID], "proveedor_ia": "reglas"}
    assert not _errores(AGENDA_RESPUESTA, respuesta)


def test_casos_invalidos():
    assert _errores(BUSQUEDA, {"pregunta": "hi"})
    assert _errores(BUSQUEDA, {"pregunta": PREGUNTA, "limite": 9})
    assert _errores(RESPUESTA, {"respuesta": "x", "items": [], "citados": [], "recuperados": 0, "proveedor_ia": "reglas", "modo": "magia"})
    assert _errores(RESPUESTA, {"respuesta": "x", "items": [], "citados": [], "recuperados": 0, "proveedor_ia": "reglas"})
    assert _errores(EMB_PETICION, {"textos": ["a"] * 101})
    assert _errores(EMB_PETICION, {"textos": []})
    assert _errores(EMB_PETICION, {"textos": [""]})
    assert _errores(AGENDA_PETICION, {"pregunta": PREGUNTA, "planes": [PLAN_EJEMPLO] * 13})
    assert _errores(PLAN, PLAN_EJEMPLO | {"categoria": "otra"})
    assert _errores(PLAN, PLAN_EJEMPLO | {"descripcion": "x" * 601})
    assert _errores(AGENDA_RESPUESTA, {"respuesta": "x", "evento_ids": ["no-es-uuid"], "proveedor_ia": "reglas"})
