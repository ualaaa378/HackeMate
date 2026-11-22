"""«Me gusta» en los planes: cualquiera lo ve, solo con cuenta se da o se quita."""

from datetime import timedelta

import pytest

from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import VIERNES
from tests.test_tareas_programadas import _plan, _vecina


@pytest.fixture
def base(db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return db


def _sesion(usuario):
    return {"Authorization": f"Bearer {emitir_jwt(usuario.id, "vecino")}"}


def test_me_gusta_solo_con_cuenta(cliente, base):
    plan = _plan(base, "Feria de Tahal", VIERNES + timedelta(days=2), municipio="Tahal")
    ana = _vecina(base, "Ana")
    beto = _vecina(base, "Beto")
    base.commit()
    url = f"/api/v1/eventos/{plan.id}/me-gusta"

    assert cliente.get(url).json() == {"total": 0, "mio": False}
    assert cliente.put(url).status_code == 401

    assert cliente.put(url, headers=_sesion(ana)).json() == {"total": 1, "mio": True}
    assert cliente.put(url, headers=_sesion(ana)).json() == {"total": 1, "mio": True}  # no suma dos veces
    assert cliente.put(url, headers=_sesion(beto)).json() == {"total": 2, "mio": True}
    assert cliente.get(url).json() == {"total": 2, "mio": False}
    assert cliente.get(url, headers=_sesion(ana)).json() == {"total": 2, "mio": True}

    assert cliente.delete(url, headers=_sesion(ana)).json() == {"total": 1, "mio": False}
    assert cliente.delete(url).status_code == 401


def test_me_gusta_de_un_plan_que_no_existe(cliente):
    assert cliente.get("/api/v1/eventos/no-existe/me-gusta").status_code == 404
