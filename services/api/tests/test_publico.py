"""Municipios, lugares y eventos salen de la base de datos (sembrada con los datos de la demo)."""

import json
import math
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from sqlalchemy import func, select

from app.config import get_settings
from app.modelos import Evento, Inscripcion, Lugar
from app.seed import sembrar

SCHEMAS = Path(__file__).resolve().parents[3] / "contracts" / "schemas"
VIERNES = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
RUTA_SOLIDARIA = "1e5d0000-0000-4000-8000-000000000001"
SENES = (37.1983, -2.3447)
TOKEN = {"X-Internal-Token": get_settings().internal_token}
INEXISTENTE = "00000000-0000-4000-8000-000000000000"


def _validador(nombre: str) -> Draft202012Validator:
    esquema = json.loads((SCHEMAS / f"{nombre}.json").read_text(encoding="utf-8"))
    return Draft202012Validator(esquema, format_checker=Draft202012Validator.FORMAT_CHECKER)


EVENTO = _validador("evento")
LUGAR = _validador("lugar")


def _valida(validador: Draft202012Validator, dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validador.iter_errors(dato)]
    assert not errores, "\n".join(errores)


def _distancia(lat1, lon1, lat2, lon2) -> float:
    r = math.radians
    a = math.sin(r(lat2 - lat1) / 2) ** 2 + math.cos(r(lat1)) * math.cos(r(lat2)) * math.sin(r(lon2 - lon1) / 2) ** 2
    return 6371 * 2 * math.asin(math.sqrt(a))


def _fecha(valor: str) -> datetime:
    return datetime.fromisoformat(valor)


def _todos(cliente, **params) -> list[dict]:
    r = cliente.get("/api/v1/eventos", params={"size": 100, **params})
    assert r.status_code == 200, r.text
    for e in r.json()["items"]:
        _valida(EVENTO, e)
    return r.json()["items"]


