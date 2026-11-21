"""Publicadores: lista, ficha y alta (E1.5); aprobar, pausar y fuentes (H2.5-H2.6)."""

import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy import select

from app.config import get_settings
from app.modelos import Notificacion, Publicador, Usuario
from app.seed import sembrar
from tests.test_importar import _cuerpo

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
def api(cliente, db, monkeypatch):
    # Bot caído (sin BOT_URL): los avisos quedan en cola y nada espera a la red.
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    sembrar(db, ahora=VIERNES)
    db.commit()
    yield cliente
    get_settings.cache_clear()


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


# --- Aviso a los moderadores en el alta ---------------------------------------------------------

TEL_MODERADOR = "+34600000779"


def _moderador(db) -> Usuario:
    u = Usuario(nombre="Mod de prueba", rol="moderador", telefono=TEL_MODERADOR)
    db.add(u)
    db.commit()
    return u


def _avisos(db, telefono: str) -> list[Notificacion]:
    db.expire_all()
    return list(db.scalars(select(Notificacion).where(Notificacion.telefono == telefono)).all())


def test_alta_avisa_a_los_moderadores_con_el_bot_caido(api, db):
    _moderador(db)
    r = api.post("/api/v1/publicadores", json=NUEVO, headers=TOKEN)
    assert r.status_code == 201, r.text
    avisos = _avisos(db, TEL_MODERADOR)
    assert len(avisos) == 1 and avisos[0].tipo == "moderacion" and NUEVO["nombre"] in avisos[0].texto
    assert avisos[0].estado_envio == "pendiente"


# --- POST /publicadores/{id}/aprobar ------------------------------------------------------------


def _alta(api) -> str:
    r = api.post("/api/v1/publicadores", json=NUEVO, headers=TOKEN)
    assert r.status_code == 201, r.text
    return r.json()["id"]


def _aprobar(api, id: str, cuerpo: dict | None = None, headers=TOKEN):
    return api.post(f"/api/v1/publicadores/{id}/aprobar", json=cuerpo, headers=headers)


def test_aprobar_publicador_con_nivel_1_obsoleto_queda_a_mano(api, db):
    # Solo hay dos modos: un nivel 1 (web antigua) se guarda como 0, «a mano».
    id = _alta(api)
    r = _aprobar(api, id, {"aprobar": True, "nivel_confianza": 1})
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["estado"] == "aprobado" and r.json()["nivel_confianza"] == 0
    # Ya es público.
    assert api.get(f"/api/v1/publicadores/{id}").status_code == 200
    # Aviso al publicador (no es usuario: va a su teléfono).
    assert any("ya puede publicar" in n.texto and "revisará" in n.texto for n in _avisos(db, NUEVO["telefono"]))
    # Ya aprobado: sin nivel no cambia nada; rechazarlo, 409.
    assert _aprobar(api, id).json()["nivel_confianza"] == 0
    _error(_aprobar(api, id, {"aprobar": False}), 409, "estado_invalido")


def test_aprobar_sin_cuerpo_desde_whatsapp_verificado(api, db):
    id = _alta(api)
    _cambiar_estado(db, id, "whatsapp_verificado")
    r = api.post(f"/api/v1/publicadores/{id}/aprobar", headers=TOKEN)
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "aprobado" and r.json()["nivel_confianza"] == 0


def test_rechazar_publicador(api, db):
    id = _alta(api)
    r = _aprobar(api, id, {"aprobar": False, "motivo": "No es de la zona"})
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["estado"] == "rechazado"
    assert "No es de la zona" in _avisos(db, NUEVO["telefono"])[-1].texto
    _error(_aprobar(api, id), 409, "estado_invalido")


def test_aprobar_errores(api):
    id = _alta(api)
    _error(_aprobar(api, id, headers={}), 401, "no_autenticado")
    _error(_aprobar(api, INEXISTENTE), 404, "publicador_no_encontrado")
    _error(_aprobar(api, id, {"nivel_confianza": 5}), 422, "validacion")
    # Ya aprobado: rechazarlo no procede (se pausa); aprobarlo otra vez solo cambia el nivel.
    _error(_aprobar(api, AMIGOS_VELEFIQUE, {"aprobar": False}), 409, "estado_invalido")


# --- POST /publicadores/{id}/pausar -------------------------------------------------------------

URL_IMPORTAR = "/api/v1/eventos/importar"


def _importar(api, **extra):
    return api.post(URL_IMPORTAR, json=_cuerpo(**extra), headers=TOKEN)


def _pausar(api, id: str, que: str, pausado: bool, headers=TOKEN):
    return api.post(f"/api/v1/publicadores/{id}/pausar", json={"que": que, "pausado": pausado}, headers=headers)


