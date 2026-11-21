"""P5a: «Mis planes propuestos». Quien propone un plan es su dueño aunque no tenga asociación (`propuesto_por_id`):
lo ve con `GET /eventos?organizador_id=`, lo modifica con `PATCH /eventos/{id}` y nadie más lo ve."""

from app.modelos import Evento
from tests.test_eventos_privados import (
    ANTONIO_PUBLICADOR,
    CARMEN,
    LUCIA_MODERADORA,
    NUEVO,
    RUTA,
    _bearer,
)
from tests.test_importar import TOKEN, _cuerpo, api  # noqa: F401 — fixture `api` con el seed
from tests.test_publico import EVENTO, _valida

JOSE = "5a5e0000-0000-4000-8000-000000000005"
URL = "/api/v1/eventos"


def _proponer(api, quien=CARMEN, **cambios) -> dict:
    r = api.post(URL, json={**NUEVO, **cambios}, headers=_bearer(quien))
    assert r.status_code == 201, r.text
    return r.json()


def test_vecino_sin_asociacion_es_dueno_de_lo_que_propone(api):
    plan = _proponer(api)
    _valida(EVENTO, plan)
    assert plan["publicador_id"] is None and plan["propuesto_por_id"] == CARMEN

    mios = api.get(URL, params={"organizador_id": CARMEN}, headers=_bearer(CARMEN)).json()
    assert [e["id"] for e in mios["items"]] == [plan["id"]]
    assert mios["items"][0]["estado"] == "en_revision"  # salen todos los estados, no solo `publicado`

    r = api.patch(f"{URL}/{plan['id']}", json={"lugar": "Plaza de la Iglesia"}, headers=_bearer(CARMEN))
    assert r.status_code == 200, r.text
    assert r.json()["lugar"] == "Plaza de la Iglesia"


def test_nadie_mas_ve_ni_modifica_los_planes_de_otro(api):
    plan = _proponer(api)
    otro = api.get(URL, params={"organizador_id": CARMEN}, headers=_bearer(JOSE)).json()
    assert otro["items"] == [] and otro["total"] == 0
    assert api.get(URL, params={"organizador_id": CARMEN}).json()["items"] == []  # sin sesión
    r = api.patch(f"{URL}/{plan['id']}", json={"lugar": "Otro"}, headers=_bearer(JOSE))
    assert r.status_code == 403


def test_el_moderador_y_el_bot_ven_los_planes_de_un_vecino(api):
    plan = _proponer(api)
    for cabeceras in (_bearer(LUCIA_MODERADORA, "moderador"), TOKEN):
        ids = [e["id"] for e in api.get(URL, params={"organizador_id": CARMEN}, headers=cabeceras).json()["items"]]
        assert ids == [plan["id"]]


def test_asociacion_ve_los_de_su_entidad_y_filtra_por_estado(api):
    mios = api.get(URL, params={"organizador_id": ANTONIO_PUBLICADOR}, headers=_bearer(ANTONIO_PUBLICADOR, "publicador")).json()
    ids = {e["id"] for e in mios["items"]}
    assert RUTA in ids  # la II Ruta Solidaria es de Amigos de Velefique
    assert all(e["estado"] != "borrador" for e in mios["items"])
    publicados = api.get(URL, params={"organizador_id": ANTONIO_PUBLICADOR, "estado": "publicado"},
                         headers=_bearer(ANTONIO_PUBLICADOR, "publicador")).json()["items"]
    assert publicados and all(e["estado"] == "publicado" for e in publicados)


def test_lo_que_manda_un_vecino_por_el_bot_tambien_es_suyo(api, db):
    # Carmen escribe al bot desde su teléfono: no es publicador, pero el plan queda a su nombre.
    r = api.post(f"{URL}/importar", json=_cuerpo(url=None, telefono_publicador="+34600000201"), headers=TOKEN)
    assert r.status_code in (200, 201), r.text
    evento_id = r.json()["evento"]["id"] if "evento" in r.json() else r.json()["id"]
    assert db.get(Evento, evento_id).propuesto_por_id == CARMEN


def test_el_moderador_que_crea_un_plan_no_queda_como_proponente(api):
    r = api.post(URL, json=NUEVO, headers=_bearer(LUCIA_MODERADORA, "moderador"))
    assert r.status_code == 201, r.text
    assert r.json()["propuesto_por_id"] is None


def test_sin_organizador_id_la_agenda_sigue_igual(api):
    datos = api.get(URL).json()
    assert datos["items"] and all(e["estado"] == "publicado" for e in datos["items"])