@pytest.fixture
def api(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


# --- municipios y lugares ---------------------------------------------------------------


def test_municipios_salen_de_la_base(api, db):
    r = api.get("/api/v1/municipios")
    assert r.status_code == 200
    assert {m["nombre"] for m in r.json()} == {
        "Lucainena de las Torres", "Senés", "Velefique", "Uleila del Campo", "Tahal"
    }
    assert set(r.json()[0]) == {"nombre", "lat", "lon"}


def test_sin_datos_no_hay_municipios(cliente):
    assert cliente.get("/api/v1/municipios").json() == []


def test_lugares_paginados_filtrados_y_ficha(api, db):
    todos = api.get("/api/v1/lugares", params={"size": 100}).json()
    assert todos["total"] == db.scalar(select(func.count()).select_from(Lugar)) == 35
    rutas = api.get("/api/v1/lugares", params={"tipo": "ruta", "size": 100}).json()["items"]
    assert rutas and all(i["tipo"] == "ruta" for i in rutas)
    senes = api.get("/api/v1/lugares", params={"municipio": "Senés", "size": 100}).json()["items"]
    assert senes and all(i["municipio"] == "Senés" for i in senes)
    for lugar in rutas + senes:
        _valida(LUGAR, lugar)

    ficha = api.get(f"/api/v1/lugares/{rutas[0]['id']}")
    assert ficha.status_code == 200 and ficha.json() == rutas[0]
    for malo in (INEXISTENTE, "no-es-un-uuid"):
        r = api.get(f"/api/v1/lugares/{malo}")
        assert r.status_code == 404 and r.json()["error"]["code"] == "lugar_no_encontrado"


def test_lugares_por_radio(api):
    items = api.get("/api/v1/lugares", params={"lat": SENES[0], "lon": SENES[1], "radio_km": 3, "size": 100}).json()["items"]
    assert items
    assert all(_distancia(*SENES, i["lat"], i["lon"]) <= 3 for i in items)
    assert "Lucainena de las Torres" not in {i["municipio"] for i in items}


def test_tipo_de_lugar_invalido_da_422(api):
    r = api.get("/api/v1/lugares", params={"tipo": "discoteca"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validacion"


# --- GET /eventos -----------------------------------------------------------------------


def test_eventos_tras_el_seed_paginados_publicados_y_ordenados(api):
    r = api.get("/api/v1/eventos")
    cuerpo = r.json()
    assert set(cuerpo) == {"items", "total", "page", "size"}
    assert cuerpo["total"] == 18 and cuerpo["page"] == 1 and cuerpo["size"] == 20
    items = _todos(api)
    assert len(items) == 18
    assert all(e["estado"] == "publicado" for e in items)
    fechas = [_fecha(e["fecha_inicio"]) for e in items]
    assert fechas == sorted(fechas)
    assert RUTA_SOLIDARIA in {e["id"] for e in items}

    segunda = api.get("/api/v1/eventos", params={"page": 2, "size": 5}).json()
    assert segunda["total"] == 18 and [e["id"] for e in segunda["items"]] == [e["id"] for e in items[5:10]]


def test_publico_solo_ve_publicados(api, db):
    db.get(Evento, RUTA_SOLIDARIA).estado = "en_revision"
    db.commit()
    assert RUTA_SOLIDARIA not in {e["id"] for e in _todos(api)}
    # Aunque pida otro estado, sin token sigue viendo solo los publicados
    assert all(e["estado"] == "publicado" for e in _todos(api, estado="en_revision"))
    # Un servicio interno sí puede pedir otro estado
    r = api.get("/api/v1/eventos", params={"estado": "en_revision"}, headers=TOKEN).json()
    assert [e["id"] for e in r["items"]] == [RUTA_SOLIDARIA]
    # La ficha de un evento no publicado no existe para el público
    assert api.get(f"/api/v1/eventos/{RUTA_SOLIDARIA}").status_code == 404
    assert api.get(f"/api/v1/eventos/{RUTA_SOLIDARIA}", headers=TOKEN).status_code == 200


def test_filtro_por_radio_desde_senes(api):
    items = _todos(api, lat=SENES[0], lon=SENES[1], radio_km=10)
    municipios = {e["municipio"] for e in items}
    # Senés, Velefique (~5 km) y Tahal (~6 km) quedan dentro; Uleila (~12 km) y Lucainena (~19 km) fuera
    assert municipios == {"Senés", "Velefique", "Tahal"}
    assert all(_distancia(*SENES, e["lat"], e["lon"]) <= 10 for e in items)
    fuera = [e for e in _todos(api) if e["id"] not in {i["id"] for i in items}]
    assert fuera and all(_distancia(*SENES, e["lat"], e["lon"]) > 10 for e in fuera)
    assert {e["municipio"] for e in fuera} == {"Uleila del Campo", "Lucainena de las Torres"}

    pagina = api.get("/api/v1/eventos", params={"lat": SENES[0], "lon": SENES[1], "radio_km": 10, "size": 2}).json()
    assert pagina["total"] == len(items) and len(pagina["items"]) == 2


def test_filtro_por_municipio(api):
    items = _todos(api, municipio="Senés")
    assert items and all(e["municipio"] == "Senés" for e in items)
    assert _todos(api, municipio="Madrid") == []


def test_filtro_por_categoria(api):
    items = _todos(api, categoria="deportiva")
    assert items and all(e["categoria"] == "deportiva" for e in items)
    r = api.get("/api/v1/eventos", params={"categoria": "toros"})
    assert r.status_code == 422 and r.json()["error"]["code"] == "validacion"


def test_filtro_por_fechas(api):
    desde, hasta = "2026-11-28T00:00:00+01:00", "2026-11-30T00:00:00+01:00"
    items = _todos(api, desde=desde, hasta=hasta)
    assert RUTA_SOLIDARIA in {e["id"] for e in items}
    assert all(_fecha(desde) <= _fecha(e["fecha_fin"] or e["fecha_inicio"]) for e in items)
    assert all(_fecha(e["fecha_inicio"]) <= _fecha(hasta) for e in items)
    todos = _todos(api)
    esperados = [e for e in todos if _fecha(e["fecha_inicio"]) <= _fecha(hasta)
                 and _fecha(e["fecha_fin"] or e["fecha_inicio"]) >= _fecha(desde)]
    assert [e["id"] for e in items] == [e["id"] for e in esperados]
    assert len(items) < len(todos)
    # Una fecha que no es fecha da 422 con el formato común
    assert api.get("/api/v1/eventos", params={"desde": "mañana"}).json()["error"]["code"] == "validacion"


def test_filtro_por_texto_en_titulo_y_descripcion(api, db):
    titulo = _todos(api, q="ruta solidaria")
    assert [e["id"] for e in titulo] == [RUTA_SOLIDARIA]
    ruta = db.get(Evento, RUTA_SOLIDARIA)
    palabra = "zxqpalabraunica"
    ruta.descripcion = f"{ruta.descripcion} {palabra}"
    db.commit()
    assert [e["id"] for e in _todos(api, q=palabra.upper())] == [RUTA_SOLIDARIA]
    assert _todos(api, q="%") == []


def test_filtro_por_publicador(api, db):
    publicador_id = db.get(Evento, RUTA_SOLIDARIA).publicador_id
    items = _todos(api, publicador_id=publicador_id)
    assert items and all(e["publicador_id"] == publicador_id for e in items)


# --- ficha ------------------------------------------------------------------------------


def test_ficha_valida_contra_el_schema(api, db):
    r = api.get(f"/api/v1/eventos/{RUTA_SOLIDARIA}")
    assert r.status_code == 200
    ficha = r.json()
    _valida(EVENTO, ficha)
    assert ficha["fecha_inicio"] == "2026-11-29T09:00:00+01:00"  # se guarda en UTC, se devuelve en Madrid
    assert ficha["publicador_nombre"] == "Amigos de Velefique"
    assert ficha["origen"]["canal"] == "facebook"
    confirmadas = db.scalar(
        select(func.coalesce(func.sum(Inscripcion.plazas), 0)).where(
            Inscripcion.evento_id == RUTA_SOLIDARIA, Inscripcion.estado == "confirmada"
        )
    )
    assert ficha["inscritos"] == confirmadas > 0


@pytest.mark.parametrize("id_malo", [INEXISTENTE, "no-es-un-uuid", "123"])
def test_ficha_inexistente_da_404_con_formato(api, id_malo):
    r = api.get(f"/api/v1/eventos/{id_malo}")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "evento_no_encontrado"
    assert set(r.json()["error"]) == {"code", "message", "details"}


# --- POST y PATCH -----------------------------------------------------------------------

NUEVO = {
    "titulo": "Taller de pan de pueblo",
    "descripcion": "Amasamos y cocemos en el horno moruno.",
    "categoria": "gastronomia",
    "etiquetas": ["pan", "taller"],
    "municipio": "Tahal",
    "fecha_inicio": "2026-12-13T11:00:00+01:00",
    "fecha_fin": "2026-12-13T13:00:00+01:00",
    "precio_eur": 0,
    "plazas_totales": 12,
}


def test_post_sin_token_da_401_con_formato(api):
    r = api.post("/api/v1/eventos", json=NUEVO)
    assert r.status_code == 401
    assert r.json()["error"]["code"] == "token_interno_invalido"


def test_post_con_token_crea_y_aparece_en_la_ficha(api, db):
    r = api.post("/api/v1/eventos", json=NUEVO, headers=TOKEN)
    assert r.status_code == 201, r.text
    creado = r.json()
    _valida(EVENTO, creado)
    assert creado["fecha_inicio"] == NUEVO["fecha_inicio"]
    assert creado["es_gratuito"] is True and creado["plazas_libres"] == 12 and creado["inscritos"] == 0
    # Sin coordenadas: las del municipio
    assert (creado["lat"], creado["lon"]) == (37.2219, -2.2853)
    assert creado["estado"] == "en_revision" and creado["origen"]["canal"] == "manual"

    ficha = api.get(f"/api/v1/eventos/{creado['id']}", headers=TOKEN)
    assert ficha.status_code == 200 and ficha.json() == creado
    assert db.get(Evento, creado["id"]) is not None


@pytest.mark.parametrize(
    "cambio,codigo",
    [
        ({"categoria": "toros"}, "validacion"),
        ({"titulo": "no"}, "validacion"),
        ({"precio_eur": -1}, "validacion"),
        ({"campo_inventado": 1}, "validacion"),
        ({"municipio": "Madrid"}, "municipio_no_encontrado"),
        ({"publicador_id": INEXISTENTE}, "publicador_no_encontrado"),
        ({"fecha_fin": "2026-12-13T10:00:00+01:00"}, "fechas_invalidas"),
    ],
)
def test_post_invalido_da_422_con_formato(api, cambio, codigo):
    r = api.post("/api/v1/eventos", json=NUEVO | cambio, headers=TOKEN)
    assert r.status_code == 422, r.text
    assert r.json()["error"]["code"] == codigo


def test_patch_solo_cambia_lo_enviado(api):
    antes = api.get(f"/api/v1/eventos/{RUTA_SOLIDARIA}").json()
    r = api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"fecha_inicio": "2026-11-29T10:00:00+01:00"}, headers=TOKEN)
    assert r.status_code == 200, r.text
    despues = r.json()
    _valida(EVENTO, despues)
    assert despues["fecha_inicio"] == "2026-11-29T10:00:00+01:00"
    ignorar = {"fecha_inicio", "actualizado_en"}
    assert {k: v for k, v in despues.items() if k not in ignorar} == {k: v for k, v in antes.items() if k not in ignorar}
    assert api.get(f"/api/v1/eventos/{RUTA_SOLIDARIA}").json() == despues


def test_patch_plazas_y_cancelar(api):
    r = api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"plazas_totales": 50, "estado": "cancelado"}, headers=TOKEN)
    assert r.status_code == 200, r.text
    e = r.json()
    _valida(EVENTO, e)
    assert e["estado"] == "cancelado" and e["plazas_totales"] == 50
    assert e["plazas_libres"] == 50 - e["inscritos"]
    # Un evento cancelado sigue teniendo ficha (los inscritos tienen que verlo), pero sale de la agenda
    assert api.get(f"/api/v1/eventos/{RUTA_SOLIDARIA}").status_code == 200
    assert RUTA_SOLIDARIA not in {x["id"] for x in _todos(api)}


@pytest.mark.parametrize(
    "cuerpo", [{"estado": "publicado"}, {"titulo": None}, {"municipio": "Tahal"}, {"fecha_fin": "2026-11-28T09:00:00+01:00"}]
)
def test_patch_invalido_da_422(api, cuerpo):
    r = api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json=cuerpo, headers=TOKEN)
    assert r.status_code == 422, r.text
    assert "error" in r.json()


def test_patch_sin_token_e_inexistente(api):
    assert api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"titulo": "Otro titulo"}).status_code == 401
    for malo in (INEXISTENTE, "no-es-un-uuid"):
        r = api.patch(f"/api/v1/eventos/{malo}", json={"titulo": "Otro titulo"}, headers=TOKEN)
        assert r.status_code == 404 and r.json()["error"]["code"] == "evento_no_encontrado"


def test_cors_permite_la_app(cliente):
    r = cliente.options(
        "/api/v1/eventos",
        headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "GET"},
    )
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