def test_pausar_y_reactivar_publicador(api, db):
    id = _alta(api)
    assert _aprobar(api, id, {"nivel_confianza": 1}).status_code == 200

    r = _pausar(api, id, "publicador", True)
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["estado"] == "pausado"
    _error(_importar(api, url="https://example.org/pausa-1", telefono_publicador=NUEVO["telefono"]),
           403, "publicador_pausado")
    assert "en pausa" in _avisos(db, NUEVO["telefono"])[-1].texto

    r = _pausar(api, id, "publicador", False)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"
    r = _importar(api, url="https://example.org/pausa-2", telefono_publicador=NUEVO["telefono"])
    assert r.status_code == 201, r.text
    assert r.json()["evento"]["publicador_id"] == id


def test_pausar_automatizaciones(api, db):
    r = _pausar(api, AMIGOS_VELEFIQUE, "automatizaciones", True)
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["automatizaciones_pausadas"] is True and r.json()["estado"] == "aprobado"
    r = _pausar(api, AMIGOS_VELEFIQUE, "automatizaciones", False)
    assert r.json()["automatizaciones_pausadas"] is False


def test_pausar_errores(api):
    id = _alta(api)
    _error(_pausar(api, id, "publicador", True, headers={}), 401, "no_autenticado")
    _error(_pausar(api, INEXISTENTE, "publicador", True), 404, "publicador_no_encontrado")
    _error(_pausar(api, id, "todo", True), 422, "validacion")
    _error(_pausar(api, id, "publicador", True), 409, "estado_invalido")  # aún solicitado


# --- POST /publicadores/{id}/fuentes ------------------------------------------------------------

URL_FUENTE = "https://www.facebook.com/club-ciclista-tahal"


def _fuente(api, id: str, canal: str = "facebook", url: str = URL_FUENTE, headers=TOKEN):
    return api.post(f"/api/v1/publicadores/{id}/fuentes", json={"canal": canal, "url": url}, headers=headers)


def test_fuente_asocia_lo_importado_al_publicador(api, db):
    id = _alta(api)
    assert _aprobar(api, id).status_code == 200
    r = _fuente(api, id)
    assert r.status_code == 201, r.text
    _valida(r.json())
    assert [(f["canal"], f["url"], f["activa"]) for f in r.json()["fuentes"]] == [("facebook", URL_FUENTE, True)]

    # Un post de esa página, sin teléfono del remitente: se asocia por la fuente.
    r = _importar(api, url=URL_FUENTE + "/posts/123")
    assert r.status_code == 201, r.text
    assert r.json()["evento"]["publicador_id"] == id


def test_fuente_errores(api):
    id = _alta(api)
    _error(_fuente(api, id, headers={}), 401, "token_interno_invalido")
    _error(_fuente(api, INEXISTENTE), 404, "publicador_no_encontrado")
    _error(_fuente(api, id, canal="whatsapp"), 422, "validacion")
    assert _fuente(api, id).status_code == 201
    _error(_fuente(api, id), 409, "fuente_ya_existe")
    _error(_fuente(api, AMIGOS_VELEFIQUE, url=URL_FUENTE + "/"), 409, "fuente_ya_existe")


# --- Concurrencia (revisión H2) -------------------------------------------------------------------


def test_aprobar_a_la_vez_solo_uno_cambia_y_avisa(api, db, motor):
    """El segundo moderador tenía cargado el publicador aún `solicitado`: el UPDATE condicionado no cambia
    nada, recibe 409 y no sale un segundo aviso."""
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session

    from app.errores import ErrorApi
    from app.rutas.publicadores import AprobarPublicador, aprobar_publicador

    id = _alta(api)
    with Session(bind=motor, expire_on_commit=False) as segundo:
        assert segundo.get(Publicador, id).estado == "solicitado"
        assert _aprobar(api, id, {"nivel_confianza": 1}).status_code == 200
        with pytest.raises(ErrorApi) as error:
            aprobar_publicador(id, BackgroundTasks(), AprobarPublicador(aprobar=False), "otro", segundo)
        assert error.value.status == 409 and error.value.code == "estado_invalido"
    db.expire_all()
    assert db.get(Publicador, id).estado == "aprobado"
    assert len(_avisos(db, NUEVO["telefono"])) == 1


def test_pausar_dos_veces_un_solo_aviso(api, db):
    tel = db.get(Publicador, AMIGOS_VELEFIQUE).telefono
    antes = len(_avisos(db, tel))
    for _ in range(2):
        assert _pausar(api, AMIGOS_VELEFIQUE, "automatizaciones", True).status_code == 200
        assert _pausar(api, AMIGOS_VELEFIQUE, "publicador", True).json()["estado"] == "pausado"
    assert len(_avisos(db, tel)) - antes == 2


def test_publicador_rechazado_no_importa(api, db):
    id = _alta(api)
    assert _aprobar(api, id, {"aprobar": False}).status_code == 200
    _error(_importar(api, url="https://example.org/rechazado", telefono_publicador=NUEVO["telefono"]),
           403, "publicador_rechazado")
