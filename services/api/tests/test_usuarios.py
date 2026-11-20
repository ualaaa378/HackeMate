"""Usuarios: alta y búsqueda por teléfono para el bot (E1.5)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.config import get_settings
from app.seed import sembrar

SCHEMAS = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
VIERNES = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
TOKEN = {"X-Internal-Token": get_settings().internal_token}
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
TELEFONO_CARMEN = "+34600000201"

USUARIO = Draft202012Validator(
    json.loads((SCHEMAS / "usuario.json").read_text(encoding="utf-8")),
    format_checker=Draft202012Validator.FORMAT_CHECKER,
)


def _valida(dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in USUARIO.iter_errors(dato)]
    assert not errores, "\n".join(errores)


def _error(r, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    cuerpo = r.json()
    assert set(cuerpo) == {"error"}
    assert cuerpo["error"]["code"] == code
    assert {"code", "message", "details"} <= set(cuerpo["error"])


@pytest.fixture
def api(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


# --- GET /usuarios/by-phone/{e164} --------------------------------------------------------


@pytest.mark.parametrize("ruta", [TELEFONO_CARMEN, "%2B34600000201", "%2b34600000201", "0034600000201"])
def test_by_phone_encuentra_a_carmen(api, ruta):
    r = api.get(f"/api/v1/usuarios/by-phone/{ruta}", headers=TOKEN)
    assert r.status_code == 200, r.text
    u = r.json()
    _valida(u)
    assert u["id"] == CARMEN
    assert u["nombre"] == "Carmen" and u["municipio"] == "Senés"
    assert u["telefono"] == TELEFONO_CARMEN
    assert u["formato_aviso"] == "audio"


def test_by_phone_sin_token_401(api):
    _error(api.get(f"/api/v1/usuarios/by-phone/{TELEFONO_CARMEN}"), 401, "token_interno_invalido")
    _error(
        api.get(f"/api/v1/usuarios/by-phone/{TELEFONO_CARMEN}", headers={"X-Internal-Token": "malo"}),
        401,
        "token_interno_invalido",
    )


def test_by_phone_404(api):
    _error(api.get("/api/v1/usuarios/by-phone/+34699999999", headers=TOKEN), 404, "usuario_no_encontrado")


@pytest.mark.parametrize("ruta", ["hola", "600000201", "+0034600000201", "+34", "+3460000020112345678"])
def test_by_phone_formato_invalido_422(api, ruta):
    _error(api.get(f"/api/v1/usuarios/by-phone/{ruta}", headers=TOKEN), 422, "telefono_invalido")


# --- POST /usuarios -----------------------------------------------------------------------


def test_alta_de_usuario(api):
    r = api.post(
        "/api/v1/usuarios",
        json={"telefono": "+34611111111", "nombre": "Rosario", "municipio": "Senés"},
        headers=TOKEN,
    )
    assert r.status_code == 201, r.text
    u = r.json()
    _valida(u)
    assert u["rol"] == "vecino" and u["nombre"] == "Rosario"
    assert u["telefono"] == "+34611111111"
    assert u["whatsapp_verificado"] is False
    assert (u["lat"], u["lon"]) == (37.1983, -2.3447)  # las de Senés

    r = api.get("/api/v1/usuarios/by-phone/%2B34611111111", headers=TOKEN)
    assert r.status_code == 200 and r.json()["id"] == u["id"]


def test_alta_solo_con_telefono(api):
    r = api.post("/api/v1/usuarios", json={"telefono": "+34 611-111-112"}, headers=TOKEN)
    assert r.status_code == 201, r.text
    _valida(r.json())
    assert r.json()["telefono"] == "+34611111112"
    assert r.json()["nombre"]  # el schema exige nombre
    assert r.json()["municipio"] is None and r.json()["lat"] is None


def test_alta_sin_token_401(api):
    _error(api.post("/api/v1/usuarios", json={"telefono": "+34611111111"}), 401, "token_interno_invalido")


def test_alta_duplicada_409(api):
    r = api.post("/api/v1/usuarios", json={"telefono": TELEFONO_CARMEN, "nombre": "Otra"}, headers=TOKEN)
    _error(r, 409, "usuario_ya_existe")
    assert r.json()["error"]["details"]["usuario_id"] == CARMEN
    # Mismo número escrito de otra forma.
    _error(api.post("/api/v1/usuarios", json={"telefono": "0034 600 000 201"}, headers=TOKEN), 409, "usuario_ya_existe")


@pytest.mark.parametrize(
    "datos",
    [
        {},
        {"nombre": "Sin teléfono"},
        {"telefono": "600000201"},
        {"telefono": "+34611111111", "rol": "moderador"},
    ],
)
def test_alta_datos_invalidos_422(api, datos):
    _error(api.post("/api/v1/usuarios", json=datos, headers=TOKEN), 422, "validacion")


def test_alta_municipio_desconocido_422(api):
    r = api.post("/api/v1/usuarios", json={"telefono": "+34611111111", "municipio": "Madrid"}, headers=TOKEN)
    _error(r, 422, "municipio_no_encontrado")


def test_me_no_esta_implementado_aun(api):
    # GET/PATCH /usuarios/me llegan en H3 con el login.
    assert api.get("/api/v1/usuarios/me", headers=TOKEN).status_code == 404
