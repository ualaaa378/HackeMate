"""Idea 6: compartir coche. El bot pone los botones a la propuesta de la API y le pasa el sí o el no."""

import pytest
from fastapi.testclient import TestClient

from app import api_cliente, canales, conversacion
from app.api_cliente import ErrorApi
from app.main import app
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante
from tests.test_avisos_codigo import CAB

ANA = {"id": "u-ana", "nombre": "Ana", "rol": "vecino", "telefono": "+34600000301"}


def _msg(texto="", **kw):
    return MensajeEntrante(canal="telegram", de="+34600000301", texto=texto, **kw)


def _texto(r) -> str:
    return "\n".join(x.texto if isinstance(x, Respuesta) else x for x in r)


@pytest.fixture
def ana(api, monkeypatch):
    api.caida = False
    api.usuarios["+34600000301"] = ANA
    llamadas = []

    def responder(ev, uid, acepta):
        llamadas.append((ev, uid, acepta))
        return {"respuesta": "si" if acepta else "no", "companeros": ana.companeros if acepta else []}

    ana = type("A", (), {"companeros": [], "llamadas": llamadas})
    monkeypatch.setattr(api_cliente, "responder_coche", responder)
    return ana


def test_la_propuesta_lleva_botones_de_si_y_no(monkeypatch):
    enviados = []
    monkeypatch.setattr(canales, "enviar", lambda d, t, botones=None, **kw: enviados.append(botones))
    r = TestClient(app).post("/notify", headers=CAB, json={
        "contacto": "tg:777", "tipo": "anuncio", "evento_id": "e1",
        "texto": "🚗 Hay otro vecino de Senés apuntados a «Feria» en Tahal. ¿Os apetece ir juntos en coche?"})
    assert r.status_code == 200
    assert enviados == [[("coche:si:e1", "🚗 Sí, vamos juntos"), ("coche:no:e1", "No, gracias")]]


def test_el_aviso_de_pareja_hecha_no_repite_los_botones(monkeypatch):
    enviados = []
    monkeypatch.setattr(canales, "enviar", lambda d, t, botones=None, **kw: enviados.append(botones))
    TestClient(app).post("/notify", headers=CAB, json={
        "contacto": "tg:777", "tipo": "anuncio", "evento_id": "e1", "texto": "✅🚗 Beto también quiere…"})
    assert enviados == [[("info:e1", "ℹ️ Ver el plan")]]


def test_si_sin_companeros_todavia(ana):
    r = conversacion.procesar(_msg("", boton_id="coche:si:e1"))
    assert ana.llamadas == [("e1", "u-ana", True)] and "En cuanto otro vecino" in _texto(r)


def test_si_con_companero_da_el_contacto(ana):
    ana.companeros = ["Beto (+34600000302)"]
    r = conversacion.procesar(_msg("", boton_id="coche:si:e1"))
    assert "Beto (+34600000302)" in _texto(r)


def test_no_no_pasa_el_contacto(ana):
    r = conversacion.procesar(_msg("", boton_id="coche:no:e1"))
    assert ana.llamadas == [("e1", "u-ana", False)] and "no paso tu contacto" in _texto(r)


def test_ya_no_disponible(ana, monkeypatch):
    def falla(*a):
        raise ErrorApi(409, "coche_no_disponible", "x")

    monkeypatch.setattr(api_cliente, "responder_coche", falla)
    assert "ya no está disponible" in _texto(conversacion.procesar(_msg("", boton_id="coche:si:e1")))
