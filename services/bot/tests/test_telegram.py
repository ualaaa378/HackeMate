import httpx
import pytest
from fastapi.testclient import TestClient

from app import canales, telegram
from app.main import app

cliente = TestClient(app)


def _update_texto(texto, update_id=1, chat=555):
    return {"update_id": update_id, "message": {"message_id": 1, "chat": {"id": chat, "type": "private"},
                                                "from": {"id": chat, "first_name": "Fran"}, "text": texto}}


@pytest.fixture
def tg(monkeypatch):
    monkeypatch.setenv("TELEGRAM_TOKEN", "123:abc")
    monkeypatch.setenv("TELEGRAM_SECRET", "s3cr3t")
    from app.config import get_settings
    get_settings.cache_clear()
    llamadas = []

    def post(url, json=None, timeout=None, **kw):
        if "api.telegram.org" not in url:
            raise httpx.ConnectError("api caída en los tests")  # la api y las métricas
        llamadas.append((url.rsplit("/", 1)[-1], json))
        return httpx.Response(200, json={"ok": True, "result": {}}, request=httpx.Request("POST", url))

    monkeypatch.setattr(httpx, "post", post)
    return llamadas


def test_parsear_texto_start_voz_foto_ubicacion_y_boton():
    m, cb = telegram.parsear(_update_texto("/start"))
    assert m.de == "tg:555" and m.texto == "hola" and m.nombre == "Fran" and cb is None

    m, _ = telegram.parsear({"update_id": 2, "message": {"chat": {"id": 555}, "voice": {
        "file_id": "VOZ1", "mime_type": "audio/ogg"}}})
    assert m.media_id == "VOZ1" and m.media_tipo == "audio/ogg"

    m, _ = telegram.parsear({"update_id": 3, "message": {"chat": {"id": 555}, "caption": "cartel", "photo": [
        {"file_id": "peq", "file_size": 10}, {"file_id": "grande", "file_size": 999}]}})
    assert m.media_id == "grande" and m.texto == "cartel"

    m, _ = telegram.parsear({"update_id": 4, "message": {"chat": {"id": 555},
                                                         "location": {"latitude": 37.1, "longitude": -2.4}}})
    assert m.lat == 37.1

    m, cb = telegram.parsear({"update_id": 5, "callback_query": {
        "id": "CB1", "data": "si", "from": {"id": 555, "first_name": "Fran"},
        "message": {"chat": {"id": 555}}}})
    assert m.boton_id == "si" and m.de == "tg:555" and cb == "CB1"


def test_a_html_convierte_negrita_y_escapa():
    assert telegram.a_html("Responde *SÍ* o <NO> & ya") == "Responde <b>SÍ</b> o &lt;NO&gt; &amp; ya"


def test_webhook_rechaza_sin_secreto(tg):
    r = cliente.post("/webhook/telegram", json=_update_texto("hola"))
    assert r.status_code == 403


def test_flujo_completo_por_telegram_con_botones(tg):
    cab = {"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"}
    r = cliente.post("/webhook/telegram", headers=cab,
                     json=_update_texto("Concierto en Tahal el 5 de diciembre a las 20:00", update_id=10))
    assert r.status_code == 200
    envios = [c for c in tg if c[0] == "sendMessage"]
    ultimo = envios[-1][1]
    assert ultimo["chat_id"] == "555" and ultimo["parse_mode"] == "HTML"
    assert ultimo["reply_markup"]["inline_keyboard"] == [[{"text": "Sí, publicar", "callback_data": "si"}],
                                                         [{"text": "No", "callback_data": "no"}]]

    # Pulsa «Sí, publicar»
    cliente.post("/webhook/telegram", headers=cab, json={"update_id": 11, "callback_query": {
        "id": "CB9", "data": "si", "from": {"id": 555}, "message": {"chat": {"id": 555}}}})
    assert ("answerCallbackQuery", {"callback_query_id": "CB9"}) in tg
    assert "Guardado" in [c for c in tg if c[0] == "sendMessage"][-1][1]["text"]
    from app import api_cliente
    assert api_cliente.pendientes[-1]["origen"] == {"canal": "telegram", "url": None, "importado_auto": False}


def test_update_repetido_no_se_procesa_dos_veces(tg):
    cab = {"X-Telegram-Bot-Api-Secret-Token": "s3cr3t"}
    cliente.post("/webhook/telegram", headers=cab, json=_update_texto("hola", update_id=77))
    cliente.post("/webhook/telegram", headers=cab, json=_update_texto("hola", update_id=77))
    assert len([c for c in tg if c[0] == "sendMessage"]) == 1


def test_avisos_a_telegram_van_como_texto_aunque_el_canal_sea_meta(tg, monkeypatch):
    monkeypatch.setenv("CANAL", "meta")
    from app.config import get_settings
    get_settings.cache_clear()
    canales.enviar_plantilla("tg:555", "cambio_hora", ["Ruta", "10:00"], texto_alternativo="La ruta cambia a las 10:00")
    assert tg[-1] == ("sendMessage", {"chat_id": "555", "text": "La ruta cambia a las 10:00", "parse_mode": "HTML"})
