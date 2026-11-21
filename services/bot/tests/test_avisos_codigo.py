"""D1 (avisos solo a quien los acepta, también sin teléfono) y D2 (entrar con código: /start codigo)."""

import pytest
from fastapi.testclient import TestClient

from app import api_cliente, avisos, canales, conversacion, telegram
from app.main import app
from app.schemas import MensajeEntrante

CAB = {"X-Internal-Token": "test"}
CARMEN = {"id": "u-carmen", "nombre": "Carmen", "rol": "vecino", "telefono": "+34600000201"}


def _msg(texto="", de="+34600000201", **kw):
    return MensajeEntrante(canal=kw.pop("canal", "whatsapp"), de=de, texto=texto, **kw)


def _t(r) -> str:
    return " ".join(r)


@pytest.fixture
def guardados(api, monkeypatch):
    api.caida = False
    api.usuarios["+34600000201"] = CARMEN
    lista = []
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: lista.append((uid, c)) or True)
    return lista


# ---------- D1: /notify sin teléfono ----------

def test_notify_solo_con_contacto_de_telegram(monkeypatch):
    enviados = []
    monkeypatch.setattr(canales, "enviar", lambda destino, texto, botones=None, **kw: enviados.append((destino, botones)))
    r = TestClient(app).post("/notify", headers=CAB, json={
        "contacto": "tg:777", "tipo": "recomendacion", "texto": "Ruta el sábado", "evento_id": "e1"})
    assert r.status_code == 200
    assert enviados == [("tg:777", [("insc:e1", "✋ Apuntarme"), ("info:e1", "ℹ️ Más info")])]


def test_notify_sin_telefono_ni_contacto_es_422():
    r = TestClient(app).post("/notify", headers=CAB, json={"tipo": "anuncio", "texto": "Hola"})
    assert r.status_code == 422


# ---------- D1: consentimiento ----------

def test_tras_los_gustos_pregunta_y_guarda_que_acepta(guardados):
    r = conversacion.procesar(_msg("Me gustan las rutas y las fiestas"))
    assert "¿Quieres que te avise" in _t(r)
    assert canales.bandeja_consola[-1]["botones"] == avisos.BOTONES
    r = conversacion.procesar(_msg("", boton_id="avisos:si"))
    assert "Te avisaré" in _t(r)
    assert guardados[-1] == ("u-carmen", {"acepta_avisos": True})
    r = conversacion.procesar(_msg("Me gusta también el teatro"))
    assert "¿Quieres que te avise" not in _t(r)  # no insiste


def test_un_no_suelto_tras_la_pregunta_es_la_respuesta(guardados):
    conversacion.procesar(_msg("Me gustan las rutas"))
    r = conversacion.procesar(_msg("no, gracias"))
    assert "no te mandaré avisos" in _t(r) and guardados[-1][1] == {"acepta_avisos": False}


@pytest.mark.parametrize("texto,acepta", [
    ("no quiero avisos", False), ("deja de avisarme", False), ("avísame de planes nuevos", True),
    ("quiero recibir avisos", True),
])
def test_cambiar_de_idea_en_cualquier_momento(guardados, texto, acepta):
    conversacion.procesar(_msg(texto))
    assert guardados[-1] == ("u-carmen", {"acepta_avisos": acepta})


def test_un_si_cualquiera_sin_pregunta_no_activa_avisos(guardados):
    conversacion.procesar(_msg("sí"))
    assert guardados == []


def test_telegram_sin_numero_lo_pide_y_guarda_al_compartirlo(api, monkeypatch):
    api.caida = False
    guardados = []
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: guardados.append(c) or True)
    r = conversacion.procesar(_msg("avísame de planes nuevos", de="tg:42", canal="telegram"))
    assert "Compartir mi número" in _t(r) and guardados == []
    r = conversacion.procesar(_msg("", de="tg:42", canal="telegram", telefono_compartido="+34600000042"))
    assert guardados == [{"acepta_avisos": True}] and "Te avisaré" in _t(r)


# ---------- D2: /start codigo ----------

def test_start_codigo_y_start_alta_desde_la_web():
    def update(texto):
        return {"update_id": 1, "message": {"chat": {"id": 42}, "from": {"first_name": "Rosa"}, "text": texto}}
    assert telegram.parsear(update("/start codigo"))[0].texto == "/codigo"
    assert telegram.parsear(update("/start alta"))[0].texto == "quiero dar de alta mi asociación"
    assert telegram.parsear(update("/start"))[0].texto == "hola"
    assert telegram.parsear(update("/start otracosa"))[0].texto == "hola"


def test_codigo_pide_el_numero_y_luego_manda_a_la_web(api):
    api.caida = False
    r = conversacion.procesar(_msg("/codigo", de="tg:43", canal="telegram"))
    assert "Compartir mi número" in _t(r) and canales.bandeja_consola[-1]["pedir_contacto"]
    r = conversacion.procesar(_msg("", de="tg:43", canal="telegram", telefono_compartido="+34600000043"))
    assert "Pedir el código" in _t(r)


def test_codigo_con_el_numero_ya_compartido(api):
    api.caida = False
    api.usuarios["tg:44"] = {"id": "u44", "rol": "vecino", "telefono": "+34600000044"}
    r = conversacion.procesar(_msg("/codigo", de="tg:44", canal="telegram"))
    assert "Pedir el código" in _t(r)


def test_whatsapp_nueva_se_da_de_alta_para_guardar_los_avisos(api, monkeypatch):
    """Por WhatsApp el contacto ya es su teléfono: si aún no existe, se le da de alta y se guarda."""
    api.caida = False
    guardados = []
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: guardados.append((uid, c)) or True)
    r = conversacion.procesar(_msg("avísame de planes nuevos", de="+34611000111"))
    assert "Te avisaré" in _t(r)
    assert guardados and guardados[-1][1] == {"acepta_avisos": True}
    assert api.usuarios["+34611000111"]["telefono"] == "+34611000111"


def test_simulador_acepta_botones():
    r = TestClient(app).post("/dev/mensaje", json={"de": "+34600000301", "boton_id": "insc_ok"})
    assert r.status_code == 200 and "Nos vemos" in " ".join(r.json()["respuestas"])


def test_los_gustos_de_una_vecina_nueva_llegan_a_la_api(api, monkeypatch):
    """Sin esto, los avisos de planes nuevos (la API filtra por gustos) nunca le llegarían."""
    api.caida = False
    guardados = []
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: guardados.append(c) or True)
    conversacion.procesar(_msg("Me gustan las rutas", de="+34611000333"))
    assert api.usuarios["+34611000333"]  # dada de alta al decir sus gustos
    assert any(c.get("gustos") == ["deportiva"] for c in guardados)


def test_en_telegram_los_gustos_suben_al_compartir_el_numero(api, monkeypatch):
    api.caida = False
    guardados = []
    monkeypatch.setattr(api_cliente, "guardar_preferencias", lambda uid, c: guardados.append(c) or True)
    conversacion.procesar(_msg("Me gustan las rutas", de="tg:77", canal="telegram"))
    assert guardados == []  # aún no sabemos quién es
    conversacion.procesar(_msg("", de="tg:77", canal="telegram", telefono_compartido="+34600000077"))
    assert any(c.get("gustos") == ["deportiva"] for c in guardados)
