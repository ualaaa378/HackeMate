"""B5: alta de una entidad por chat, con los datos del responsable (POST /publicadores)."""

import pytest

from app import alta, api_cliente, canales, conversacion
from app.api_cliente import ErrorApi
from app.schemas import MensajeEntrante

WA = "+34600000999"
TG = "tg:555"


def _msg(texto="", de=WA, **kw):
    return MensajeEntrante(canal=kw.pop("canal", "whatsapp"), de=de, texto=texto, **kw)


def _texto(respuestas) -> str:
    return " ".join(respuestas)


@pytest.fixture
def enviados(monkeypatch):
    lista = []
    monkeypatch.setattr(api_cliente, "crear_publicador", lambda cuerpo: lista.append(cuerpo) or {"id": "p1"})
    return lista


@pytest.mark.parametrize("texto,quiere", [
    ("Quiero dar de alta mi asociación", True),
    ("¿Cómo me doy de alta como bar?", False),  # «me doy» no es ninguna de las frases: mejor no adivinar
    ("quiero darme de alta", True),
    ("Quiero registrar mi bar", True),
    ("Ruta de alta montaña el sábado", False),
    ("quiero ser publicador", True),
])
def test_cuando_empieza_el_alta(texto, quiere):
    assert alta.quiere_alta(texto) is quiere


@pytest.mark.parametrize("dni,valido", [
    ("12345678Z", "12345678Z"), ("12.345.678-z", "12345678Z"), ("12345678A", None),
    ("X1234567L", "X1234567L"), ("X1234567A", None), ("hola", None),
])
def test_dni_y_nie_con_la_letra_de_control(dni, valido):
    assert alta.normalizar_dni(dni) == valido


def test_alta_completa_por_whatsapp(api, enviados):
    r = conversacion.procesar(_msg("Hola, quiero dar de alta mi asociación"))
    assert "¿Cómo se llama la entidad?" in _texto(r)
    conversacion.procesar(_msg("Asociación Amigos de Velefique"))
    r = conversacion.procesar(_msg("Es una asociación cultural"))  # el tipo también vale escrito
    assert "¿En qué pueblo está?" in _texto(r)
    r = conversacion.procesar(_msg("Madrid"))
    assert "no está en la plataforma" in _texto(r)
    conversacion.procesar(_msg("velefique"))
    r = conversacion.procesar(_msg("Antonio"))
    assert "apellido" in _texto(r)
    conversacion.procesar(_msg("Antonio García López"))
    r = conversacion.procesar(_msg("12345678A"))  # letra mal
    assert "no es válido" in _texto(r)
    conversacion.procesar(_msg("12345678Z"))
    r = conversacion.procesar(_msg("Velefique"))
    assert "Cuántos años" in _texto(r)  # P4b: opcional
    r = conversacion.procesar(_msg("12"))
    assert "al menos 14" in _texto(r)
    r = conversacion.procesar(_msg("58"))
    resumen = _texto(r)
    assert "58 años" in resumen
    assert "Asociación Amigos de Velefique (Asociación)" in resumen and "•••••678Z" in resumen
    assert "12345678Z" not in resumen  # el DNI nunca se enseña entero

    r = conversacion.procesar(_msg("", boton_id="alta_si"))
    assert "Solicitud enviada" in _texto(r)
    assert enviados == [{
        "nombre": "Asociación Amigos de Velefique", "tipo": "asociacion", "municipio": "Velefique",
        "telefono": WA,
        "responsable": {"nombre": "Antonio García López", "dni": "12345678Z", "residencia": "Velefique", "edad": 58},
    }]
    assert not alta.en_curso(WA)  # los datos personales ya no están en memoria


def test_tipo_con_boton_y_cancelar_borra_los_datos(api, enviados):
    conversacion.procesar(_msg("quiero registrar mi bar"))
    conversacion.procesar(_msg("Bar La Plaza"))
    assert canales.bandeja_consola[-1]["botones"][0] == ("alta_tipo:asociacion", "Asociación")
    conversacion.procesar(_msg("", boton_id="alta_tipo:bar_restaurante"))
    assert alta.altas[WA].datos["tipo"] == "bar_restaurante"
    r = conversacion.procesar(_msg("cancelar"))
    assert "borrado los datos" in _texto(r) and not alta.en_curso(WA) and enviados == []


def test_telegram_sin_numero_pide_compartirlo_y_sigue(api, enviados):
    api.caida = False
    r = conversacion.procesar(_msg("quiero dar de alta mi asociación", de=TG, canal="telegram"))
    assert "Compartir mi número" in _texto(r) and canales.bandeja_consola[-1]["pedir_contacto"]
    r = conversacion.procesar(_msg("Peña El Olivo", de=TG, canal="telegram"))  # aún sin número
    assert "Compartir mi número" in _texto(r)
    r = conversacion.procesar(_msg("", de=TG, canal="telegram", telefono_compartido="+34600000555"))
    assert "¿Cómo se llama la entidad?" in _texto(r)
    assert alta.altas[TG].telefono == "+34600000555"


def test_ya_publica_en_nombre_de_una_entidad(api):
    api.caida = False
    api.usuarios[WA] = {"id": "u1", "rol": "vecino", "telefono": WA, "publicador_id": "p9"}
    r = conversacion.procesar(_msg("quiero dar de alta mi asociación"))
    assert "Ya publicas en nombre de una entidad" in _texto(r) and not alta.en_curso(WA)


def _hasta_confirmar():
    for t in ("quiero dar de alta mi asociación", "Club Senderista Tahal", "asociación", "Tahal",
              "María Pérez Gil", "X1234567L", "Tahal", "saltar"):
        conversacion.procesar(_msg(t))


def test_errores_de_la_api(api, monkeypatch):
    _hasta_confirmar()

    def ya_existe(cuerpo):
        raise ErrorApi(409, "publicador_ya_existe", "Ya hay un publicador con ese teléfono")
    monkeypatch.setattr(api_cliente, "crear_publicador", ya_existe)
    r = conversacion.procesar(_msg("sí"))
    assert "ya tiene una entidad" in _texto(r) and not alta.en_curso(WA)

    _hasta_confirmar()

    def dni_malo(cuerpo):
        raise ErrorApi(422, "dni_invalido", "El DNI o NIE del responsable no es válido")
    monkeypatch.setattr(api_cliente, "crear_publicador", dni_malo)
    r = conversacion.procesar(_msg("sí"))
    assert "DNI o NIE" in _texto(r) and alta.altas[WA].paso == "dni"


def test_api_caida_no_encola_el_dni(api, monkeypatch):
    _hasta_confirmar()
    api.caida = True
    r = conversacion.procesar(_msg("sí"))
    assert "Inténtalo en un minuto" in _texto(r) and alta.en_curso(WA)
    assert not api_cliente.pendientes  # un DNI nunca va a la cola en disco
