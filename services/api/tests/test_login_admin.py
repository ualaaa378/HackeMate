"""POST /auth/admin: acceso de la moderación del ayuntamiento con usuario y contraseña (ADMIN_USUARIO / ADMIN_CONTRASENA)."""

import pytest

from app.config import Settings, avisar_configuracion_insegura, get_settings
from app.seed import sembrar
from tests.test_importar import VIERNES

URL = "/api/v1/auth/admin"
LUCIA_MODERADORA = "5a5e0000-0000-4000-8000-000000000002"


@pytest.fixture(autouse=True)
def credenciales_de_ejemplo(monkeypatch):
    """Los tests no dependen del .env local (la máquina de la demo usa otra contraseña): admin / 1234."""
    monkeypatch.setattr(get_settings(), "admin_usuario", "admin")
    monkeypatch.setattr(get_settings(), "admin_contrasena", "1234")


@pytest.fixture
def api(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


def test_admin_1234_da_sesion_de_moderador(api):
    r = api.post(URL, json={"usuario": "admin", "contrasena": "1234"})
    assert r.status_code == 200, r.text
    token = r.json()
    assert token["usuario"]["id"] == LUCIA_MODERADORA and token["usuario"]["rol"] == "moderador"
    # Con esa sesión se entra en la bandeja
    pendientes = api.get("/api/v1/moderacion/pendientes",
                         headers={"Authorization": f"Bearer {token['access_token']}"})
    assert pendientes.status_code == 200


@pytest.mark.parametrize("usuario, contrasena", [("admin", "12345"), ("Admin", "1234"), ("otro", "1234"), ("admin", " 1234")])
def test_credenciales_incorrectas(api, usuario, contrasena):
    r = api.post(URL, json={"usuario": usuario, "contrasena": contrasena})
    assert r.status_code == 401 and r.json()["error"]["code"] == "credenciales_invalidas"


def test_faltan_campos(api):
    assert api.post(URL, json={"usuario": "admin"}).status_code == 422
    assert api.post(URL, json={"usuario": "", "contrasena": "1234"}).status_code == 422


def test_otra_contrasena_desde_el_env(api, monkeypatch):
    monkeypatch.setattr(get_settings(), "admin_contrasena", "otra-clave")
    assert api.post(URL, json={"usuario": "admin", "contrasena": "1234"}).status_code == 401
    assert api.post(URL, json={"usuario": "admin", "contrasena": "otra-clave"}).status_code == 200


def test_sin_moderador_503(cliente):
    r = cliente.post(URL, json={"usuario": "admin", "contrasena": "1234"})
    assert r.status_code == 503 and r.json()["error"]["code"] == "sin_moderador"


def test_avisa_si_la_contrasena_es_la_de_ejemplo_fuera_de_la_demo():
    avisos = avisar_configuracion_insegura(Settings(_env_file=None, demo_mode=False, jwt_secret="x" * 32))
    assert any("ADMIN_CONTRASENA" in a for a in avisos)
    assert not any("ADMIN_CONTRASENA" in a for a in
                   avisar_configuracion_insegura(Settings(_env_file=None, demo_mode=False, jwt_secret="x" * 32, admin_contrasena="buena")))


@pytest.fixture(autouse=True)
def _sin_fallos_previos():
    from app.rutas import auth

    auth._fallos_admin.clear()
    yield
    auth._fallos_admin.clear()


def test_cinco_fallos_bloquean_la_ip_con_429(api):
    for _ in range(5):
        assert api.post(URL, json={"usuario": "admin", "contrasena": "mal"}).status_code == 401
    r = api.post(URL, json={"usuario": "admin", "contrasena": "1234"})
    assert r.status_code == 429 and r.json()["error"]["code"] == "demasiados_intentos"
    # Otra IP (por el túnel, CF-Connecting-IP) sigue pudiendo entrar
    otra = api.post(URL, json={"usuario": "admin", "contrasena": "1234"}, headers={"CF-Connecting-IP": "203.0.113.9"})
    assert otra.status_code == 200


def test_entrar_bien_borra_los_fallos(api):
    for _ in range(4):
        api.post(URL, json={"usuario": "admin", "contrasena": "mal"})
    assert api.post(URL, json={"usuario": "admin", "contrasena": "1234"}).status_code == 200
    for _ in range(4):
        assert api.post(URL, json={"usuario": "admin", "contrasena": "mal"}).status_code == 401


def test_tope_total_frena_a_quien_cambia_de_ip(api, monkeypatch):
    from app.rutas import auth

    monkeypatch.setattr(auth, "ADMIN_FALLOS_TOTALES", 3)
    for i in range(3):
        api.post(URL, json={"usuario": "admin", "contrasena": "mal"}, headers={"CF-Connecting-IP": f"198.51.100.{i}"})
    r = api.post(URL, json={"usuario": "admin", "contrasena": "1234"}, headers={"CF-Connecting-IP": "198.51.100.99"})
    assert r.status_code == 429


def test_avisa_tambien_en_modo_demo():
    avisos = avisar_configuracion_insegura(Settings(_env_file=None, demo_mode=True))
    assert any("ADMIN_CONTRASENA" in a for a in avisos)
    assert any("JWT_SECRET" in a for a in avisos)
    assert any("INTERNAL_TOKEN" in a for a in avisos)
