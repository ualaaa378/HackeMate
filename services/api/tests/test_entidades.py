"""Solo ayuntamientos como entidades publicadoras (app/entidades.py, SOLO_AYUNTAMIENTOS=true)."""

import pytest
from sqlalchemy import select

from app.canales import buscar_publicador_por_contacto
from app.config import get_settings
from app.modelos import Evento, Fuente, Publicador, Usuario
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import TOKEN, VIERNES, _error

ANTONIO = "5a5e0000-0000-4000-8000-000000000003"  # era el organizador de «Amigos de Velefique»
AMIGOS_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"
AYTO_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a10"


@pytest.fixture
def solo_aytos(monkeypatch):
    monkeypatch.setenv("SOLO_AYUNTAMIENTOS", "true")
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _tipos(db) -> set[str]:
    return set(db.scalars(select(Publicador.tipo)).all())


def test_el_seed_solo_carga_ayuntamientos_y_les_pasa_lo_de_las_demas(db, solo_aytos):
    sembrar(db, ahora=VIERNES)
    db.commit()
    assert _tipos(db) == {"ayuntamiento"}
    assert db.get(Publicador, AMIGOS_VELEFIQUE) is None
    ayto = db.get(Publicador, AYTO_VELEFIQUE)
    assert ayto.usuario_id == ANTONIO and db.get(Usuario, ANTONIO).publicador_id == AYTO_VELEFIQUE
    assert ayto.nivel_confianza == 0  # Antonio publicaba a mano: sus planes siguen yendo a la bandeja
    # Ningún plan se queda colgando de una entidad borrada
    ids = set(db.scalars(select(Publicador.id)).all())
    assert all(e.publicador_id in ids or e.publicador_id is None for e in db.scalars(select(Evento)).all())
    assert db.scalar(select(Evento).where(Evento.publicador_id == AYTO_VELEFIQUE)) is not None
    # Se puede volver a sembrar (como al arrancar el contenedor) sin que vuelvan ni choquen
    sembrar(db, ahora=VIERNES, sobrescribir=False)
    db.commit()
    assert _tipos(db) == {"ayuntamiento"}


def test_depura_lo_que_ya_estaba_en_la_base(db, monkeypatch):
    sembrar(db, ahora=VIERNES)  # SOLO_AYUNTAMIENTOS=false: como la base de antes del cambio
    db.commit()
    planes_amigos = db.scalars(select(Evento.id).where(Evento.publicador_id == AMIGOS_VELEFIQUE)).all()
    fuentes_amigos = db.scalars(select(Fuente.id).where(Fuente.publicador_id == AMIGOS_VELEFIQUE)).all()
    db.get(Publicador, AMIGOS_VELEFIQUE).telegram_id = "999"
    db.add(Publicador(nombre="Peña nueva", tipo="asociacion", municipio="Velefique", telefono="+34600000999"))
    db.commit()
    assert planes_amigos
    monkeypatch.setenv("SOLO_AYUNTAMIENTOS", "true")
    get_settings.cache_clear()
    try:
        resumen = sembrar(db, ahora=VIERNES, sobrescribir=False)
        db.commit()
    finally:
        get_settings.cache_clear()
    assert resumen["entidades_no_ayuntamiento_borradas"] >= 6 and _tipos(db) == {"ayuntamiento"}
    db.expire_all()
    assert {db.get(Evento, i).publicador_id for i in planes_amigos} == {AYTO_VELEFIQUE}
    assert {db.get(Fuente, i).publicador_id for i in fuentes_amigos} == {AYTO_VELEFIQUE}
    ayto = db.get(Publicador, AYTO_VELEFIQUE)
    assert ayto.usuario_id == ANTONIO and ayto.telegram_id == "999" and ayto.nivel_confianza == 0
    # Antonio sigue publicando por el bot: ahora en nombre del ayuntamiento
    antonio = db.get(Usuario, ANTONIO)
    assert buscar_publicador_por_contacto(db, antonio.telefono).id == AYTO_VELEFIQUE


def test_el_alta_solo_admite_ayuntamientos(cliente, db, solo_aytos):
    sembrar(db, ahora=VIERNES)
    db.commit()
    cuerpo = {"nombre": "Club de Petanca", "tipo": "asociacion", "municipio": "Tahal", "telefono": "+34600000611"}
    _error(cliente.post("/api/v1/publicadores", json=cuerpo, headers=TOKEN), 422, "solo_ayuntamientos")
    r = cliente.post("/api/v1/publicadores", json=cuerpo | {"nombre": "Ayuntamiento de Tahal", "tipo": "ayuntamiento"},
                     headers=TOKEN)
    assert r.status_code == 201 and r.json()["estado"] == "solicitado"


def test_alta_desde_la_web_con_el_telefono_de_la_cuenta(cliente, db, solo_aytos):
    sembrar(db, ahora=VIERNES)
    u = Usuario(nombre="Marta", telefono="+34600000612", whatsapp_verificado=True)
    db.add(u)
    db.commit()
    sesion = {"Authorization": f"Bearer {emitir_jwt(u.id, 'vecino')}"}
    cuerpo = {"nombre": "Ayuntamiento de Senés", "tipo": "ayuntamiento", "municipio": "Senés",
              "responsable": {"nombre": "Marta López", "dni": "12345678Z", "residencia": "Senés"}}
    _error(cliente.post("/api/v1/publicadores", json=cuerpo | {"telefono": "+34600000613"}, headers=sesion),
           403, "prohibido")
    r = cliente.post("/api/v1/publicadores", json=cuerpo | {"telefono": "+34600000612"}, headers=sesion)
    assert r.status_code == 201, r.text
    assert db.get(Publicador, r.json()["id"]).usuario_id == u.id
    _error(cliente.post("/api/v1/publicadores", json=cuerpo | {"telefono": "+34600000612"}), 401, "no_autenticado")
