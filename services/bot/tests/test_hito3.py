"""Hito 3: la vecina busca planes, dice sus gustos, se apunta con un botón, pregunta por un
evento y recibe avisos. También por nota de voz."""

from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

import pytest
from fastapi.testclient import TestClient

from app import canales, conversacion, telegram, vecino
from app.agentes import asistente, busqueda, intencion, medios, preferencias
from app.main import app
from app.schemas import MensajeEntrante

cliente = TestClient(app)
TZ = ZoneInfo("Europe/Madrid")


def _msg(texto="", de="+34600000201", **kw):
    return MensajeEntrante(canal=kw.pop("canal", "whatsapp"), de=de, texto=texto, **kw)


def _ev(id_, titulo, municipio, categoria, dias, **kw):
    fecha = (datetime.now(TZ) + timedelta(days=dias)).replace(hour=11, minute=0, second=0, microsecond=0)
    return {"id": id_, "titulo": titulo, "municipio": municipio, "categoria": categoria,
            "fecha_inicio": fecha.isoformat(), "lugar": "Plaza", "es_gratuito": False, "precio_eur": 5.0,
            "plazas_libres": 10, "descripcion": "Ruta de 12 km. Salida desde la plaza.", **kw}


CARMEN = {"id": "u-carmen", "nombre": "Carmen", "rol": "vecino", "telefono": "+34600000201"}


@pytest.fixture
def agenda(api):
    api.caida = False
    api.agenda = [
        _ev("e1", "Ruta por la sierra", "Velefique", "deportiva", 2),
        _ev("e2", "Migas solidarias", "Senés", "gastronomia", 3),
        _ev("e3", "Teatro", "Uleila del Campo", "cultural", 4),
        _ev("e4", "Fiesta de la matanza", "Tahal", "fiestas", 20),
    ]
    api.usuarios["+34600000201"] = CARMEN
    return api


# ---------- Intención ----------

@pytest.mark.parametrize("texto,tipo", [
    ("¿Qué hay este finde?", "buscar"),
    ("que hay en Senés", "buscar"),
    ("Me gustan las rutas y las fiestas", "gustos"),
    ("apúntame", "inscribir"),
    ("Ruta solidaria el 30 de noviembre a las 9:00 desde la plaza de Velefique, 5 euros, 40 plazas. ¿Te apuntas?",
     "publicar"),
    ("Torneo de fútbol sala el 12 de diciembre a las 17:00", "publicar"),
    # Mensajes cortos sin pregunta: antes acababan en el saludo genérico «¿Buscas planes?»
    ("rutas este fin de semana", "buscar"),
    ("Conciertos mañana", "buscar"),
    ("algo para el finde", "buscar"),
    ("rutas", "buscar"),
])
def test_intencion(texto, tipo):
    assert intencion.detectar(texto).tipo == tipo


def test_pregunta_sobre_el_evento_que_esta_mirando():
    assert intencion.detectar("¿Hay que llevar linterna?", mirando_evento=True).tipo == "pregunta_evento"
    assert intencion.detectar("¿Hay que llevar linterna?").tipo == "buscar"


# ---------- Buscar ----------

def test_interpretar_consulta():
    viernes = datetime(2026, 11, 20, 10, 0, tzinfo=TZ)  # viernes
    c = busqueda.interpretar("¿Qué hay este finde en Senés de comida?", viernes)
    assert c.municipio == "Senés" and c.categorias == ["gastronomia"]
    assert c.desde.date() == date(2026, 11, 20) and c.hasta.date() == date(2026, 11, 22)
    c = busqueda.interpretar("y mañana?", viernes)
    assert c.desde.date() == c.hasta.date() == date(2026, 11, 21)


def test_buscar_muestra_tarjetas_con_botones(agenda):
    r = conversacion.procesar(_msg("¿qué hay en Senés?"))
    assert "Senés" in r[0] and "Migas solidarias" in r[1]
    assert canales.bandeja_consola[-1]["botones"] == [("insc:e2", "✋ Apuntarme"), ("info:e2", "ℹ️ Más info")]


def test_buscar_sin_resultados_en_esas_fechas_mira_mas_adelante(agenda):
    agenda.agenda = [agenda.agenda[3]]  # solo la fiesta, dentro de 20 días
    r = conversacion.procesar(_msg("¿qué hay mañana?"))
    assert "más adelante" in r[0] and "matanza" in r[1]


