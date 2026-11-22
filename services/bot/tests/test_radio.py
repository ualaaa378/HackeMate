"""«La radio del pueblo»: el resumen del lunes llega también como nota de voz con guion de locutor."""

from fastapi.testclient import TestClient

from app import canales, radio
from app.agentes import voz
from app.main import app
from tests.test_avisos_codigo import CAB

RESUMEN = ("📅 Esta semana en Senés y alrededores:\n• Sábado 28/11 17:00 · Taller de esparto (Senés)\n"
           "• Domingo 29/11 10:00 · Ruta de la Molatica (Velefique)\nSi te apetece alguno, dímelo y te apunto.")


def test_plantilla_sin_ia_lee_los_planes_como_un_locutor():
    g = radio._plantilla(RESUMEN)
    assert g.startswith("¡Buenos días") and "La radio del pueblo" in g
    assert "Taller de esparto (Senés)" in g and "Ruta de la Molatica" in g and "•" not in g


def test_el_resumen_llega_en_texto_y_en_voz(monkeypatch):
    textos, voces, guiones = [], [], []
    monkeypatch.setattr(canales, "enviar", lambda d, t, botones=None, **kw: textos.append(t))
    monkeypatch.setattr(canales, "enviar_voz", lambda d, ogg: voces.append((d, ogg)) or True)
    monkeypatch.setattr(voz, "sintetizar", lambda t: guiones.append(t) or b"OggS-radio")
    r = TestClient(app).post("/notify", headers=CAB, json={"contacto": "tg:5", "tipo": "recomendacion",
                                                           "texto": RESUMEN})
    assert r.status_code == 200
    assert textos == [RESUMEN] and voces == [("tg:5", b"OggS-radio")]
    assert "radio del pueblo" in guiones[0].lower()


def test_si_la_voz_falla_se_queda_el_texto(monkeypatch):
    textos, voces = [], []
    monkeypatch.setattr(canales, "enviar", lambda d, t, botones=None, **kw: textos.append(t))
    monkeypatch.setattr(canales, "enviar_voz", lambda d, ogg: voces.append(ogg) or True)
    monkeypatch.setattr(voz, "sintetizar", lambda t: None)
    TestClient(app).post("/notify", headers=CAB, json={"contacto": "tg:5", "tipo": "recomendacion", "texto": RESUMEN})
    assert textos == [RESUMEN] and voces == []


def test_otros_avisos_no_van_a_la_radio(monkeypatch):
    voces = []
    monkeypatch.setattr(canales, "enviar", lambda d, t, botones=None, **kw: None)
    monkeypatch.setattr(canales, "enviar_voz", lambda d, ogg: voces.append(ogg) or True)
    monkeypatch.setattr(voz, "sintetizar", lambda t: b"OggS")
    TestClient(app).post("/notify", headers=CAB, json={"contacto": "tg:5", "tipo": "anuncio", "texto": "⏰ Mañana…"})
    assert voces == []
