"""Choque de fechas (app/choques.py, GET /api/v1/choques)."""

from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from app.choques import choques
from app.modelos import Evento
from app.seed import sembrar
from tests.test_importar import VIERNES, _error

TZ = ZoneInfo("Europe/Madrid")


def _plan(db, titulo, inicio, municipio, estado="publicado"):
    e = Evento(titulo=titulo, categoria="cultural", municipio=municipio, fecha_inicio=inicio, estado=estado,
               lat=37.18, lon=-2.36)
    db.add(e)
    db.commit()
    return e


def _sabado_que_viene() -> datetime:
    """Un sábado dentro de un año: lejos de los planes de los fixtures."""
    dia = datetime.now(TZ).replace(hour=18, minute=0, second=0, microsecond=0) + timedelta(days=365)
    return dia + timedelta(days=(5 - dia.weekday()) % 7)


def test_choque_el_mismo_dia_cerca_y_propone_otro_fin_de_semana(db):
    sembrar(db, ahora=VIERNES)
    sabado = _sabado_que_viene()
    otro = _plan(db, "Verbena", sabado.replace(hour=22), "Senés")
    _plan(db, "Borrador", sabado, "Tahal", estado="borrador")  # no cuenta
    r = choques(db, sabado, "Tahal")
    assert [c["evento_id"] for c in r["choques"]] == [otro.id]
    assert 0 < r["choques"][0]["distancia_km"] <= 20
    assert r["alternativas"]
    for iso in r["alternativas"]:
        d = datetime.fromisoformat(iso).astimezone(TZ)
        assert d.weekday() >= 5 and (d.hour, d.minute) == (18, 0) and d.date() != sabado.date()


def test_sin_choque_y_excluir_el_propio_plan(db):
    sembrar(db, ahora=VIERNES)
    sabado = _sabado_que_viene()
    propio = _plan(db, "Mi plan", sabado, "Tahal")
    assert choques(db, sabado, "Tahal", excluir=propio.id) == {"choques": [], "alternativas": []}


def test_ruta_publica(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    sabado = _sabado_que_viene()
    r = cliente.get("/api/v1/choques", params={"fecha_inicio": sabado.isoformat(), "municipio": "Senés"})
    assert r.status_code == 200 and set(r.json()) == {"choques", "alternativas"}
    _error(cliente.get("/api/v1/choques", params={"fecha_inicio": "mañana", "municipio": "Senés"}), 422, "validacion")
    _error(cliente.get("/api/v1/choques", params={"fecha_inicio": sabado.isoformat(), "municipio": "Madrid"}),
           422, "municipio_no_encontrado")