def test_buscar_pone_primero_lo_que_le_gusta(agenda):
    vecino.preferencias_locales["+34600000201"] = preferencias.Preferencias(gustos=["cultural"])
    r = conversacion.procesar(_msg("¿qué hay este mes?"))
    assert "Teatro" in r[1] and "Te gusta: cultura" in r[1]


def test_cerca_en_telegram_pide_ubicacion_y_luego_busca(agenda):
    r = conversacion.procesar(_msg("¿qué hay cerca?", de="tg:7", canal="telegram"))
    assert "ubicación" in r[0]
    r = conversacion.procesar(_msg(de="tg:7", canal="telegram", lat=37.19, lon=-2.40))
    assert "Gracias" in r[0] and "Esto es lo que hay" in r[1]
    assert any("lat=37.19" in ruta for _, ruta, _ in agenda.llamadas)


def test_recomendaciones_de_la_api_con_motivo(agenda):
    agenda.recomendaciones = [{"evento": agenda.agenda[0], "puntuacion": 0.9,
                               "motivo": "Te gusta el senderismo y está a 4 km"}]
    r = conversacion.procesar(_msg("recomiéndame algo"))
    assert "Te recomiendo" in r[0] and "está a 4 km" in r[1]


# ---------- Gustos ----------

def test_gustos_se_guardan_y_enseña_planes(agenda):
    r = conversacion.procesar(_msg("Me gustan las rutas y las fiestas"))
    assert "deporte y rutas" in r[0] and "fiestas" in r[0]
    assert vecino.preferencias_locales["+34600000201"].gustos == ["deportiva", "fiestas"]
    assert any("Ruta por la sierra" in x for x in r)
    assert ("PATCH", "/api/v1/usuarios/u-carmen",
            {"gustos": ["deportiva", "fiestas"], "etiquetas_interes": ["ruta", "fiesta"]}) in agenda.llamadas


def test_preferencias_con_audio():
    p = preferencias.interpretar("me gusta el teatro y avísame con audios")
    assert p.gustos == ["cultural"] and p.formato_aviso == "audio"


# ---------- Inscripción ----------

def test_apuntarse_con_un_boton(agenda):
    r = conversacion.procesar(_msg("✋ Apuntarme", boton_id="insc:e1"))
    assert "Apuntado" in r[0]
    assert ("POST", "/api/v1/eventos/e1/inscripciones",
            {"usuario_id": "u-carmen", "plazas": 1, "canal": "whatsapp"}) in agenda.llamadas


def test_lista_de_espera(agenda):
    agenda.lleno = True
    assert "lista de espera (puesto 2)" in conversacion.procesar(_msg("", boton_id="insc:e1"))[0]


def test_sin_inscripciones_en_la_api_manda_a_la_web(agenda):
    agenda.inscripciones_implementadas = False
    r = conversacion.procesar(_msg("", boton_id="insc:e1"))
    assert "Todavía no puedo apuntarte" in r[0] and "/evento/e1" in r[0]


def test_telegram_sin_vincular_pide_numero_y_luego_apunta(agenda):
    r = conversacion.procesar(_msg("", de="tg:8", canal="telegram", boton_id="insc:e1"))
    assert "Compartir mi número" in r[0]
    r = conversacion.procesar(_msg(de="tg:8", canal="telegram", nombre="Carmen", telefono_compartido="+34600000201"))
    assert "Gracias" in r[0] and "Apuntado" in r[1]


# ---------- Ficha y asistente ----------

def test_mas_info_y_preguntas_con_la_ficha(agenda):
    r = conversacion.procesar(_msg("", boton_id="info:e1"))
    assert "Ruta de 12 km" in r[0] and "/evento/e1" in r[0]
    assert "Cuesta 5 €" in conversacion.procesar(_msg("¿Cuánto cuesta?"))[0]
    assert "Empieza el" in conversacion.procesar(_msg("¿A qué hora empieza?"))[0]


def test_pregunta_que_no_esta_en_la_ficha_va_al_organizador(agenda):
    agenda.chat_implementado = True
    conversacion.procesar(_msg("", boton_id="info:e1"))
    r = conversacion.procesar(_msg("¿Puedo llevar al perro?"))
    assert "Se lo he pasado al organizador" in r[0]
    assert any(ruta == "/api/v1/eventos/e1/mensajes" for _, ruta, _ in agenda.llamadas)


