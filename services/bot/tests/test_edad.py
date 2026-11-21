"""P4b: la edad, opcional, al identificarse por primera vez (vecinos) y en el alta de asociaciones (responsable)."""

from app import api_cliente, conversacion
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante

TG = "tg:555"


def _msg(texto="", **kw):
    return MensajeEntrante(canal="telegram", de=TG, texto=texto, nombre="Rosa", **kw)


def _texto(r) -> str:
    return "\n".join(x.texto if isinstance(x, Respuesta) else x for x in r)


def _identificarse(api):
    api.caida = False
    conversacion.esperando_edad.discard(TG)
    return conversacion.procesar(_msg("", telefono_compartido="+34600000777"))


def test_pregunta_la_edad_al_identificarse_y_la_guarda(api, monkeypatch):
    guardado = []
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: guardado.append(c) or True)
    r = _identificarse(api)
    assert "cuántos años tienes" in _texto(r)
    r = conversacion.procesar(_msg("tengo 72 años"))
    assert guardado == [{"edad": 72}] and "Apuntado" in _texto(r)
    assert TG not in conversacion.esperando_edad


def test_menos_de_14_y_saltar(api, monkeypatch):
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: (_ for _ in ()).throw(AssertionError))
    _identificarse(api)
    r = conversacion.procesar(_msg("12"))
    assert "al menos 14" in _texto(r)
    r = conversacion.procesar(_msg("", boton_id="edad_saltar"))
    assert "Sin problema" in _texto(r) and TG not in conversacion.esperando_edad


def test_si_contesta_otra_cosa_sigue_la_conversacion(api):
    _identificarse(api)
    conversacion.procesar(_msg("¿qué hay este finde?"))
    assert TG not in conversacion.esperando_edad


def test_no_pregunta_si_ya_la_tiene(api):
    api.caida = False
    api.usuarios[TG] = {"id": "u1", "nombre": "Rosa", "rol": "vecino", "edad": 70}
    monkeypatch_vincular = api_cliente.vincular
    try:
        api_cliente.vincular = lambda tel, contacto, nombre=None: api.usuarios[TG]
        r = conversacion.procesar(_msg("", telefono_compartido="+34600000777"))
    finally:
        api_cliente.vincular = monkeypatch_vincular
    assert "cuántos años" not in _texto(r)
