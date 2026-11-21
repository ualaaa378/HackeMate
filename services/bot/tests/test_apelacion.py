"""P3b: apelar desde el bot un plan rechazado (POST /eventos/{id}/apelacion con usuario_id)."""

import pytest
from fastapi.testclient import TestClient

from app import api_cliente, apelacion, canales, conversacion
from app.api_cliente import ErrorApi
from app.main import app
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante
from tests.test_avisos_codigo import CAB

CARMEN = {"id": "u-carmen", "nombre": "Carmen", "rol": "vecino", "telefono": "+34600000201"}


def _msg(texto="", **kw):
    return MensajeEntrante(canal="telegram", de="+34600000201", texto=texto, **kw)


def _texto(r) -> str:
    return "\n".join(x.texto if isinstance(x, Respuesta) else x for x in r)


@pytest.fixture
def carmen(api, monkeypatch):
    api.caida = False
    api.usuarios["+34600000201"] = CARMEN
    apelacion._esperando.clear()
    enviadas = []
    monkeypatch.setattr(api_cliente, "apelar", lambda ev, uid, motivo: enviadas.append((ev, uid, motivo)) or {})
    return enviadas


def test_el_aviso_de_rechazo_lleva_el_boton_apelar(monkeypatch):
    enviados = []
    monkeypatch.setattr(canales, "enviar", lambda d, t, botones=None, **kw: enviados.append(botones))
    r = TestClient(app).post("/notify", headers=CAB, json={
        "contacto": "tg:777", "tipo": "moderacion", "evento_id": "e9",
        "texto": "Tu evento «Fiesta» no se ha publicado. Motivo: falta el lugar"})
    assert r.status_code == 200 and enviados == [[("apelar:e9", "✍️ Apelar")]]


def test_apelar_con_el_boton(carmen):
    r = conversacion.procesar(_msg("", boton_id="apelar:e9"))
    assert "Por qué" in _texto(r)
    r = conversacion.procesar(_msg("corto"))
    assert "al menos 10" in _texto(r) and carmen == []
    r = conversacion.procesar(_msg("Ya hemos puesto el lugar: la plaza del pueblo"))
    assert carmen == [("e9", "u-carmen", "Ya hemos puesto el lugar: la plaza del pueblo")]
    assert "enviado tu apelación" in _texto(r) and not apelacion.esperando("+34600000201")


def test_apelar_escribiendo_busca_sus_rechazados(carmen, monkeypatch):
    monkeypatch.setattr(api_cliente, "planes_de", lambda uid: [
        {"id": "p1", "titulo": "Ruta", "estado": "publicado"},
        {"id": "p2", "titulo": "Fiesta", "estado": "rechazado", "apelacion": None},
        {"id": "p3", "titulo": "Taller", "estado": "rechazado", "apelacion": {"motivo": "x" * 10}}])
    r = conversacion.procesar(_msg("quiero apelar"))
    assert "Por qué" in _texto(r) and apelacion._esperando["+34600000201"] == "p2"


def test_segunda_apelacion_y_no_apelar(carmen, monkeypatch):
    def ya_usada(*a):
        raise ErrorApi(409, "apelacion_usada", "Ya apeló")
    monkeypatch.setattr(api_cliente, "apelar", ya_usada)
    conversacion.procesar(_msg("", boton_id="apelar:e9"))
    r = conversacion.procesar(_msg("Por favor, revisadlo otra vez"))
    assert "definitiva" in _texto(r)
    conversacion.procesar(_msg("", boton_id="apelar:e9"))
    assert "no apelo" in _texto(conversacion.procesar(_msg("", boton_id="apelar_no")))
    assert not apelacion.esperando("+34600000201")


@pytest.mark.parametrize("texto,si", [("quiero apelar", True), ("quiero recurrir el rechazo", True),
                                      ("que lo revisen otra vez", True), ("¿qué hay este finde?", False)])
def test_detecta_apelar(texto, si):
    assert apelacion.quiere_apelar(texto) is si
