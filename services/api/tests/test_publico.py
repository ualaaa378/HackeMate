from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def test_municipios_son_los_cinco():
    r = cliente.get("/api/v1/municipios")
    assert r.status_code == 200
    assert len(r.json()) == 5


def test_eventos_solo_publicados_y_ordenados():
    r = cliente.get("/api/v1/eventos", params={"size": 100})
    cuerpo = r.json()
    assert set(cuerpo) == {"items", "total", "page", "size"}
    assert cuerpo["total"] > 0
    assert all(e["estado"] == "publicado" for e in cuerpo["items"])
    fechas = [e["fecha_inicio"] for e in cuerpo["items"]]
    assert fechas == sorted(fechas)


def test_eventos_filtra_por_municipio():
    r = cliente.get("/api/v1/eventos", params={"municipio": "Senés"})
    assert all(e["municipio"] == "Senés" for e in r.json()["items"])


def test_ficha_evento_y_404_con_formato_de_error():
    primero = cliente.get("/api/v1/eventos").json()["items"][0]
    assert cliente.get(f"/api/v1/eventos/{primero['id']}").json()["id"] == primero["id"]
    r = cliente.get("/api/v1/eventos/00000000-0000-4000-8000-000000000000")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "evento_no_encontrado"


def test_lugares_paginados_y_ficha():
    r = cliente.get("/api/v1/lugares", params={"tipo": "ruta"})
    items = r.json()["items"]
    assert items and all(i["tipo"] == "ruta" for i in items)
    assert cliente.get(f"/api/v1/lugares/{items[0]['id']}").status_code == 200


def test_cors_permite_la_app():
    r = cliente.options(
        "/api/v1/eventos",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
