"""Compartir coche (app/coche.py): propuesta por la tarea programada y doble consentimiento."""

from datetime import timedelta

import pytest

from app import coche, tareas_programadas as tareas
from app.config import get_settings
from app.modelos import CocheCompartido, Notificacion
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import TOKEN, VIERNES, _error
from tests.test_tareas_programadas import _apuntar, _plan, _vecina

AHORA = VIERNES


@pytest.fixture
def base(db):
    sembrar(db, ahora=AHORA)
    db.commit()
    return db


@pytest.fixture
def api(cliente, base, monkeypatch):
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    yield cliente
    get_settings.cache_clear()


def _escena(db, inicio=None):
    """Plan en Tahal; Ana y Beto de Senés, Carla de Tahal, Dani de Senés en lista de espera."""
    plan = _plan(db, "Feria de Tahal", inicio or AHORA + timedelta(days=2), municipio="Tahal")
    ana = _vecina(db, "Ana", municipio="Senés", telefono="+34600000001")
    beto = _vecina(db, "Beto", municipio="Senés", telefono="+34600000002")
    carla = _vecina(db, "Carla", municipio="Tahal")
    dani = _vecina(db, "Dani", municipio="Senés")
    for u in (ana, beto, carla):
        _apuntar(db, u, plan)
    _apuntar(db, dani, plan, estado="lista_espera")
    return plan, ana, beto, carla, dani


def test_propone_a_los_del_mismo_pueblo_una_sola_vez(base):
    plan, ana, beto, carla, dani = _escena(base)
    avisos = coche.proponer(base, AHORA)
    base.commit()
    assert sorted(n.usuario_id for n in avisos) == sorted([ana.id, beto.id])  # ni Carla (es de Tahal) ni Dani (espera)
    assert all(n.texto.startswith(coche.MARCA_COCHE) and n.evento_id == plan.id and n.tipo == "anuncio" for n in avisos)
    assert "otro vecino de Senés" in avisos[0].texto and "+34" not in avisos[0].texto  # sin contacto todavía
    assert coche.proponer(base, AHORA + timedelta(minutes=10)) == []


def test_solo_uno_del_pueblo_no_propone(base):
    plan = _plan(base, "Feria", AHORA + timedelta(days=2), municipio="Tahal")
    _apuntar(base, _vecina(base, "Ana", municipio="Senés"), plan)
    assert coche.proponer(base, AHORA) == []


def test_planes_lejanos_o_inminentes_no(base):
    _escena(base, inicio=AHORA + timedelta(days=9))
    assert coche.proponer(base, AHORA) == []


def test_la_tarea_programada_lo_incluye(base, motor):
    from sqlalchemy.orm import sessionmaker

    _escena(base)
    tareas.ciclo_tareas(sessionmaker(bind=motor, expire_on_commit=False), ahora=AHORA)
    base.expire_all()
    assert base.query(CocheCompartido).count() == 2


def test_doble_consentimiento(api, base):
    plan, ana, beto, carla, dani = _escena(base)
    url = f"/api/v1/eventos/{plan.id}/coche"
    r = api.post(url, json={"usuario_id": ana.id, "acepta": True}, headers=TOKEN)
    assert r.status_code == 200, r.text
    assert r.json() == {"respuesta": "si", "companeros": []}  # Beto aún no ha dicho nada: ni su contacto
    # Beto responde con su propia sesión: recibe el contacto de Ana y Ana recibe el suyo
    r = api.post(url, json={"acepta": True}, headers={"Authorization": f"Bearer {emitir_jwt(beto.id, 'vecino')}"})
    assert r.json() == {"respuesta": "si", "companeros": ["Ana (+34600000001)"]}
    base.expire_all()
    aviso = base.query(Notificacion).filter_by(usuario_id=ana.id, evento_id=plan.id).one()
    assert aviso.texto.startswith(coche.MARCA_COCHE_HECHO) and "Beto (+34600000002)" in aviso.texto
    assert not aviso.texto.startswith(coche.MARCA_COCHE)  # el bot no le pone otra vez los botones de sí/no


def test_quien_dice_que_no_no_aparece(api, base):
    plan, ana, beto, *_ = _escena(base)
    url = f"/api/v1/eventos/{plan.id}/coche"
    assert api.post(url, json={"usuario_id": ana.id, "acepta": False}, headers=TOKEN).json()["respuesta"] == "no"
    r = api.post(url, json={"usuario_id": beto.id, "acepta": True}, headers=TOKEN)
    assert r.json()["companeros"] == []
    base.expire_all()
    assert base.query(Notificacion).filter_by(usuario_id=ana.id).count() == 0


def test_no_disponible_y_permisos(api, base):
    plan, ana, beto, carla, dani = _escena(base)
    url = f"/api/v1/eventos/{plan.id}/coche"
    _error(api.post(url, json={"usuario_id": carla.id, "acepta": True}, headers=TOKEN), 409, "coche_no_disponible")
    _error(api.post(url, json={"usuario_id": dani.id, "acepta": True}, headers=TOKEN), 409, "coche_no_disponible")
    _error(api.post(url, json={"acepta": True}, headers=TOKEN), 422, "falta_usuario_id")
    otro = {"Authorization": f"Bearer {emitir_jwt(beto.id, 'vecino')}"}
    _error(api.post(url, json={"usuario_id": ana.id, "acepta": True}, headers=otro), 403, "prohibido")
    _error(api.post(url, json={"usuario_id": ana.id, "acepta": True}), 401, "no_autenticado")
