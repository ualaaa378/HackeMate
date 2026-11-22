"""Canales de mensajeria (app/canales.py): WhatsApp (+34…) y Telegram (tg:<chat_id>) a la vez."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

from app.canales import (
    CANALES_MENSAJERIA,
    buscar_publicador_por_contacto,
    buscar_usuario_por_contacto,
    contacto_de,
    parsear_contacto,
)
from app.config import get_settings
from app.errores import ErrorApi
from app.modelos import CANALES, Publicador, Usuario
from app.seed import sembrar

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"
VIERNES = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
TOKEN = {"X-Internal-Token": get_settings().internal_token}
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
TELEFONO_CARMEN = "+34600000201"
ANTONIO = "5a5e0000-0000-4000-8000-000000000003"
AMIGOS_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"
TELEFONO_AMIGOS = "+34600000101"
BAR_LA_PLAZA = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a03"
IMPORTAR = "/api/v1/eventos/importar"
VINCULAR = "/api/v1/usuarios/vincular"


def _schema(nombre: str) -> Draft202012Validator:
    esquema = json.loads((CONTRATOS / "schemas" / f"{nombre}.json").read_text(encoding="utf-8"))
    return Draft202012Validator(esquema, format_checker=Draft202012Validator.FORMAT_CHECKER)


USUARIO = _schema("usuario")
PUBLICADOR = _schema("publicador")
EVENTO = _schema("evento")
NOTIFICACION = _schema("notificacion")
OPENAPI = YAML(typ="safe").load((CONTRATOS / "openapi.yaml").read_text(encoding="utf-8"))


def _valida(validador: Draft202012Validator, dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validador.iter_errors(dato)]
    assert not errores, "\n".join(errores)


def _error(r, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    cuerpo = r.json()
    assert set(cuerpo) == {"error"}
    assert cuerpo["error"]["code"] == code
    assert {"code", "message", "details"} <= set(cuerpo["error"])


def _importar(**extra) -> dict:
    extraccion = json.loads((CONTRATOS / "fixtures" / "extraccion_evento.json").read_text(encoding="utf-8"))[0]
    return {
        "extraccion": copy.deepcopy(extraccion),
        "origen": {"canal": "telegram", "url": None, "importado_auto": False},
        **extra,
    }


@pytest.fixture
def api(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


# --- Registro de canales -------------------------------------------------------------------


@pytest.mark.parametrize(
    "texto,canal,valor",
    [
        ("+34600000201", "whatsapp", "+34600000201"),
        ("0034 600 000 201", "whatsapp", "+34600000201"),
        ("tg:123456", "telegram", "123456"),
        ("tg:-100123", "telegram", "-100123"),
        ("TG:42", "telegram", "42"),
    ],
)
def test_parsear_contacto_valido(texto, canal, valor):
    c, v = parsear_contacto(texto)
    assert (c.nombre, v) == (canal, valor)
    assert parsear_contacto(contacto_de(c, v)) == (c, v)


@pytest.mark.parametrize("texto", ["tg:abc", "hola", "600", "", "tg:", "tg:123456789012345678901", "+0034600000201"])
def test_parsear_contacto_invalido(texto):
    with pytest.raises(ErrorApi) as e:
        parsear_contacto(texto)
    assert (e.value.status, e.value.code) == (422, "contacto_invalido")


def test_contacto_de():
    assert contacto_de("telegram", "123") == "tg:123"
    assert contacto_de("whatsapp", "+34600000201") == "+34600000201"


def test_cada_canal_tiene_su_columna_y_esta_en_el_enum():
    for canal in CANALES_MENSAJERIA.values():
        assert canal.nombre in CANALES
        assert hasattr(Usuario, canal.campo) and hasattr(Publicador, canal.campo)


def test_busquedas_por_contacto(api, db):
    db.get(Usuario, CARMEN).telegram_id = "555"
    db.commit()
    assert buscar_usuario_por_contacto(db, "tg:555").id == CARMEN
    assert buscar_usuario_por_contacto(db, TELEFONO_CARMEN).id == CARMEN
    assert buscar_usuario_por_contacto(db, "tg:556") is None
    assert buscar_publicador_por_contacto(db, TELEFONO_AMIGOS).id == AMIGOS_VELEFIQUE
    # Telegram: si el publicador no tiene el id, se busca por el teléfono del usuario vinculado
    db.get(Usuario, "5a5e0000-0000-4000-8000-000000000004").telegram_id = "777"
    db.commit()
    assert buscar_publicador_por_contacto(db, "tg:777").id == BAR_LA_PLAZA
    assert buscar_publicador_por_contacto(db, "tg:778") is None


# --- Contrato ------------------------------------------------------------------------------


def test_contrato_tiene_telegram_y_las_rutas_nuevas():
    for nombre in ("evento", "inscripcion"):
        esquema = json.loads((CONTRATOS / "schemas" / f"{nombre}.json").read_text(encoding="utf-8"))
        props = esquema["properties"]
        enum = props["origen"]["properties"]["canal"]["enum"] if nombre == "evento" else props["canal"]["enum"]
        assert list(enum) == list(CANALES)
    comp = OPENAPI["components"]["schemas"]
    assert comp["Origen"]["properties"]["canal"]["enum"] == list(CANALES)
    assert "contacto_publicador" in comp["ImportarEvento"]["properties"]
    for ruta, metodo in [
        ("/api/v1/usuarios/by-contacto/{contacto}", "get"),
        ("/api/v1/usuarios/vincular", "post"),
    ]:
        assert OPENAPI["paths"][ruta][metodo]["x-implementado"] is True
        assert OPENAPI["paths"][ruta][metodo]["security"] == [{"interno": []}]
    for ruta, metodo in [("/webhook/telegram", "post"), ("/webhook/meta", "get"), ("/webhook/meta", "post"), ("/dev/mensaje", "post")]:
        assert metodo in OPENAPI["paths"][ruta]


def test_notificacion_admite_contacto_y_plantilla():
    aviso = {
        "telefono": TELEFONO_CARMEN,
        "contacto": "tg:123456",
        "tipo": "cambio_evento",
        "texto": "La ruta empieza a las 10:00",
        "plantilla": "cambio_hora",
        "parametros": ["Ruta solidaria", "10:00"],
    }
    _valida(NOTIFICACION, aviso)
    assert list(NOTIFICACION.iter_errors({**aviso, "contacto": "tg:abc"}))


# --- POST /eventos/importar por Telegram ---------------------------------------------------


def test_importar_por_telegram_sin_publicador(api):
    r = api.post(IMPORTAR, json=_importar(telefono_publicador="tg:999"), headers=TOKEN)
    assert r.status_code == 201, r.text
    evento = r.json()["evento"]
    _valida(EVENTO, evento)
    assert evento["origen"]["canal"] == "telegram"
    assert evento["publicador_id"] is None


@pytest.mark.parametrize("campo", ["telefono_publicador", "contacto_publicador"])
def test_importar_por_telegram_tras_vincular(api, campo):
    r = api.post(VINCULAR, json={"telefono": TELEFONO_AMIGOS, "contacto": "tg:999"}, headers=TOKEN)
    assert r.status_code == 200, r.text
    r = api.post(IMPORTAR, json=_importar(**{campo: "tg:999"}), headers=TOKEN)
    assert r.status_code == 201, r.text
    assert r.json()["evento"]["publicador_id"] == AMIGOS_VELEFIQUE


def test_importar_contacto_publicador_whatsapp(api):
    cuerpo = _importar(contacto_publicador=TELEFONO_AMIGOS)
    cuerpo["origen"]["canal"] = "whatsapp"
    r = api.post(IMPORTAR, json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    assert r.json()["evento"]["publicador_id"] == AMIGOS_VELEFIQUE


# --- GET /usuarios/by-contacto/{contacto} ------------------------------------------------


@pytest.mark.parametrize("ruta", [TELEFONO_CARMEN, "%2B34600000201", "tg:4242"])
def test_by_contacto_encuentra_a_carmen(api, db, ruta):
    db.get(Usuario, CARMEN).telegram_id = "4242"
    db.commit()
    r = api.get(f"/api/v1/usuarios/by-contacto/{ruta}", headers=TOKEN)
    assert r.status_code == 200, r.text
    u = r.json()
    _valida(USUARIO, u)
    assert u["id"] == CARMEN
    assert u["telegram_id"] == "4242"


def test_by_contacto_404(api):
    _error(api.get("/api/v1/usuarios/by-contacto/tg:4242", headers=TOKEN), 404, "usuario_no_encontrado")
    _error(api.get("/api/v1/usuarios/by-contacto/+34699999999", headers=TOKEN), 404, "usuario_no_encontrado")


@pytest.mark.parametrize("ruta", ["tg:abc", "hola", "600"])
def test_by_contacto_422(api, ruta):
    _error(api.get(f"/api/v1/usuarios/by-contacto/{ruta}", headers=TOKEN), 422, "contacto_invalido")


def test_by_contacto_sin_token_401(api):
    _error(api.get("/api/v1/usuarios/by-contacto/tg:1"), 401, "token_interno_invalido")


# --- POST /usuarios/vincular -----------------------------------------------------------------


def test_vincular_crea_usuario(api):
    datos = {"telefono": "+34 699 000 111", "contacto": "tg:31337", "nombre": "Rosa", "municipio": "Tahal"}
    r = api.post(VINCULAR, json=datos, headers=TOKEN)
    assert r.status_code == 201, r.text
    u = r.json()
    _valida(USUARIO, u)
    assert (u["telefono"], u["telegram_id"], u["nombre"], u["municipio"]) == ("+34699000111", "31337", "Rosa", "Tahal")
    r = api.get("/api/v1/usuarios/by-contacto/tg:31337", headers=TOKEN)
    assert r.json()["id"] == u["id"]


def test_vincular_usuario_existente(api):
    r = api.post(VINCULAR, json={"telefono": TELEFONO_CARMEN, "contacto": "tg:-100777"}, headers=TOKEN)
    assert r.status_code == 200, r.text
    u = r.json()
    _valida(USUARIO, u)
    assert (u["id"], u["telegram_id"], u["nombre"]) == (CARMEN, "-100777", "Carmen")
    # Repetir es idempotente
    r = api.post(VINCULAR, json={"telefono": TELEFONO_CARMEN, "contacto": "tg:-100777"}, headers=TOKEN)
    assert r.status_code == 200, r.text


def test_vincular_tambien_al_publicador(api, db):
    r = api.post(VINCULAR, json={"telefono": TELEFONO_AMIGOS, "contacto": "tg:999"}, headers=TOKEN)
    assert r.status_code == 200, r.text
    assert r.json()["id"] == ANTONIO
    db.expire_all()
    assert db.get(Publicador, AMIGOS_VELEFIQUE).telegram_id == "999"
    # telegram_id solo sale con el token interno
    con = api.get(f"/api/v1/publicadores/{AMIGOS_VELEFIQUE}", headers=TOKEN).json()
    _valida(PUBLICADOR, con)
    assert con["telegram_id"] == "999"
    sin = api.get(f"/api/v1/publicadores/{AMIGOS_VELEFIQUE}")
    assert sin.status_code == 200, sin.text
    assert "telegram_id" not in sin.json() and "telefono" not in sin.json()


def test_vincular_contacto_en_uso_409(api):
    assert api.post(VINCULAR, json={"telefono": TELEFONO_CARMEN, "contacto": "tg:5"}, headers=TOKEN).status_code == 200
    r = api.post(VINCULAR, json={"telefono": "+34600000205", "contacto": "tg:5"}, headers=TOKEN)
    _error(r, 409, "contacto_en_uso")
    assert r.json()["error"]["details"]["usuario_id"] == CARMEN
    r = api.post(VINCULAR, json={"telefono": "+34699000222", "contacto": "tg:5"}, headers=TOKEN)
    _error(r, 409, "contacto_en_uso")


@pytest.mark.parametrize("contacto", ["tg:abc", "hola", "+34600000999"])
def test_vincular_contacto_invalido_422(api, contacto):
    r = api.post(VINCULAR, json={"telefono": TELEFONO_CARMEN, "contacto": contacto}, headers=TOKEN)
    _error(r, 422, "contacto_invalido")


def test_vincular_telefono_invalido_422(api):
    _error(api.post(VINCULAR, json={"telefono": "600", "contacto": "tg:1"}, headers=TOKEN), 422, "validacion")
    _error(api.post(VINCULAR, json={"contacto": "tg:1"}, headers=TOKEN), 422, "validacion")


def test_vincular_sin_token_401(api):
    _error(api.post(VINCULAR, json={"telefono": TELEFONO_CARMEN, "contacto": "tg:1"}), 401, "token_interno_invalido")
