"""D1: avisos de planes nuevos (A10) solo a quien los acepta (A8) y por su Telegram aunque no tenga teléfono (A9)."""

from datetime import datetime, timezone

import pytest
from sqlalchemy import select

from app import notificaciones
from app.avisos_planes import avisar_interesados
from app.config import get_settings
from app.modelos import Evento, Inscripcion, Notificacion, Usuario
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import VIERNES
from tests.test_notificaciones import Bot

import httpx

CARMEN = "5a5e0000-0000-4000-8000-000000000001"  # fixtures: Senés, le gusta el deporte, acepta avisos
LUCIA_MODERADORA = "5a5e0000-0000-4000-8000-000000000002"
PASADO = datetime(2026, 10, 3, 17, 0, tzinfo=timezone.utc)
LIGA = {
    "titulo": "II Liga de futbolín de Senés",
    "descripcion": "Por parejas, en el bar de la plaza.",
    "categoria": "deportiva",
    "etiquetas": ["futbolín"],
    "municipio": "Senés",
    "fecha_inicio": "2026-12-14T17:00:00+01:00",
}


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setenv("BOT_URL", "http://bot-falso:8001")
    get_settings.cache_clear()
    b = Bot()
    monkeypatch.setattr(notificaciones, "_transporte", httpx.MockTransport(b))
    yield b
    get_settings.cache_clear()


@pytest.fixture
def api(cliente, db, bot):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


def _vecina(db, nombre, **extra) -> Usuario:
    u = Usuario(nombre=nombre, **({"municipio": "Senés"} | extra))
    db.add(u)
    db.commit()
    return u


def _fue_a_la_primera_liga(db, usuario: Usuario) -> None:
    """La I Liga de futbolín (octubre): la IA la clasificó como «ludica», no como deporte."""
    liga = Evento(titulo="I Liga de futbolín", categoria="ludica", etiquetas=["futbolin"], municipio="Senés",
                  lat=37.18, lon=-2.36, fecha_inicio=PASADO, estado="finalizado")
    db.add(liga)
    db.flush()
    db.add(Inscripcion(evento_id=liga.id, usuario_id=usuario.id, plazas=1, estado="asistio", canal="telegram"))
    db.commit()


def _publicar_como_moderador(api, cuerpo=LIGA) -> dict:
    r = api.post("/api/v1/eventos", json=cuerpo,
                 headers={"Authorization": f"Bearer {emitir_jwt(LUCIA_MODERADORA, 'moderador')}"})
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "publicado"
    return r.json()


def _avisos(db, evento_id) -> dict[str, Notificacion]:
    db.expire_all()
    filas = db.scalars(select(Notificacion).where(Notificacion.evento_id == evento_id,
                                                  Notificacion.tipo == "recomendacion")).all()
    return {n.usuario_id: n for n in filas}


def test_a8_acepta_avisos_es_falso_por_defecto(db):
    assert _vecina(db, "Nueva", municipio=None).acepta_avisos is False


def test_quien_fue_a_una_liga_de_futbolin_se_entera_de_la_siguiente(api, db, bot):
    ana = _vecina(db, "Ana", telegram_id="501", acepta_avisos=True)  # solo Telegram, sin teléfono (A9)
    _fue_a_la_primera_liga(db, ana)
    beto = _vecina(db, "Beto", telefono="+34600000777", gustos=["deportiva"])  # no ha aceptado avisos (A8)
    lejos = _vecina(db, "Lejos", telefono="+34600000778", gustos=["deportiva"], acepta_avisos=True, municipio=None,
                    lat=40.42, lon=-3.70, radio_km=20)  # vive en Madrid
    nada = _vecina(db, "Nada", telefono="+34600000779", gustos=["gastronomia"], acepta_avisos=True)

    evento = _publicar_como_moderador(api)
    avisos = _avisos(db, evento["id"])

    assert ana.id in avisos and CARMEN in avisos  # Ana por su historial (etiqueta), Carmen por sus gustos
    assert {beto.id, lejos.id, nada.id}.isdisjoint(avisos)
    aviso_ana = avisos[ana.id]
    assert aviso_ana.estado_envio == "enviada" and aviso_ana.contacto == "tg:501" and aviso_ana.telefono is None
    assert "II Liga de futbolín de Senés" in aviso_ana.texto and "lunes 14/12 a las 17:00" in aviso_ana.texto
    assert "ya te has apuntado a otros planes de «futbolín»" in aviso_ana.texto
    cuerpo = next(c for c in bot.cuerpos() if c.get("contacto") == "tg:501")
    assert cuerpo["tipo"] == "recomendacion" and cuerpo["evento_id"] == evento["id"]

    # Como mucho un aviso por persona y plan
    assert avisar_interesados(db, db.get(Evento, evento["id"])) == []


def test_al_aprobar_desde_la_bandeja_tambien_avisa(api, db):
    ana = _vecina(db, "Ana", telegram_id="502", acepta_avisos=True, gustos=["deportiva"])
    from tests.test_importar import _extraccion, TOKEN

    extraccion = _extraccion()
    extraccion["campos"]["titulo"]["valor"] = "Torneo de pádel"
    extraccion["campos"]["municipio"]["valor"] = "Senés"
    extraccion["campos"]["fecha_inicio"]["valor"] = "2026-12-20T10:00:00+01:00"
    r = api.post("/api/v1/eventos/importar", headers=TOKEN, json={
        "extraccion": extraccion, "origen": {"canal": "facebook", "url": "https://fb/p/9", "importado_auto": True}})
    evento_id = r.json()["evento"]["id"]
    r = api.post(f"/api/v1/eventos/{evento_id}/confirmar", headers=TOKEN, json={"campos": {}})
    assert r.json()["evento"]["estado"] == "en_revision"
    assert _avisos(db, evento_id) == {}  # en la bandeja aún no se avisa a nadie

    r = api.post(f"/api/v1/moderacion/{evento_id}/decision", json={"decision": "aprobar", "motivo": None},
                 headers={"Authorization": f"Bearer {emitir_jwt(LUCIA_MODERADORA, 'moderador')}"})
    assert r.status_code == 200, r.text
    assert ana.id in _avisos(db, evento_id)


def test_ya_apuntada_o_quien_publica_no_reciben_aviso(api, db):
    ana = _vecina(db, "Ana", telegram_id="503", acepta_avisos=True, gustos=["deportiva"])
    evento = _publicar_como_moderador(api, LIGA | {"titulo": "Carrera popular"})
    assert ana.id in _avisos(db, evento["id"])
    db.add(Inscripcion(evento_id=evento["id"], usuario_id=ana.id, plazas=1, estado="confirmada", canal="web"))
    db.query(Notificacion).filter(Notificacion.usuario_id == ana.id).delete()
    db.commit()
    assert all(n.usuario_id != ana.id for n in avisar_interesados(db, db.get(Evento, evento["id"])))


def test_recomendacion_a_quien_no_acepta_no_sale(db, bot):
    beto = _vecina(db, "Beto", telefono="+34600000777", municipio=None)
    n = notificaciones.notificar(db, tipo="recomendacion", texto="Plan", usuario=beto)
    assert n.estado_envio == "fallida" and n.ultimo_error == "no acepta avisos" and not bot.recibidas
    # Los avisos de un plan al que ya está apuntado (cambio de hora…) salen igual
    assert notificaciones.notificar(db, tipo="cambio_evento", texto="Cambio", usuario=beto).estado_envio == "enviada"