def test_asistente_no_inventa():
    ev = {"titulo": "Ruta", "fecha_inicio": "2026-11-28T10:00:00+01:00", "es_gratuito": True}
    assert asistente.responder(ev, "¿es gratis?").respuesta == "Es gratis."
    r = asistente.responder(ev, "¿hay autobús desde Almería?")  # sin IA: no lo sabe
    assert r.puede_responder is False and r.respuesta is None


# ---------- Por voz ----------

def test_vecina_pregunta_con_una_nota_de_voz(agenda, monkeypatch):
    monkeypatch.setattr(telegram, "descargar_archivo", lambda fid: b"OGG")
    monkeypatch.setattr(medios, "transcribir", lambda d, m: "¿Qué hay este mes en Velefique?")
    agenda.usuarios["tg:9"] = CARMEN
    r = conversacion.procesar(_msg(de="tg:9", canal="telegram", media_id="V", media_tipo="audio/ogg"))
    assert r[0].startswith("🎙️ He entendido") and "Velefique" in r[1] and "Ruta por la sierra" in r[2]


# ---------- Endpoints y avisos ----------

def test_endpoints_ai_de_la_vecina():
    cab = {"X-Internal-Token": "test"}
    r = cliente.post("/ai/preferencias", json={"texto": "me gustan las rutas"}, headers=cab).json()
    assert r["gustos"] == ["deportiva"]
    r = cliente.post("/ai/responder-ficha", headers=cab, json={
        "evento": {"titulo": "X", "precio_eur": 3}, "pregunta": "¿cuánto cuesta?"}).json()
    assert r == {"puede_responder": True, "respuesta": "Cuesta 3 €.", "proveedor_ia": "reglas"}
    assert cliente.post("/ai/preferencias", json={"texto": "x"}).status_code == 401


