"""Tareas programadas: recordatorio 24 h antes, «¿qué tal fue?» y resumen semanal (app/tareas_programadas.py)."""

from datetime import timedelta

import httpx
import pytest
from sqlalchemy.orm import sessionmaker

from app import notificaciones, tareas_programadas as tareas
from app.config import get_settings
from app.modelos import Evento, Inscripcion, Usuario
from app.seed import sembrar
from tests.test_importar import VIERNES
from tests.test_notificaciones import Bot

AHORA = VIERNES  # viernes 20/11, 19:00 en Madrid


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setenv("BOT_URL", "http://bot-falso:8001")
    get_settings.cache_clear()
    b = Bot()
    monkeypatch.setattr(notificaciones, "_transporte", httpx.MockTransport(b))
    yield b
    get_settings.cache_clear()


@pytest.fixture
def base(db):
    sembrar(db, ahora=AHORA)
    db.commit()
    return db


def _vecina(db, nombre, **extra) -> Usuario:
    u = Usuario(nombre=nombre, **({"telegram_id": str(abs(hash(nombre)) % 10**9)} | extra))
    db.add(u)
    db.commit()
    return u


def _plan(db, titulo, inicio, municipio="Senés", estado="publicado", **extra) -> Evento:
    ev = Evento(titulo=titulo, categoria="cultural", municipio=municipio, fecha_inicio=inicio, estado=estado,
                **({"lat": 37.18, "lon": -2.36} | extra))
    db.add(ev)
    db.commit()
    return ev


def _apuntar(db, usuario, evento, estado="confirmada"):
    db.add(Inscripcion(evento_id=evento.id, usuario_id=usuario.id, plazas=1, estado=estado, canal="telegram"))
    db.commit()


def test_recordatorio_24_horas_antes_una_sola_vez(base):
    ana, beto = _vecina(base, "Ana"), _vecina(base, "Beto")
    manana = _plan(base, "Taller de esparto", AHORA + timedelta(hours=24), lugar="Centro social")
    lejano = _plan(base, "Concierto", AHORA + timedelta(days=5))
    _apuntar(base, ana, manana)
    _apuntar(base, beto, manana, estado="lista_espera")  # sin plaza: no se le recuerda
    _apuntar(base, ana, lejano)
    avisos = tareas.recordatorios(base, AHORA)
    base.commit()
    assert [(n.usuario_id, n.evento_id) for n in avisos] == [(ana.id, manana.id)]
    assert avisos[0].tipo == "anuncio" and avisos[0].texto.startswith("⏰ Mañana a las ")
    assert "«Taller de esparto» en Senés (Centro social)" in avisos[0].texto
    assert tareas.recordatorios(base, AHORA + timedelta(minutes=10)) == []  # no se repite


def test_que_tal_fue_al_terminar(base):
    ana, beto = _vecina(base, "Ana"), _vecina(base, "Beto")
    recien = _plan(base, "Ruta corta", AHORA - timedelta(hours=5))  # sin fecha_fin: terminó hace 2 h
    viejo = _plan(base, "Fiesta", AHORA - timedelta(days=3), estado="finalizado")
    en_curso = _plan(base, "Mercado", AHORA - timedelta(hours=1), fecha_fin=AHORA + timedelta(hours=3))
    _apuntar(base, ana, recien, estado="asistio")
    _apuntar(base, beto, recien, estado="cancelada")
    for ev in (viejo, en_curso):
        _apuntar(base, ana, ev)
    avisos = tareas.que_tal_fue(base, AHORA)
    base.commit()
    assert [(n.usuario_id, n.evento_id) for n in avisos] == [(ana.id, recien.id)]
    assert avisos[0].texto.startswith(tareas.MARCA_QUE_TAL)
    assert tareas.que_tal_fue(base, AHORA) == []


