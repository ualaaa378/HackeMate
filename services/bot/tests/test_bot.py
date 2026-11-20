from fastapi.testclient import TestClient

from app.main import app

cliente = TestClient(app)


def _di(texto, de="+34611111111"):
    return cliente.post("/dev/mensaje", json={"de": de, "texto": texto}).json()["respuestas"]


def test_health():
    assert cliente.get("/health").json()["status"] == "ok"


def test_saludo_responde_ayuda():
    assert "mándame el texto" in _di("hola")[0]


def test_flujo_publicador_pregunta_lo_que_falta_y_confirma():
    r = _di("Torneo de fútbol sala el 12 de diciembre a las 17:00, inscripción 10 euros")
    assert len(r) == 1  # ficha y pregunta van juntas
    assert "Esto es lo que he entendido" in r[0]
    assert "pueblo" in r[0]  # falta el municipio

    r = _di("En Uleila")
    assert "Uleila del Campo" in r[0]
    assert "SÍ" in r[0]

    r = _di("sí")
    # La api no está levantada en los tests: el evento queda en cola
    assert "Guardado" in r[0]
    from app import api_cliente
    assert api_cliente.pendientes[0]["json"]["extraccion"]["campos"]["municipio"]["valor"] == "Uleila del Campo"


def test_cancelar_borra_el_borrador():
    _di("Concierto en Tahal el 5 de diciembre")
    assert "borrado" in _di("cancelar")[0]


def test_webhook_twilio_acusa_al_momento():
    r = cliente.post("/webhook/twilio", data={
        "From": "whatsapp:+34622222222",
        "Body": "Gran fiesta de la matanza en Lucainena el sábado 6 de diciembre a las 12:00",
        "NumMedia": "0",
    })
    assert r.status_code == 200
    assert "Recibido" in r.text and r.text.startswith("<?xml")
    from app import canales
    assert any(m["para"] == "+34622222222" for m in canales.bandeja_consola)


def test_endpoints_internos_piden_token():
    assert cliente.post("/ai/extraer", json={"texto": "x"}).status_code == 401
    r = cliente.post("/notify", json={"telefono": "+34633333333", "texto": "Cambio de hora"},
                     headers={"X-Internal-Token": "test"})
    assert r.json() == {"enviado": True}


def test_metricas_registran_las_llamadas():
    _di("Ruta en bici por Senés el 14 de diciembre a las 10:00")
    m = cliente.get("/metrics").json()
    assert m["totales"]["reglas"]["llamadas"] >= 1
