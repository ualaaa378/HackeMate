"""Avisos de las tareas programadas de la API: recordatorio, «¿qué tal fue?» y resumen semanal."""

import pytest
from fastapi.testclient import TestClient

from app import api_cliente, canales, conversacion, vecino
from app.main import app
from app.schemas import MensajeEntrante

CAB = {"X-Internal-Token": "test"}
DE = "+34600000201"


def _msg(texto="", **kw):
    return MensajeEntrante(canal="whatsapp", de=DE, texto=texto, **kw)


@pytest.fixture
def comentarios(api, monkeypatch):
    api.caida = False
    api.usuarios[DE] = {"id": "u-carmen", "nombre": "Carmen", "rol": "vecino", "telefono": DE}
    lista = []
    monkeypatch.setattr(api_cliente, "comentar_en_chat", lambda ev, uid, t: lista.append((ev, uid, t)) or {})
    return lista


def _notify(**cuerpo):
    assert TestClient(app).post("/notify", headers=CAB, json={"telefono": DE, **cuerpo}).status_code == 200
    return canales.bandeja_consola[-1]


def test_recordatorio_solo_con_ver_el_plan():
    m = _notify(tipo="anuncio", evento_id="e1", texto="⏰ Mañana a las 09:00 tienes «Ruta»")
    assert m["botones"] == [("info:e1", "ℹ️ Ver el plan")]


def test_recomendacion_sigue_con_apuntarme():
    m = _notify(tipo="recomendacion", evento_id="e1", texto="🔔 Plan nuevo")
    assert m["botones"][0] == ("insc:e1", "✋ Apuntarme")


def test_que_tal_fue_con_botones_y_el_boton_deja_un_comentario(comentarios):
    m = _notify(tipo="anuncio", evento_id="e1", texto="¿Qué tal fue «Ruta»? 😊 Cuéntamelo")
    assert m["botones"] == vecino.botones_valoracion("e1")
    r = conversacion.procesar(_msg(boton_id="valora:e1:muy_bien"))
    assert comentarios == [("e1", "u-carmen", "😍 ¡Muy bien!")] and "Gracias" in r[0]
    # Después del botón aún puede añadir algo con sus palabras
    conversacion.procesar(_msg("La guía explicaba genial, repetiremos"))
    assert comentarios[-1] == ("e1", "u-carmen", "💬 La guía explicaba genial, repetiremos")
    # Y ya no: el siguiente mensaje vuelve a ser normal
    conversacion.procesar(_msg("Otra cosa"))
    assert len(comentarios) == 2


def test_contestar_con_palabras_y_si_busca_no_es_una_valoracion(comentarios):
    _notify(tipo="anuncio", evento_id="e1", texto="¿Qué tal fue «Ruta»?")
    conversacion.procesar(_msg("¿qué hay este finde?"))  # está buscando: no se toma como valoración
    assert comentarios == []
    conversacion.procesar(_msg("Nos encantó, gracias"))
    assert comentarios == [("e1", "u-carmen", "💬 Nos encantó, gracias")]


def test_una_vecina_recien_dada_de_alta_no_se_queda_olvidada(api, monkeypatch):
    """Antes se guardaba 60 s «este contacto no existe» y, tras darla de alta, se la ignoraba."""
    api.caida = False
    comentarios = []
    monkeypatch.setattr(api_cliente, "comentar_en_chat", lambda ev, uid, t: comentarios.append(uid) or {})
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: True)
    nueva = "+34611000888"
    conversacion.procesar(MensajeEntrante(canal="whatsapp", de=nueva, texto="Me gustan las rutas"))  # la da de alta
    TestClient(app).post("/notify", headers=CAB, json={"telefono": nueva, "tipo": "anuncio", "evento_id": "e1",
                                                       "texto": "¿Qué tal fue «Ruta»?"})
    conversacion.procesar(MensajeEntrante(canal="whatsapp", de=nueva, texto="", boton_id="valora:e1:bien"))
    assert comentarios == [api.usuarios[nueva]["id"]]