def test_resumen_semanal_por_pueblo_solo_a_quien_acepta_y_una_vez(base, monkeypatch):
    monkeypatch.setenv("RESUMEN_DIA_SEMANA", "4")  # viernes
    monkeypatch.setenv("RESUMEN_HORA", "18")
    get_settings.cache_clear()
    ana = _vecina(base, "Ana", municipio="Tahal", acepta_avisos=True)
    beto = _vecina(base, "Beto", municipio="Tahal")  # no ha aceptado avisos (D1)
    _plan(base, "Verbena de Tahal", AHORA + timedelta(days=2), municipio="Tahal", lat=37.2, lon=-2.29)
    avisos = tareas.resumen_semanal(base, AHORA)
    base.commit()
    mios = [n for n in avisos if n.usuario_id in (ana.id, beto.id)]
    assert [n.usuario_id for n in mios] == [ana.id]
    assert mios[0].tipo == "recomendacion" and mios[0].texto.startswith("📅 Esta semana en Tahal")
    assert "Verbena de Tahal (Tahal)" in mios[0].texto
    assert all(n.usuario_id != ana.id for n in tareas.resumen_semanal(base, AHORA + timedelta(hours=2)))
    get_settings.cache_clear()


def test_resumen_no_sale_otro_dia(base, monkeypatch):
    monkeypatch.setenv("RESUMEN_DIA_SEMANA", "0")  # lunes; hoy es viernes
    get_settings.cache_clear()
    _vecina(base, "Ana", municipio="Tahal", acepta_avisos=True)
    assert tareas.resumen_semanal(base, AHORA) == []
    get_settings.cache_clear()


def test_ciclo_crea_y_envia_al_bot(base, motor, bot):
    ana = _vecina(base, "Ana")
    _apuntar(base, ana, _plan(base, "Taller", AHORA + timedelta(hours=23)))
    enviados = tareas.ciclo_tareas(sessionmaker(bind=motor, expire_on_commit=False), ahora=AHORA)
    assert enviados >= 1
    cuerpo = next(c for c in bot.cuerpos() if c.get("texto", "").startswith("⏰"))
    assert cuerpo["contacto"] == f"tg:{ana.telegram_id}" and cuerpo["tipo"] == "anuncio"


# --- Idea 7: «quedan pocas plazas» -------------------------------------------------------------------------------

def test_quedan_pocas_plazas_a_quien_le_interesa_y_no_esta_apuntado(base):
    ana = _vecina(base, "Ana", municipio="Senés", acepta_avisos=True, gustos=["cultural"])
    beto = _vecina(base, "Beto", municipio="Senés", gustos=["cultural"])  # no acepta avisos
    carla = _vecina(base, "Carla", municipio="Senés", acepta_avisos=True, gustos=["cultural"])
    taller = _plan(base, "Taller de esparto", AHORA + timedelta(days=3), plazas_totales=15, plazas_libres=2)
    _plan(base, "Concierto", AHORA + timedelta(days=3), plazas_totales=100, plazas_libres=60)  # aún hay sitio
    _apuntar(base, carla, taller)
    avisos = [n for n in tareas.pocas_plazas(base, AHORA) if n.usuario_id in (ana.id, beto.id, carla.id)]
    base.commit()
    assert [n.usuario_id for n in avisos] == [ana.id]
    assert avisos[0].tipo == "recomendacion" and avisos[0].evento_id == taller.id
    assert avisos[0].texto.startswith("⏳ Quedan 2 plazas para «Taller de esparto» en Senés")
    # Una sola vez por persona y plan
    assert all(n.usuario_id != ana.id for n in tareas.pocas_plazas(base, AHORA + timedelta(hours=1)))


def test_pocas_plazas_no_avisa_de_planes_llenos_ni_lejanos(base):
    ana = _vecina(base, "Ana", municipio="Senés", acepta_avisos=True, gustos=["cultural"])
    _plan(base, "Lleno", AHORA + timedelta(days=3), plazas_totales=10, plazas_libres=0)
    _plan(base, "Dentro de un mes", AHORA + timedelta(days=30), plazas_totales=10, plazas_libres=1)
    _plan(base, "Sin aforo", AHORA + timedelta(days=3))
    assert all(n.usuario_id != ana.id for n in tareas.pocas_plazas(base, AHORA))
