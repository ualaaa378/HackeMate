import hashlib
import hmac
import json

import httpx
import pytest
from fastapi.testclient import TestClient

from app import canales, meta
from app.main import app

cliente = TestClient(app)


def _payload(mensajes, contactos=None):
    return {"object": "whatsapp_business_account", "entry": [{"id": "WABA", "changes": [{
        "field": "messages",
        "value": {"messaging_product": "whatsapp", "metadata": {"phone_number_id": "123"},
                  "contacts": contactos or [{"wa_id": "34611111111", "profile": {"name": "Paco"}}],
                  "messages": mensajes}}]}]}


def _texto(cuerpo, id_="wamid.1"):
    return {"from": "34611111111", "id": id_, "timestamp": "1", "type": "text", "text": {"body": cuerpo}}


@pytest.fixture
def meta_cfg(monkeypatch):
    monkeypatch.setenv("META_VERIFY_TOKEN", "verificame")
    monkeypatch.setenv("META_APP_SECRET", "secreto")
    from app.config import get_settings
    get_settings.cache_clear()


def _firmar(cuerpo: bytes) -> str:
    return "sha256=" + hmac.new(b"secreto", cuerpo, hashlib.sha256).hexdigest()


def test_parsear_texto_boton_audio_y_ubicacion():
    msgs = meta.parsear(_payload([
        _texto("hola"),
        {"from": "34611111111", "id": "w2", "type": "interactive",
         "interactive": {"type": "button_reply", "button_reply": {"id": "si", "title": "Sí, publicar"}}},
        {"from": "34611111111", "id": "w3", "type": "audio", "audio": {"id": "MEDIA1", "mime_type": "audio/ogg"}},
        {"from": "34611111111", "id": "w4", "type": "location", "location": {"latitude": 37.19, "longitude": -2.4}},
        {"from": "34611111111", "id": "w5", "type": "reaction", "reaction": {"emoji": "👍"}},
    ]))
    assert [m.id_mensaje for m in msgs] == ["wamid.1", "w2", "w3", "w4"]  # la reacción se ignora
    assert msgs[0].de == "+34611111111" and msgs[0].nombre == "Paco" and msgs[0].texto == "hola"
    assert msgs[1].boton_id == "si"
    assert msgs[2].media_id == "MEDIA1" and msgs[2].media_tipo == "audio/ogg"
    assert msgs[3].lat == 37.19


def test_parsear_ignora_estados_de_entrega():
    payload = {"entry": [{"changes": [{"value": {"statuses": [{"id": "x", "status": "read"}]}}]}]}
    assert meta.parsear(payload) == []


def test_verificacion_del_webhook(meta_cfg):
    ok = cliente.get("/webhook/meta", params={"hub.mode": "subscribe", "hub.verify_token": "verificame",
                                              "hub.challenge": "12345"})
    assert ok.status_code == 200 and ok.text == "12345"
    mal = cliente.get("/webhook/meta", params={"hub.mode": "subscribe", "hub.verify_token": "otro",
                                               "hub.challenge": "12345"})
    assert mal.status_code == 403


def test_webhook_rechaza_firma_incorrecta(meta_cfg):
    cuerpo = json.dumps(_payload([_texto("hola")])).encode()
    r = cliente.post("/webhook/meta", content=cuerpo, headers={"X-Hub-Signature-256": "sha256=falsa",
                                                               "Content-Type": "application/json"})
    assert r.status_code == 403


def test_webhook_procesa_y_no_repite_reenvios(meta_cfg):
    cuerpo = json.dumps(_payload([_texto("hola", id_="wamid.unico")])).encode()
    cab = {"X-Hub-Signature-256": _firmar(cuerpo), "Content-Type": "application/json"}
    assert cliente.post("/webhook/meta", content=cuerpo, headers=cab).status_code == 200
    assert cliente.post("/webhook/meta", content=cuerpo, headers=cab).status_code == 200  # reenvío de Meta
    respuestas = [m for m in canales.bandeja_consola if m["para"] == "+34611111111"]
    assert len(respuestas) == 1 and "Buscas planes" in respuestas[0]["texto"]


def test_confirmacion_lleva_botones():
    cliente.post("/dev/mensaje", json={"de": "+34644444444",
                                       "texto": "Concierto en Tahal el 5 de diciembre a las 20:00"})
    ultimo = canales.bandeja_consola[-1]
    assert ultimo["botones"] == [("si", "Sí, publicar"), ("no", "No")]


def test_boton_si_confirma_aunque_el_texto_sea_otro():
    from app import conversacion
    from app.schemas import MensajeEntrante
    conversacion.procesar(MensajeEntrante(canal="whatsapp", de="+34655555555",
                                          texto="Concierto en Tahal el 5 de diciembre a las 20:00"))
    r = conversacion.procesar(MensajeEntrante(canal="whatsapp", de="+34655555555",
                                              texto="Sí, publicar", boton_id="si"))
    assert "Guardado" in r[0]


def test_envio_meta_con_botones_y_plantilla(monkeypatch):
    monkeypatch.setenv("CANAL", "meta")
    monkeypatch.setenv("META_TOKEN", "tok")
    monkeypatch.setenv("META_PHONE_NUMBER_ID", "999")
    from app.config import get_settings
    get_settings.cache_clear()
    enviados = []

    def post(url, json, headers, timeout):
        enviados.append((url, json, headers))
        return httpx.Response(200, json={"messages": [{"id": "wamid.x"}]}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    canales.enviar("+34611111111", "¿Lo publico?", [("si", "Sí, publicar"), ("no", "No")])
    canales.enviar_plantilla("+34611111111", "cambio_hora", ["Ruta", "10:00"], texto_alternativo="x")

    url, cuerpo, cab = enviados[0]
    assert url == "https://graph.facebook.com/v26.0/999/messages"
    assert cab["Authorization"] == "Bearer tok"
    assert cuerpo["to"] == "34611111111" and cuerpo["type"] == "interactive"
    assert cuerpo["interactive"]["action"]["buttons"][0]["reply"] == {"id": "si", "title": "Sí, publicar"}
    plantilla = enviados[1][1]["template"]
    assert plantilla["name"] == "cambio_hora" and plantilla["language"] == {"code": "es"}
    assert [p["text"] for p in plantilla["components"][0]["parameters"]] == ["Ruta", "10:00"]


def test_fallos_de_entrega_con_codigo_de_error():
    payload = {"entry": [{"changes": [{"value": {"statuses": [
        {"id": "w", "status": "delivered", "recipient_id": "34600"},
        {"id": "w2", "status": "failed", "recipient_id": "34600", "errors": [
            {"code": 131047, "title": "Re-engagement message",
             "error_data": {"details": "More than 24 hours have passed"}}]},
    ]}}]}]}
    assert meta.fallos_de_entrega(payload) == [
        {"para": "34600", "codigo": 131047, "motivo": "Re-engagement message",
         "detalle": "More than 24 hours have passed"}]
