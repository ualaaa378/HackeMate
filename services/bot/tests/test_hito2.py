"""Hito 2: importar → confirmar según contrato, identidad en Telegram, moderador por chat,
notas de voz, carteles y antispam."""

import httpx
import pytest
from fastapi.testclient import TestClient

from app import canales, conversacion, telegram
from app.agentes import antispam, extractor, medios
from app.main import app
from app.schemas import MensajeEntrante

cliente = TestClient(app)
POST = "Torneo de fútbol sala el 12 de diciembre a las 17:00, inscripción 10 euros"


def _msg(texto="", de="+34611111111", **kw):
    return MensajeEntrante(canal=kw.pop("canal", "whatsapp"), de=de, texto=texto, **kw)


# ---------- Publicador: importar → completar → confirmar ----------

def test_importa_al_momento_pregunta_lo_que_falta_y_confirma(api):
    api.caida = False
    r = conversacion.procesar(_msg(POST))
    assert "pueblo" in r[0]
    importar = [c for c in api.llamadas if c[1] == "/api/v1/eventos/importar"]
    assert len(importar) == 1 and importar[0][2]["contacto_publicador"] == "+34611111111"
    assert importar[0][2]["origen"]["canal"] == "whatsapp"

    conversacion.procesar(_msg("En Uleila"))
    r = conversacion.procesar(_msg("sí", boton_id="si"))
    assert "moderador lo revisará" in r[0]
    confirmar = [c for c in api.llamadas if c[1].endswith("/confirmar")][0]
    assert confirmar[2] == {"campos": {"municipio": "Uleila del Campo"}, "confirmado_por": "whatsapp"}


def test_si_la_api_lo_publica_directamente_se_dice(api):
    api.caida = False
    api.estado_tras_confirmar = "publicado"
    conversacion.procesar(_msg("Concierto en Tahal el 5 de diciembre a las 20:00"))
    assert "Publicado" in conversacion.procesar(_msg("si", boton_id="si"))[0]


def test_sin_confirmar_en_la_api_guarda_con_patch(api):
    api.caida = False
    api.confirmar_implementado = False
    conversacion.procesar(_msg(POST))
    conversacion.procesar(_msg("Senés"))
    r = conversacion.procesar(_msg("si"))
    assert "Recibido" in r[0]
    assert any(m == "PATCH" and j == {"municipio": "Senés"} for m, _, j in api.llamadas)


def test_publicador_pausado(api, monkeypatch):
    from app import api_cliente
    from app.api_cliente import ErrorApi

    def pausado(*a, **k):
        raise ErrorApi(403, "publicador_pausado", "pausado")

    monkeypatch.setattr(api_cliente, "importar_evento", pausado)
    assert "en pausa" in conversacion.procesar(_msg(POST))[0]


def test_duplicado(api, monkeypatch):
    from app import api_cliente
    monkeypatch.setattr(api_cliente, "importar_evento",
                        lambda *a, **k: {"evento": {"id": "e1"}, "faltan": [], "duplicado": True})
    assert "ya lo tenía" in conversacion.procesar(_msg(POST))[0]


# ---------- Identidad en Telegram ----------

def test_saludo_en_telegram_sin_vincular_pide_el_numero(api):
    api.caida = False
    conversacion.procesar(_msg("hola", de="tg:555", canal="telegram"))
    assert canales.bandeja_consola[-1]["pedir_contacto"] is True


def test_compartir_numero_vincula_con_la_api(api):
    api.caida = False
    m, _ = telegram.parsear({"update_id": 1, "message": {
        "chat": {"id": 555}, "from": {"id": 555, "first_name": "Carmen"},
        "contact": {"phone_number": "34600000201", "user_id": 555}}})
    assert m.telefono_compartido == "+34600000201"
    r = conversacion.procesar(m)
    assert "Gracias, Carmen" in r[0]
    assert ("POST", "/api/v1/usuarios/vincular",
            {"telefono": "+34600000201", "contacto": "tg:555", "nombre": "Carmen"}) in api.llamadas


def test_no_acepta_el_numero_de_otra_persona():
    m, _ = telegram.parsear({"update_id": 1, "message": {
        "chat": {"id": 555}, "from": {"id": 555}, "contact": {"phone_number": "34999", "user_id": 777}}})
    assert m.telefono_compartido is None


