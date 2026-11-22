"""Choque de fechas al confirmar (app/choque_fechas.py): aviso con propuesta y decide quien crea el plan."""

import pytest

from app import api_cliente, canales, choque_fechas, conversacion
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante

DE = "+34611110000"
SABADO, OTRO_SABADO = "2026-12-12T17:00:00+01:00", "2026-12-19T17:00:00+01:00"
CHOQUE = {"choques": [{"evento_id": "e9", "titulo": "Verbena", "municipio": "Senés",
                       "fecha_inicio": "2026-12-12T22:00:00+01:00", "distancia_km": 6.2}],
          "alternativas": [OTRO_SABADO]}


def _msg(texto="", **kw):
    return MensajeEntrante(canal="whatsapp", de=DE, texto=texto, **kw)


def _textos(r) -> str:
    return "\n".join(x.texto if isinstance(x, Respuesta) else x for x in r)


@pytest.fixture
def choque(monkeypatch):
    llamadas = []
    monkeypatch.setattr(api_cliente, "choques", lambda f, m, e=None: llamadas.append((f, m)) or CHOQUE)
    conversacion.estados.pop(DE, None)
    return llamadas


def _hasta_confirmar():
    return conversacion.procesar(_msg("Torneo de fútbol sala en Uleila el 12 de diciembre a las 17:00, gratis"))


def test_avisa_del_choque_y_cambia_la_fecha(choque):
    r = _hasta_confirmar()
    assert choque and "Verbena" in _textos(r)
    assert canales.bandeja_consola[-1]["botones"] == [(choque_fechas.CAMBIAR, "📅 Cambiar al sábado 19"),
                             (choque_fechas.MANTENER, "Mantener la fecha")]
    r = conversacion.procesar(_msg("", boton_id=choque_fechas.CAMBIAR))
    est = conversacion.estados[DE]
    assert "sábado 19" in _textos(r) and "SÍ" in _textos(r)
    assert est.borrador.campos["fecha_inicio"].valor == OTRO_SABADO
    assert est.campos_corregidos["fecha_inicio"] == OTRO_SABADO  # llega a la API al confirmar


def test_mantener_la_fecha(choque):
    _hasta_confirmar()
    r = conversacion.procesar(_msg("", boton_id=choque_fechas.MANTENER))
    est = conversacion.estados[DE]
    assert "mantengo" in _textos(r) and est.esperando_confirmacion
    assert "fecha_inicio" not in est.campos_corregidos


def test_sin_choque_pregunta_como_siempre(monkeypatch):
    monkeypatch.setattr(api_cliente, "choques", lambda f, m, e=None: {"choques": [], "alternativas": []})
    conversacion.estados.pop(DE, None)
    r = _hasta_confirmar()
    assert "¿Lo publico así?" in _textos(r) and conversacion.estados[DE].fecha_propuesta is None