def test_notify_recomendacion_con_boton_de_apuntarse(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    from app.config import get_settings
    get_settings.cache_clear()
    enviados = []
    monkeypatch.setattr(telegram, "enviar", lambda destino, texto, botones=None, **k: enviados.append((destino, botones)))
    cliente.post("/notify", headers={"X-Internal-Token": "test"}, json={
        "telefono": "+34600000201", "contacto": "tg:9", "tipo": "recomendacion",
        "texto": "Te puede gustar: Ruta por la sierra", "evento_id": "e1"})
    assert enviados == [("tg:9", [("insc:e1", "✋ Apuntarme"), ("info:e1", "ℹ️ Más info")])]


# ---------- Planes terminados (contrato: 409 evento_finalizado) ----------

def test_apuntarse_a_un_plan_terminado_no_dice_ya_estabas(agenda):
    agenda.finalizados.add("e1")
    r = conversacion.procesar(_msg("", boton_id="insc:e1"))
    assert "ya ha terminado" in r[0] and "Ya estabas" not in r[0]


def test_ya_apuntado_sigue_funcionando(agenda, monkeypatch):
    from app import api_cliente
    from app.api_cliente import ErrorApi

    def ya(*a, **k):
        raise ErrorApi(409, "ya_inscrito", "Ya inscrito")

    monkeypatch.setattr(api_cliente, "inscribir", ya)
    assert "Ya estabas" in conversacion.procesar(_msg("", boton_id="insc:e1"))[0]


def test_ficha_de_un_plan_pasado_sin_boton_de_apuntarse(agenda):
    agenda.agenda.append(_ev("viejo", "Fiesta pasada", "Senés", "fiestas", -3))
    r = conversacion.procesar(_msg("", boton_id="info:viejo"))
    assert "ya terminó" in r[0] and canales.bandeja_consola[-1]["botones"] == []
    # Y si aun así pulsa un botón viejo de «Apuntarme», ni se llama a la api
    antes = len(agenda.llamadas)
    assert "ya ha terminado" in conversacion.procesar(_msg("", boton_id="insc:viejo"))[0]
    assert not any(r.endswith("/inscripciones") for _, r, _ in agenda.llamadas[antes:])


def test_terminado():
    assert vecino.terminado({"estado": "finalizado", "fecha_inicio": "2099-01-01T10:00:00+01:00"})
    assert vecino.terminado({"fecha_inicio": "2020-01-01T10:00:00+01:00"})
    assert not vecino.terminado({"fecha_inicio": "2099-01-01T10:00:00+01:00"})
    assert not vecino.terminado({"fecha_inicio": "2020-01-01T10:00:00+01:00", "fecha_fin": "2099-01-01T10:00:00+01:00"})


def test_inscribir_por_nombre_entre_varios_planes():
    from app.vecino import _por_nombre
    titulos = {"a": "Menú del domingo: migas con tropezones", "b": "Taller de esparto", "c": "Ruta de la Tapa y el Postre"}
    assert _por_nombre("apuntame al taller de esparto", titulos) == "b"
    assert _por_nombre("me apunto a las migas", titulos) == "a"
    assert _por_nombre("apuntame", titulos) is None  # no dice cuál: se pregunta


# ---------- B1: hallazgos de la prueba sin IA ----------

@pytest.mark.parametrize("post,titulo", [
    ("Taller de esparto en Senés el sábado 28 de noviembre a las 11:00 en la plaza. Gratis", "Taller de esparto"),
    ("Este sábado fiesta de la castaña en Tahal a las 18:00", "Fiesta de la castaña"),
    ("Mañana a las 10 ruta por Uleila", "Ruta por Uleila"),
    ("¡Hola vecinos! Taller de cocina en Senés el sábado", "Taller de cocina"),
    ("II Ruta Solidaria Sierra de Velefique\nEl domingo 30 a las 9:00", "II Ruta Solidaria Sierra de Velefique"),
])
def test_titulo_por_reglas_es_el_nombre_del_plan(post, titulo):
    from app.agentes.extractor import titulo_por_reglas
    assert titulo_por_reglas(post) == titulo


def test_pregunta_por_un_plan_en_el_chat_privado_se_responde(agenda):
    agenda.agenda[0]["titulo"] = "II Ruta Solidaria Sierra de Velefique"
    agenda.agenda[0]["es_gratuito"] = True
    r = conversacion.procesar(_msg("¿Es gratis la ruta solidaria?"))
    texto = " ".join(x if isinstance(x, str) else x.texto for x in r)
    assert "Es gratis" in texto and "📌" not in texto  # responde, no enseña tarjetas


def test_pregunta_general_sigue_siendo_busqueda(agenda):
    r = conversacion.procesar(_msg("¿qué hay en Senés?"))
    assert "Migas solidarias" in r[1]


def test_spam_sin_fecha_no_se_queda_preguntando(agenda):
    r = conversacion.procesar(_msg("APUESTAS DEPORTIVAS!!! gana dinero con el casino, entra ya en bit.ly/xxx"))
    texto = " ".join(x if isinstance(x, str) else x.texto for x in r)
    assert "spam" in texto and "¿Qué día" not in texto
    assert not conversacion.estados.get("+34600000201") or not conversacion.estados["+34600000201"].preguntando


def test_recomendaciones_de_este_finde_solo_son_de_este_finde(agenda, monkeypatch):
    # Sábado por la mañana: «este finde» es hoy y mañana
    monkeypatch.setattr(vecino, "_ahora", lambda: datetime(2026, 11, 21, 10, 0, tzinfo=TZ))
    finde = dict(agenda.agenda[0], id="f1", titulo="Fiesta del sábado", fecha_inicio="2026-11-21T20:00:00+01:00")
    lejos = dict(agenda.agenda[1], id="l1", titulo="Ruta del 13", fecha_inicio="2026-12-13T09:00:00+01:00")
    agenda.recomendaciones = [{"evento": lejos, "motivo": "Te gusta el senderismo"},
                              {"evento": finde, "motivo": "Es en tu pueblo"}]
    r = conversacion.procesar(_msg("¿Qué planes hay este finde?"))
    texto = " ".join(x if isinstance(x, str) else x.texto for x in r)
    assert "Fiesta del sábado" in texto and "Ruta del 13" not in texto


def test_sin_recomendaciones_en_el_finde_dice_que_no_hay_y_ofrece_mas_adelante(agenda, monkeypatch):
    monkeypatch.setattr(vecino, "_ahora", lambda: datetime(2026, 11, 21, 10, 0, tzinfo=TZ))
    lejos = dict(agenda.agenda[1], id="l1", titulo="Ruta del 13", fecha_inicio="2026-12-13T09:00:00+01:00")
    agenda.recomendaciones = [{"evento": lejos, "motivo": "Te gusta el senderismo"}]
    agenda.agenda = [lejos]
    r = conversacion.procesar(_msg("¿Qué planes hay este finde?"))
    assert "Te recomiendo este fin de semana" not in r[0] and "más adelante" in r[0]
