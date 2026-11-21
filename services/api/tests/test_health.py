from fastapi.testclient import TestClient

from app.main import app


def test_health():
    r = TestClient(app).get("/health")
    assert r.status_code == 200
    cuerpo = r.json()
    assert cuerpo["status"] == "ok"
    assert cuerpo["version"]


def test_aviso_si_jwt_secret_es_el_de_ejemplo_fuera_de_demo(caplog):
    import logging

    from app.config import JWT_SECRET_POR_DEFECTO, Settings, avisar_configuracion_insegura

    with caplog.at_level(logging.WARNING, logger="app.config"):
        avisos = avisar_configuracion_insegura(Settings(jwt_secret=JWT_SECRET_POR_DEFECTO, demo_mode=False))
    assert len(avisos) == 1 and "JWT_SECRET" in avisos[0]
    assert any("JWT_SECRET" in r.getMessage() and r.levelno == logging.WARNING for r in caplog.records)

    assert avisar_configuracion_insegura(Settings(jwt_secret=JWT_SECRET_POR_DEFECTO, demo_mode=True)) == []
    assert avisar_configuracion_insegura(Settings(jwt_secret="un-secreto-de-verdad", demo_mode=False)) == []


def test_arranca_aunque_el_jwt_secret_sea_el_de_ejemplo(monkeypatch, caplog):
    import logging

    from app.config import JWT_SECRET_POR_DEFECTO, get_settings

    monkeypatch.setenv("JWT_SECRET", JWT_SECRET_POR_DEFECTO)
    monkeypatch.setenv("DEMO_MODE", "false")
    get_settings.cache_clear()
    try:
        with caplog.at_level(logging.WARNING, logger="app.config"), TestClient(app) as cliente:
            assert cliente.get("/health").status_code == 200
        assert any("JWT_SECRET" in r.getMessage() for r in caplog.records)
    finally:
        get_settings.cache_clear()
