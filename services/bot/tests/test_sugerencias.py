"""N8: POST /ai/sugerir-eventos (lo usa la API en N7)."""

from fastapi.testclient import TestClient

from app.agentes import sugerencias
from app.llm import router
from app.main import app

CAB = {"X-Internal-Token": "test"}
RUTA = {"evento_id": "1e5d0000-0000-4000-8000-000000000001", "titulo": "II Ruta Solidaria Sierra de Velefique",
        "categoria": "deportiva", "municipio": "Velefique", "fecha_inicio": "2026-11-29T09:00:00+01:00",
        "plazas_totales": 40, "inscritos": 40, "lista_espera": 6, "preguntas_chat": 4}
TALLER = {"evento_id": "1e5d0000-0000-4000-8000-000000000002", "titulo": "Taller de esparto", "categoria": "cultural",
          "municipio": "Senés", "fecha_inicio": "2026-12-05T17:00:00+01:00", "plazas_totales": 12, "inscritos": 5}


def test_sin_ia_repite_lo_que_mas_se_lleno_con_las_cifras_reales():
    r = TestClient(app).post("/ai/sugerir-eventos", headers=CAB, json={"planes": [TALLER, RUTA], "maximo": 1})
    assert r.status_code == 200
    d = r.json()
    assert d["proveedor_ia"] == "reglas" and len(d["propuestas"]) == 1
    p = d["propuestas"][0]
    assert "Ruta Solidaria" in p["titulo"] and p["municipio"] == "Velefique" and p["categoria"] == "deportiva"
    assert "40 de 40 plazas" in p["motivo"] and "6 en lista de espera" in p["motivo"]
    assert p["basado_en"] == [RUTA["evento_id"]]


def test_pide_token():
    assert TestClient(app).post("/ai/sugerir-eventos", json={"planes": [RUTA]}).status_code == 401


def test_la_ia_va_con_freellm_primero_y_se_descarta_lo_inventado(monkeypatch):
    cadenas = []

    def ia(tarea, system, texto, salida, reglas, cadena=None):
        cadenas.append(cadena)
        return router.Resultado(proveedor="freellm:x", salida=salida(propuestas=[
            sugerencias.Propuesta(titulo="Ruta Solidaria en primavera", categoria="deportiva", municipio="Velefique",
                                  fecha_aproximada="primavera", motivo="Se llenó: 40 de 40 y 6 en espera",
                                  basado_en=[RUTA["evento_id"], "inventado"]),
            sugerencias.Propuesta(titulo="Concierto en Madrid", categoria="cultural", municipio="Madrid",
                                  motivo="x"),  # pueblo que no está: fuera
        ]))
    monkeypatch.setattr(router, "estructurado", ia)
    d = TestClient(app).post("/ai/sugerir-eventos", headers=CAB, json={"planes": [RUTA, TALLER]}).json()
    assert cadenas[0][0] == "freellm"
    assert [p["titulo"] for p in d["propuestas"]] == ["Ruta Solidaria en primavera"]
    assert d["propuestas"][0]["basado_en"] == [RUTA["evento_id"]]  # el id inventado se quita
    assert d["proveedor_ia"] == "freellm:x"
