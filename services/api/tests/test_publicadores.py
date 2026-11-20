"""Publicadores: lista, ficha y alta (E1.5)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator

from app.config import get_settings
from app.modelos import Publicador
from app.seed import sembrar

SCHEMAS = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
VIERNES = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
TOKEN = {"X-Internal-Token": get_settings().internal_token}
INEXISTENTE = "00000000-0000-4000-8000-000000000000"
AMIGOS_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"
CARMEN = "5a5e0000-0000-4000-8000-000000000001"

PUBLICADOR = Draft202012Validator(
    json.loads((SCHEMAS / "publicador.json").read_text(encoding="utf-8")),
    format_checker=Draft202012Validator.FORMAT_CHECKER,
)

NUEVO = {
    "nombre": "Club Ciclista Tahal",
    "tipo": "asociacion",
    "municipio": "Tahal",
    "descripcion": "Salidas en bici los domingos.",
    "telefono": "+34600000999",
    "email": "club@example.org",
}


def _valida(dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in PUBLICADOR.iter_errors(dato)]
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


def _cambiar_estado(db, id: str, estado: str) -> None:
    db.get(Publicador, id).estado = estado
    db.commit()


# --- GET /publicadores --------------------------------------------------------------------


def test_lista_publica_paginada_sin_contacto(api):
    r = api.get("/api/v1/publicadores", params={"size": 100})
    assert r.status_code == 200, r.text
    pagina = r.json()
    assert set(pagina) == {"items", "total", "page", "size"}
    assert pagina["total"] == len(pagina["items"]) >= 4
    nombres = {p["nombre"] for p in pagina["items"]}
    assert {"Amigos de Velefique", "Bar La Plaza"} <= nombres
    for p in pagina["items"]:
        _valida(p)
        assert p["estado"] == "aprobado"
        assert "telefono" not in p and "email" not in p
    amigos = next(p for p in pagina["items"] if p["id"] == AMIGOS_VELEFIQUE)
    assert amigos["fuentes"][0]["canal"] == "facebook"

    r = api.get("/api/v1/publicadores", params={"size": 2, "page": 2})
    assert r.json()["page"] == 2 and len(r.json()["items"]) <= 2 and r.json()["total"] == pagina["total"]


def test_lista_filtra_por_municipio_y_estado(api, db):
    r = api.get("/api/v1/publicadores", params={"municipio": "Velefique"})
    assert [p["nombre"] for p in r.json()["items"]] == ["Amigos de Velefique"]

    _cambiar_estado(db, AMIGOS_VELEFIQUE, "pausado")
    # El público no ve los que no están aprobados, aunque los pida.
    publico = api.get("/api/v1/publicadores", params={"estado": "pausado"}).json()
    assert publico["items"] == [] and publico["total"] == 0
    assert AMIGOS_VELEFIQUE not in {p["id"] for p in api.get("/api/v1/publicadores").json()["items"]}
    # El bot (servicio interno) sí, y con el contacto.
    interno = api.get("/api/v1/publicadores", params={"estado": "pausado"}, headers=TOKEN).json()
    assert [p["id"] for p in interno["items"]] == [AMIGOS_VELEFIQUE]
    _valida(interno["items"][0])
    assert interno["items"][0]["telefono"] == "+34600000101"


def test_lista_estado_invalido_422(api):
    _error(api.get("/api/v1/publicadores", params={"estado": "inventado"}), 422, "validacion")


# --- GET /publicadores/{id} ---------------------------------------------------------------


def test_ficha_publica_e_interna(api):
    r = api.get(f"/api/v1/publicadores/{AMIGOS_VELEFIQUE}")
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["nombre"] == "Amigos de Velefique"
    assert "telefono" not in r.json() and "email" not in r.json()

    r = api.get(f"/api/v1/publicadores/{AMIGOS_VELEFIQUE}", headers=TOKEN)
    _valida(r.json())
    assert r.json()["telefono"] == "+34600000101"
    assert "email" in r.json()


def test_ficha_404(api):
    _error(api.get(f"/api/v1/publicadores/{INEXISTENTE}"), 404, "publicador_no_encontrado")
    _error(api.get("/api/v1/publicadores/no-es-un-uuid"), 404, "publicador_no_encontrado")


def test_ficha_de_solicitado_solo_para_internos(api, db):
    _cambiar_estado(db, AMIGOS_VELEFIQUE, "solicitado")
    _error(api.get(f"/api/v1/publicadores/{AMIGOS_VELEFIQUE}"), 404, "publicador_no_encontrado")
    assert api.get(f"/api/v1/publicadores/{AMIGOS_VELEFIQUE}", headers=TOKEN).status_code == 200


# --- POST /publicadores -------------------------------------------------------------------


def test_alta_queda_solicitado(api):
    r = api.post("/api/v1/publicadores", json=NUEVO, headers=TOKEN)
    assert r.status_code == 201, r.text
    p = r.json()
    _valida(p)
    assert p["estado"] == "solicitado"
    assert p["nivel_confianza"] == 0 and p["aprobaciones"] == 0
    assert p["telefono"] == NUEVO["telefono"] and p["email"] == NUEVO["email"]
    assert p["usuario_id"] is None and p["fuentes"] == []

    ficha = api.get(f"/api/v1/publicadores/{p['id']}", headers=TOKEN)
    assert ficha.json()["nombre"] == NUEVO["nombre"]
    # Aún no es público.
    assert api.get(f"/api/v1/publicadores/{p['id']}").status_code == 404


def test_alta_enlaza_al_usuario_con_ese_telefono(api):
    datos = NUEVO | {"telefono": "+34 600 000 201", "email": None}  # Carmen; se normaliza
    r = api.post("/api/v1/publicadores", json=datos, headers=TOKEN)
    assert r.status_code == 201, r.text
    _valida(r.json())
    assert r.json()["telefono"] == "+34600000201"
    assert r.json()["usuario_id"] == CARMEN


def test_alta_sin_token_401(api):
    _error(api.post("/api/v1/publicadores", json=NUEVO), 401, "token_interno_invalido")
    _error(
        api.post("/api/v1/publicadores", json=NUEVO, headers={"X-Internal-Token": "malo"}),
        401,
        "token_interno_invalido",
    )


def test_alta_duplicada_409(api):
    assert api.post("/api/v1/publicadores", json=NUEVO, headers=TOKEN).status_code == 201
    r = api.post("/api/v1/publicadores", json=NUEVO | {"nombre": "Otro nombre"}, headers=TOKEN)
    _error(r, 409, "publicador_ya_existe")
    assert r.json()["error"]["details"]["publicador_id"]
    # También con uno del seed (Amigos de Velefique).
    _error(
        api.post("/api/v1/publicadores", json=NUEVO | {"telefono": "+34600000101"}, headers=TOKEN),
        409,
        "publicador_ya_existe",
    )


@pytest.mark.parametrize(
    "cambio",
    [
        {"telefono": "600000999"},
        {"telefono": "+0123"},
        {"tipo": "secta"},
        {"nombre": "X"},
        {"email": "no-es-un-email"},
        {"campo_raro": 1},
    ],
)
def test_alta_datos_invalidos_422(api, cambio):
    _error(api.post("/api/v1/publicadores", json=NUEVO | cambio, headers=TOKEN), 422, "validacion")


def test_alta_sin_campos_obligatorios_422(api):
    for campo in ("nombre", "tipo", "municipio", "telefono"):
        datos = {k: v for k, v in NUEVO.items() if k != campo}
        _error(api.post("/api/v1/publicadores", json=datos, headers=TOKEN), 422, "validacion")


def test_alta_municipio_desconocido_422(api):
    r = api.post("/api/v1/publicadores", json=NUEVO | {"municipio": "Madrid"}, headers=TOKEN)
    _error(r, 422, "municipio_no_encontrado")
