"""Piezas comunes: token interno, formato de error para cualquier fallo y paginación."""

from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient
from sqlalchemy import select

from app import errores
from app.config import get_settings
from app.main import app
from app.modelos import Municipio
from app.paginacion import Pagina, pagina, paginar
from app.seguridad import exigir_token_interno

# App mínima de prueba con las mismas piezas que la real
prueba = FastAPI()
errores.registrar(prueba)


@prueba.get("/interna", dependencies=[Depends(exigir_token_interno)])
def _interna():
    return {"ok": True}


@prueba.get("/pagina")
def _pagina(p: Pagina = Depends(pagina)):
    return {"page": p.page, "size": p.size}


@prueba.get("/rompe")
def _rompe():
    raise RuntimeError("fallo inesperado")


cliente_prueba = TestClient(prueba, raise_server_exceptions=False)


def test_ruta_interna_sin_token_da_401_con_formato():
    r = cliente_prueba.get("/interna")
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_interno_invalido"


def test_ruta_interna_con_token_equivocado_da_401():
    r = cliente_prueba.get("/interna", headers={"X-Internal-Token": "otro"})
    assert r.status_code == 401


def test_ruta_interna_con_token_correcto_pasa():
    r = cliente_prueba.get("/interna", headers={"X-Internal-Token": get_settings().internal_token})
    assert r.status_code == 200


def test_error_inesperado_da_500_sin_detalles_internos():
    r = cliente_prueba.get("/rompe")
    assert r.status_code == 500
    assert r.json() == {"error": {"code": "error_interno", "message": "Error interno del servidor", "details": {}}}


def test_ruta_inexistente_da_404_con_formato():
    r = TestClient(app).get("/api/v1/no-existe")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "no_encontrado"


def test_paginacion_por_defecto_y_limites():
    assert cliente_prueba.get("/pagina").json() == {"page": 1, "size": 20}
    r = cliente_prueba.get("/pagina", params={"size": 101})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "validacion"
    assert cliente_prueba.get("/pagina", params={"page": 0}).status_code == 422


def test_paginar_consulta_cuenta_el_total_y_corta_la_pagina(db):
    db.add_all(Municipio(nombre=f"Pueblo {i:02d}", lat=37.0, lon=-2.0) for i in range(25))
    db.commit()
    consulta = select(Municipio).order_by(Municipio.nombre)
    r = paginar(db, consulta, Pagina(page=3, size=10), lambda m: {"nombre": m.nombre})
    assert r["total"] == 25 and r["page"] == 3 and r["size"] == 10
    assert [m["nombre"] for m in r["items"]] == [f"Pueblo {i}" for i in range(20, 25)]


def test_la_api_usa_la_base_de_prueba(cliente, db):
    # El cliente de los tests no toca DATABASE_URL: la base temporal empieza vacía.
    assert db.scalar(select(Municipio).limit(1)) is None
    assert cliente.get("/health").status_code == 200
