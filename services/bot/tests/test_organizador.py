"""P5b: «modificar plan» por el bot. Lista los planes de quien escribe (P5a), elige plan y campo, y hace el PATCH."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

import pytest

from app import api_cliente, conversacion, organizador
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante

TZ = ZoneInfo("Europe/Madrid")
CARMEN = {"id": "u-carmen", "nombre": "Carmen", "rol": "vecino", "telefono": "+34600000201"}


def _msg(texto="", **kw):
    return MensajeEntrante(canal="telegram", de="+34600000201", texto=texto, **kw)


def _texto(r) -> str:
    return "\n".join(x.texto if isinstance(x, Respuesta) else x for x in r)


def _plan(id_, titulo, estado="publicado", dias=5):
    fecha = (datetime.now(TZ) + timedelta(days=dias)).replace(hour=10, minute=0, second=0, microsecond=0)
    return {"id": id_, "titulo": titulo, "estado": estado, "fecha_inicio": fecha.isoformat()}


@pytest.fixture
def planes(api, monkeypatch):
    api.caida = False
    api.usuarios["+34600000201"] = CARMEN
    organizador._sesiones.clear()
    lista = [_plan("p1", "Merienda de otoño en la plaza", "en_revision"),
             _plan("p2", "Ruta de las cortijadas", "publicado"),
             _plan("p3", "Taller de esparto", "rechazado")]
    cambios = []
    monkeypatch.setattr(api_cliente, "planes_de", lambda uid: lista if uid == "u-carmen" else [])
    monkeypatch.setattr(api_cliente, "editar_evento",
                        lambda ev, c: cambios.append((ev, c)) or {"id": ev, "titulo": next(
                            p["titulo"] for p in lista if p["id"] == ev)})
    return lista, cambios


@pytest.mark.parametrize("texto,si", [
    ("modificar plan", True),
    ("mis planes", True),
    ("quiero cambiar la hora de la ruta", True),
    ("Quiero editar mi evento", True),
    ("¿qué hay este finde?", False),
    ("Concierto de la banda el domingo 14 de diciembre a las 18:00 en la plaza. Este año cambia el lugar del "
     "concierto por la lluvia, traed paraguas y ganas de bailar.", False),
])
def test_detecta_modificar(texto, si):
    assert organizador.quiere_modificar(texto) is si


def test_lista_los_planes_y_cambia_el_lugar_con_botones(planes):
    _, cambios = planes
    r = conversacion._responder(_msg("modificar plan"))  # sin enviar: para ver los botones
    t = _texto(r)
    assert "Merienda de otoño" in t and "en revisión" in t and "rechazado" in t
    botones = [b[0] for b in r[-1].botones]
    assert "orgplan:p1" in botones and "orgplan:p2" in botones
    assert "orgplan:p3" not in botones  # rechazado: se apela, no se modifica
    conversacion.procesar(_msg("", boton_id="orgplan:p2"))
    r = conversacion.procesar(_msg("", boton_id="orgcampo:lugar"))
    assert "Dónde" in _texto(r)
    r = conversacion.procesar(_msg("Plaza de la Iglesia"))
    assert cambios == [("p2", {"lugar": "Plaza de la Iglesia"})]
    assert "Hecho" in _texto(r) and "avisado a las personas apuntadas" in _texto(r)
    assert not organizador.en_curso("+34600000201")


def test_frase_con_plan_y_campo_va_directa_y_cambia_solo_la_hora(planes):
    lista, cambios = planes
    r = conversacion.procesar(_msg("quiero cambiar la hora de la ruta"))
    assert "Cuándo" in _texto(r)
    conversacion.procesar(_msg("a las 18:30"))
    (ev, c), = cambios
    nueva = datetime.fromisoformat(c["fecha_inicio"]).astimezone(TZ)
    antigua = datetime.fromisoformat(lista[1]["fecha_inicio"]).astimezone(TZ)
    assert ev == "p2" and nueva.date() == antigua.date() and (nueva.hour, nueva.minute) == (18, 30)


def test_plazas_y_cancelar(planes):
    _, cambios = planes
    conversacion.procesar(_msg("cambiar las plazas de la merienda"))
    r = conversacion.procesar(_msg("muchas"))
    assert "número" in _texto(r) and cambios == []
    conversacion.procesar(_msg("40"))
    assert cambios == [("p1", {"plazas_totales": 40})]
    conversacion.procesar(_msg("modificar plan"))
    r = conversacion.procesar(_msg("", boton_id="orgfin"))
    assert "no cambio nada" in _texto(r) and len(cambios) == 1


def test_sin_usuario_o_sin_planes(api, monkeypatch):
    api.caida = False
    organizador._sesiones.clear()
    r = conversacion.procesar(_msg("modificar plan"))
    assert "No encuentro planes tuyos" in _texto(r)
    api.usuarios["+34600000201"] = CARMEN
    monkeypatch.setattr(api_cliente, "planes_de", lambda uid: [])
    assert "Todavía no has propuesto" in _texto(conversacion.procesar(_msg("mis planes")))


def test_una_descripcion_con_fraude_no_se_guarda(planes):
    _, cambios = planes
    conversacion.procesar(_msg("cambiar la descripción de la ruta"))
    r = conversacion.procesar(_msg("Reserva tu plaza pagando 50 euros por adelantado por Bizum al 600111222, "
                                   "plazas limitadas, solo hoy, mándame tus datos bancarios por privado"))
    assert cambios == [] and "No puedo guardar" in _texto(r)
