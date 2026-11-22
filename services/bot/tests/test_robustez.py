"""Robustez: la cola sobrevive a un reinicio, se reintenta sola y al volver la api se confirma y se
avisa al publicador. Registro automático del webhook de Telegram al arrancar."""

import json

import pytest
from fastapi.testclient import TestClient

from app import api_cliente, canales, conversacion, telegram
from app.main import app
from app.schemas import MensajeEntrante

CAB = {"X-Internal-Token": "test"}


@pytest.fixture
def cola_en_disco(tmp_path, monkeypatch):
    ruta = tmp_path / "cola.json"
    monkeypatch.setenv("COLA_PATH", str(ruta))
    from app.config import get_settings
    get_settings.cache_clear()
    return ruta


def _msg(texto, de="+34611111111"):
    return MensajeEntrante(canal="whatsapp", de=de, texto=texto)


def _publicar_sin_api():
    conversacion.procesar(_msg("Concierto en Tahal el 5 de diciembre a las 20:00"))
    return conversacion.procesar(_msg("sí"))


def test_la_cola_se_guarda_en_disco_y_se_recupera(api, cola_en_disco):
    r = _publicar_sin_api()  # la api del conftest empieza caída
    assert "te aviso" in r[0]
    guardado = json.loads(cola_en_disco.read_text(encoding="utf-8"))
    assert guardado[0]["ruta"] == "/api/v1/eventos/importar"
    assert guardado[0]["al_reintentar"]["avisar"] == "+34611111111"

    api_cliente.pendientes.clear()  # «reinicio» del bot
    assert api_cliente.cargar_cola() == 1


def test_al_volver_la_api_importa_confirma_y_avisa(api, cola_en_disco):
    _publicar_sin_api()
    assert api_cliente.reintentar_pendientes() == 0  # sigue caída: no se pierde nada
    assert len(api_cliente.pendientes) == 1

    api.caida = False
    assert api_cliente.reintentar_pendientes() == 1
    assert api_cliente.pendientes == [] and json.loads(cola_en_disco.read_text(encoding="utf-8")) == []
    assert any(r.endswith("/confirmar") for _, r, _ in api.llamadas)
    aviso = canales.bandeja_consola[-1]
    assert aviso["para"] == "+34611111111" and "Ya hay conexión" in aviso["texto"]


def test_lo_que_la_api_rechaza_se_descarta(api):
    api_cliente.pendientes.append({"metodo": "POST", "ruta": "/api/v1/nada", "json": {}})
    api.caida = False  # la api falsa devuelve 404 a rutas desconocidas: reintentarlo daría lo mismo
    assert api_cliente.reintentar_pendientes() == 1 and api_cliente.pendientes == []


def test_cola_ilegible_no_rompe_el_arranque(cola_en_disco):
    cola_en_disco.write_text("{esto no es json", encoding="utf-8")
    assert api_cliente.cargar_cola() == 0


def test_al_arrancar_registra_el_webhook_y_carga_la_cola(cola_en_disco, monkeypatch):
    monkeypatch.setenv("PUBLIC_URL", "https://algo.trycloudflare.com/")
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    from app.config import get_settings
    get_settings.cache_clear()
    cola_en_disco.write_text(json.dumps([{"metodo": "POST", "ruta": "/x", "json": {}}]), encoding="utf-8")
    urls = []
    monkeypatch.setattr(telegram, "configurar_webhook", lambda url: urls.append(url) or True)
    with TestClient(app):  # ejecuta el arranque (lifespan)
        pass
    assert urls == ["https://algo.trycloudflare.com/webhook/telegram"]
    assert len(api_cliente.pendientes) == 1


def test_sin_public_url_no_toca_telegram(monkeypatch):
    monkeypatch.setattr(telegram, "configurar_webhook", lambda url: pytest.fail("no debe registrar"))
    with TestClient(app):
        pass


def test_endpoints_de_administracion(api, monkeypatch):
    cliente = TestClient(app)
    assert cliente.post("/admin/reintentar-cola").status_code == 401
    assert cliente.post("/admin/reintentar-cola", headers=CAB).json() == {"enviados": 0, "quedan": 0}
    assert cliente.post("/admin/webhook-telegram", json={}, headers=CAB).status_code == 422

    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(telegram, "configurar_webhook", lambda url: True)
    r = cliente.post("/admin/webhook-telegram", json={"public_url": "https://nueva.trycloudflare.com"}, headers=CAB)
    assert r.json() == {"url": "https://nueva.trycloudflare.com/webhook/telegram", "ok": True,
                        "web_url": get_settings().web_url}


def test_url_publica_nueva_sin_reiniciar_no_pierde_la_conversacion(api, monkeypatch):
    """Cambiar la URL del túnel (url_publica.py) no debe tirar lo que un publicador tiene a medias."""
    from app import conversacion, vecino
    from app.config import get_settings
    from app.schemas import MensajeEntrante
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    get_settings.cache_clear()
    monkeypatch.setattr(telegram, "configurar_webhook", lambda url: True)
    conversacion.procesar(MensajeEntrante(canal="whatsapp", de="+34600000101",
                                          texto="Fiesta de la castaña en Tahal con castañas asadas y música para "
                                                "toda la familia en la plaza del pueblo"))
    assert conversacion.estados["+34600000101"].borrador is not None  # a medias: le falta la fecha

    r = TestClient(app).post("/admin/webhook-telegram", headers=CAB,
                             json={"public_url": "https://otra.trycloudflare.com",
                                   "web_url": "https://otra.trycloudflare.com"})
    assert r.json()["ok"] and r.json()["web_url"] == "https://otra.trycloudflare.com"
    assert conversacion.estados["+34600000101"].borrador is not None  # sigue a medias
    assert vecino._enlace("ev-1") == "https://otra.trycloudflare.com/evento/ev-1"