def test_boton_compartir_en_telegram(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    from app.config import get_settings
    get_settings.cache_clear()
    enviados = []
    monkeypatch.setattr(telegram, "_llamar", lambda metodo, cuerpo: enviados.append(cuerpo))
    telegram.enviar("tg:555", "hola", pedir_contacto=True)
    assert enviados[0]["reply_markup"]["keyboard"][0][0]["request_contact"] is True


# ---------- Moderador ----------

LUCIA = {"id": "u1", "nombre": "Lucía", "rol": "moderador"}


def test_bandeja_del_moderador_con_botones(api):
    api.caida = False
    api.usuarios["tg:1"] = LUCIA
    api.pendientes = [{"tipo": "evento", "motivo": "publicador de nivel 0", "score_spam": 0.1, "evento": {
        "id": "ev-1", "titulo": "Fiesta", "municipio": "Tahal", "fecha_inicio": "2026-12-05T20:00:00+01:00"}}]
    r = conversacion.procesar(_msg("pendientes", de="tg:1", canal="telegram"))
    assert "1 pendiente" in r[0] and "Fiesta" in r[1] and "nivel 0" in r[1]
    assert canales.bandeja_consola[-1]["botones"] == [("mod:aprobar:ev-1", "✅ Aprobar"),
                                                     ("mod:rechazar:ev-1", "❌ Rechazar")]
    r = conversacion.procesar(_msg("✅ Aprobar", de="tg:1", canal="telegram", boton_id="mod:aprobar:ev-1"))
    assert "Aprobado" in r[0]
    assert ("POST", "/api/v1/moderacion/ev-1/decision",
            {"decision": "aprobar", "motivo": "Decidido por chat (telegram)"}) in api.llamadas


def test_bandeja_sin_implementar_en_la_api(api):
    api.caida = False
    api.usuarios["tg:1"] = LUCIA
    assert "aún no está disponible" in conversacion.procesar(_msg("pendientes", de="tg:1", canal="telegram"))[0]


def test_solo_moderadores(api):
    api.caida = False
    assert "solo para moderadores" in conversacion.procesar(_msg("pendientes"))[0]
    assert "solo para moderadores" in conversacion.procesar(_msg("", boton_id="mod:aprobar:x"))[0]


# ---------- Notas de voz y carteles ----------

def test_nota_de_voz_se_transcribe_y_se_extrae(monkeypatch):
    monkeypatch.setattr(telegram, "descargar_archivo", lambda fid: b"OGG")
    monkeypatch.setattr(medios, "transcribir",
                        lambda datos, mime: "El sábado 28 de noviembre a las 10 ruta de senderismo en Belefique, 5 euros")
    r = conversacion.procesar(_msg(de="tg:9", canal="telegram", media_id="V1", media_tipo="audio/ogg"))
    assert r[0].startswith("🎙️ He entendido")
    assert "Velefique" in r[1]  # «Belefique» corregido


def test_cartel_ilegible_pide_el_texto(monkeypatch):
    monkeypatch.setattr(telegram, "descargar_archivo", lambda fid: b"JPG")
    monkeypatch.setattr(medios, "leer_imagen", lambda datos, mime: None)
    r = conversacion.procesar(_msg(de="tg:9", canal="telegram", media_id="F1", media_tipo="image/jpeg"))
    assert "No he podido entender" in r[0]


@pytest.fixture
def freellm(monkeypatch):
    monkeypatch.setenv("FREELLM_API_KEY", "freellmapi-test")
    from app.config import get_settings
    get_settings.cache_clear()


def test_transcribir_con_freellm(freellm, monkeypatch):
    def post(url, **kw):
        assert url.endswith("/audio/transcriptions") and kw["data"]["model"] == "whisper-large-v3"
        return httpx.Response(200, json={"text": " Hola vecinos "}, request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    assert medios.transcribir(b"x", "audio/ogg") == "Hola vecinos"


def test_leer_cartel_pasa_al_siguiente_modelo(freellm, monkeypatch):
    modelos = []

    def post(url, **kw):
        modelos.append(kw["json"]["model"])
        if len(modelos) == 1:
            return httpx.Response(503, json={}, request=httpx.Request("POST", url))
        assert kw["json"]["messages"][0]["content"][1]["image_url"]["url"].startswith("data:image/jpeg;base64,")
        return httpx.Response(200, json={"choices": [{"message": {"content": "FIESTA DE LA MATANZA"}}]},
                              request=httpx.Request("POST", url))
    monkeypatch.setattr(httpx, "post", post)
    assert medios.leer_imagen(b"jpg") == "FIESTA DE LA MATANZA"
    assert modelos == ["gemini-flash-lite", "auto"]


def test_municipio_tolera_b_y_v():
    assert extractor.buscar_municipio("ruta por belefique") == "Velefique"
    assert extractor.buscar_municipio("fiesta en uleila") == "Uleila del Campo"


# ---------- Antispam ----------

def test_spam_claro_por_reglas_sin_gastar_tokens(monkeypatch):
    from app.llm import router
    monkeypatch.setattr(router, "estructurado", lambda *a, **k: pytest.fail("no debería llamar a la IA"))
    r = antispam.puntuar("GANA DINERO CON CRIPTO!!! inversion garantizada bit.ly/xx https://a https://b https://c")
    assert r.es_spam and r.score_spam >= 0.7 and r.proveedor_ia == "reglas"
    r = antispam.puntuar("Fiesta de la matanza en la plaza de Uleila el sábado")
    assert not r.es_spam and r.score_spam == 0


def test_spam_dudoso_pregunta_a_la_ia(monkeypatch):
    from app.llm import router

    def ia(tarea, system, texto, salida, reglas):
        return router.Resultado(salida=salida(es_spam=True, score_spam=0.9, motivo="publicidad ajena"),
                                proveedor="freellm:x")
    monkeypatch.setattr(router, "estructurado", ia)
    r = antispam.puntuar("Mira esto que te interesa bit.ly/abc")  # enlace acortado: 0.4, dudoso
    assert r.es_spam and r.proveedor_ia == "freellm:x" and "publicidad ajena" in r.motivo


def test_endpoint_ai_spam():
    assert cliente.post("/ai/spam", json={"texto": "hola"}).status_code == 401
    r = cliente.post("/ai/spam", json={"texto": "Ruta por Senés el domingo"}, headers={"X-Internal-Token": "test"})
    assert r.status_code == 200 and r.json()["es_spam"] is False


def test_simulador_nunca_escribe_a_un_canal_real(monkeypatch):
    monkeypatch.setenv("CANAL", "meta")
    from app.config import get_settings
    get_settings.cache_clear()
    monkeypatch.setattr(canales, "_enviar_meta", lambda *a, **k: pytest.fail("no debe usar Meta"))
    r = cliente.post("/dev/mensaje", json={"de": "+34600000101", "texto": "hola"})
    assert r.status_code == 200 and canales.bandeja_consola
