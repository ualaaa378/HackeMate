"""A6: la API detrás del nginx de la web y del túnel (una sola URL pública) y desde el APK de Capacitor."""

from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from uvicorn.middleware.proxy_headers import ProxyHeadersMiddleware

from app.config import Settings, get_settings
from app.main import app
from app.seed import sembrar
from tests.test_importar import VIERNES

APK_ANDROID = "https://localhost"
APK_IOS = "capacitor://localhost"
DOCKERFILE = Path(__file__).resolve().parents[1] / "Dockerfile"


def test_cors_por_defecto_admite_el_apk_de_capacitor():
    por_defecto = Settings.model_fields["cors_origenes"].default.split(",")
    assert APK_ANDROID in por_defecto and APK_IOS in por_defecto
    assert "http://localhost:8080" in por_defecto  # la web en local sigue igual


@pytest.mark.parametrize("origen", [APK_ANDROID, APK_IOS])
def test_preflight_desde_el_apk(cliente, origen):
    if origen not in get_settings().lista_cors:
        pytest.skip(f"CORS_ORIGENES del .env no incluye {origen}: copia la línea nueva de .env.example")
    r = cliente.options(
        "/api/v1/eventos",
        headers={"Origin": origen, "Access-Control-Request-Method": "POST",
                 "Access-Control-Request-Headers": "authorization,content-type"},
    )
    assert r.status_code == 200
    assert r.headers["access-control-allow-origin"] == origen


def test_dockerfile_arranca_uvicorn_detras_del_proxy():
    cmd = next(l for l in DOCKERFILE.read_text(encoding="utf-8").splitlines() if l.startswith("CMD"))
    assert "--proxy-headers" in cmd and "--forwarded-allow-ips='*'" in cmd


def test_con_cabeceras_del_proxy_las_redirecciones_salen_con_https_y_el_dominio_publico(motor):
    # Lo que hace uvicorn con --proxy-headers: la API ve el esquema y el host de la URL pública del túnel.
    detras = TestClient(ProxyHeadersMiddleware(app, trusted_hosts="*"))
    r = detras.get(
        "/api/v1/eventos/",
        headers={"Host": "demo.trycloudflare.com", "X-Forwarded-Proto": "https", "X-Forwarded-For": "1.2.3.4"},
        follow_redirects=False,
    )
    assert r.status_code == 307
    assert r.headers["location"] == "https://demo.trycloudflare.com/api/v1/eventos"


def test_ninguna_respuesta_lleva_localhost(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    eventos = cliente.get("/api/v1/eventos?size=100")
    assert eventos.status_code == 200 and eventos.json()["items"]
    assert "localhost" not in eventos.text
    for e in eventos.json()["items"][:5]:
        assert "localhost" not in cliente.get(f"/api/v1/eventos/{e['id']}").text
        assert "localhost" not in cliente.get(f"/api/v1/eventos/{e['id']}/ics").text
    for ruta in ("/api/v1/municipios", "/api/v1/lugares?size=100", "/api/v1/publicadores?size=100"):
        assert "localhost" not in cliente.get(ruta).text, ruta
