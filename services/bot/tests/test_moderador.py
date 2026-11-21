"""Idea 5: asistente del moderador. Resumen de la bandeja, sugerencia por plan y motivo de rechazo amable (IA) que el
moderador revisa antes de enviarlo."""

import pytest

from app import conversacion
from app.agentes import moderador
from app.respuestas import Respuesta
from app.schemas import MensajeEntrante

LUCIA = {"id": "u1", "nombre": "Lucía", "rol": "moderador"}
MOD = "tg:1"


def _msg(texto="", **kw):
    return MensajeEntrante(canal="telegram", de=MOD, texto=texto, **kw)


def _texto(r) -> str:
    return "\n".join(x.texto if isinstance(x, Respuesta) else x for x in r)


def _item(id_, titulo, motivo):
    return {"tipo": "evento", "motivo": motivo, "score_spam": 0.1, "evento": {
        "id": id_, "titulo": titulo, "municipio": "Tahal", "fecha_inicio": "2026-12-05T20:00:00+01:00"}}


@pytest.fixture
def bandeja(api):
    api.caida = False
    api.usuarios[MOD] = LUCIA
    conversacion._rechazos.clear()
    api.pendientes = [
        _item("ev-1", "Rifa solidaria", "Posible fraude (0.82): IA (nim): pide Bizum por adelantado"),
        _item("ev-2", "Fiesta de la matanza", "Apelación: ya hemos puesto el lugar"),
        _item("ev-3", "Mercadillo", "Importado automáticamente (p. ej. de Facebook): lo revisa el moderador"),
    ]
    return api


def test_resumen_y_sugerencias_de_la_bandeja(bandeja):
    r = conversacion.procesar(_msg("pendientes"))
    assert r[0].startswith("Tienes 3 pendiente(s): 1 posible fraude, 1 apelación y 1 importado de Facebook.")
    assert "Empieza por el posible fraude" in r[0]
    assert "Sugerencia: rechazar" in r[1] and "segundo rechazo es definitivo" in r[2]


def test_rechazar_propone_un_motivo_amable_y_lo_envia(bandeja):
    conversacion.procesar(_msg("pendientes"))
    r = conversacion.procesar(_msg("", boton_id="mod:rechazar:ev-1"))
    assert "Voy a rechazar *Rifa solidaria*" in _texto(r) and "pagos por adelantado" in _texto(r)
    assert not any(c[1].endswith("/decision") for c in bandeja.llamadas)  # aún no ha rechazado
    r = conversacion.procesar(_msg("", boton_id="modrz_ok:ev-1"))
    assert "Rechazado" in _texto(r)
    metodo, ruta, cuerpo = [c for c in bandeja.llamadas if c[1].endswith("/decision")][-1]
    assert ruta == "/api/v1/moderacion/ev-1/decision" and cuerpo["decision"] == "rechazar"
    assert "pagos por adelantado" in cuerpo["motivo"]


def test_el_moderador_escribe_su_propio_motivo_o_se_arrepiente(bandeja):
    conversacion.procesar(_msg("pendientes"))
    conversacion.procesar(_msg("", boton_id="mod:rechazar:ev-3"))
    conversacion.procesar(_msg("", boton_id="modrz_otro:ev-3"))
    conversacion.procesar(_msg("La fecha es de 2019: no es de este año"))
    cuerpo = [c for c in bandeja.llamadas if c[1].endswith("/decision")][-1][2]
    assert cuerpo == {"decision": "rechazar", "motivo": "La fecha es de 2019: no es de este año"}
    conversacion.procesar(_msg("", boton_id="mod:rechazar:ev-2"))
    r = conversacion.procesar(_msg("", boton_id="modrz_no"))
    assert "no lo rechazo" in _texto(r)
    assert len([c for c in bandeja.llamadas if c[1].endswith("/decision")]) == 1


def test_un_vecino_no_puede_rechazar(api):
    api.caida = False
    api.usuarios[MOD] = {"id": "u9", "nombre": "Pepe", "rol": "vecino"}
    assert "solo para moderadores" in _texto(conversacion.procesar(_msg("", boton_id="mod:rechazar:ev-1")))


@pytest.mark.parametrize("motivo,tipo", [
    ("Posible fraude (0.9): x", "fraude"), ("Posible spam (0.8): x", "spam"), ("Apelación: x", "apelacion"),
    ("Posible duplicado de «X»", "duplicado"), ("Editado después de publicarse. Posible fraude (0.7): x", "fraude"),
    ("Publicación a mano: la revisa el moderador", "a_mano"), (None, "a_mano"),
])
def test_tipo_de_motivo(motivo, tipo):
    assert moderador.tipo_de(motivo) == tipo
