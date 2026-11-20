"""POST /eventos/importar (E1.6): el bot entrega una ExtraccionEvento + origen."""

import copy
import json
from datetime import datetime, timezone
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from ruamel.yaml import YAML
from sqlalchemy import func, select

from app.config import get_settings
from app.modelos import Evento, Publicador
from app.seed import sembrar

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"
VIERNES = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
TOKEN = {"X-Internal-Token": get_settings().internal_token}
URL = "/api/v1/eventos/importar"
AMIGOS_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"
BAR_LA_PLAZA = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a03"
URL_POST = "https://example.org/posts/ruta-solidaria"


def _validador_resultado() -> Draft202012Validator:
    """components/schemas/ResultadoImportacion de openapi.yaml, con sus $ref a ./schemas/*.json."""
    openapi = YAML(typ="safe").load((CONTRATOS / "openapi.yaml").read_text(encoding="utf-8"))
    componentes = json.loads(json.dumps(openapi["components"]["schemas"]))
    recursos = [
        (f"./schemas/{f.name}", Resource.from_contents(json.loads(f.read_text(encoding="utf-8"))))
        for f in (CONTRATOS / "schemas").glob("*.json")
    ]
    raiz = {"$schema": "https://json-schema.org/draft/2020-12/schema", "components": {"schemas": componentes}}
    recursos.append(("urn:openapi", Resource.from_contents(raiz)))
    esquema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": "urn:openapi#/components/schemas/ResultadoImportacion"}
    # Los $ref relativos (./schemas/x.json) dentro de urn:openapi se resuelven contra el registro.
    registro = Registry().with_resources(recursos)
    return Draft202012Validator(esquema, registry=registro, format_checker=Draft202012Validator.FORMAT_CHECKER)


RESULTADO = _validador_resultado()


def _valida(dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in RESULTADO.iter_errors(dato)]
    assert not errores, "\n".join(errores)


def _error(r, status: int, code: str) -> None:
    assert r.status_code == status, r.text
    cuerpo = r.json()
    assert set(cuerpo) == {"error"}
    assert cuerpo["error"]["code"] == code
    assert {"code", "message", "details"} <= set(cuerpo["error"])


def _extraccion() -> dict:
    return copy.deepcopy(json.loads((CONTRATOS / "fixtures" / "extraccion_evento.json").read_text(encoding="utf-8"))[0])


def _cuerpo(url: str | None = URL_POST, **extra) -> dict:
    return {
        "extraccion": _extraccion(),
        "origen": {"canal": "whatsapp", "url": url, "importado_auto": False},
        **extra,
    }


@pytest.fixture
def api(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


def test_resolutor_de_refs_funciona():
    # Si el $ref a evento.json no se resolviera, cualquier cosa validaría.
    assert list(RESULTADO.iter_errors({"evento": {}, "faltan": [], "duplicado": False}))


def test_importa_la_ruta_solidaria(api, db):
    r = api.post(URL, json=_cuerpo(), headers=TOKEN)
    assert r.status_code == 201, r.text
    datos = r.json()
    _valida(datos)
    assert datos["duplicado"] is False
    assert sorted(datos["faltan"]) == ["lugar", "plazas_totales"]
    evento = datos["evento"]
    assert evento["estado"] == "pendiente_confirmacion"
    assert evento["titulo"] == "II Ruta Solidaria Sierra de Velefique"
    assert evento["categoria"] == "deportiva"
    assert evento["municipio"] == "Velefique"
    assert evento["fecha_inicio"] == "2026-11-29T09:00:00+01:00"
    assert evento["precio_eur"] == 5.0 and evento["es_gratuito"] is False
    assert evento["lugar"] is None and evento["plazas_totales"] is None
    assert evento["origen"] == {"canal": "whatsapp", "url": URL_POST, "importado_auto": False}
    assert evento["publicador_id"] is None
    # Lat/lon del municipio
    assert evento["lat"] and evento["lon"]
    guardado = db.get(Evento, evento["id"])
    db.refresh(guardado)
    assert guardado.extraccion["proveedor_ia"] == "gemini-2.5-flash"
    assert sorted(guardado.faltan) == ["lugar", "plazas_totales"]


@pytest.mark.parametrize("campo", ["fecha_inicio", "categoria"])
def test_extraccion_incompleta(api, campo):
    cuerpo = _cuerpo()
    cuerpo["extraccion"]["campos"][campo] = {"valor": None, "confianza": "falta"}
    r = api.post(URL, json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    _valida(r.json())
    assert campo in r.json()["faltan"]
    assert r.json()["evento"]["estado"] == "pendiente_confirmacion"


def test_sin_campos_rellena_provisional_y_lista_obligatorios(api):
    cuerpo = _cuerpo()
    cuerpo["extraccion"]["campos"] = {"municipio": {"valor": "SENES", "confianza": "media"}}
    cuerpo["extraccion"]["faltan"] = []
    r = api.post(URL, json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    _valida(r.json())
    assert r.json()["faltan"] == ["titulo", "categoria", "fecha_inicio"]
    assert r.json()["evento"]["municipio"] == "Senés"


def test_categoria_fuera_del_enum_cuenta_como_falta(api):
    cuerpo = _cuerpo()
    cuerpo["extraccion"]["campos"]["categoria"] = {"valor": "senderismo", "confianza": "media"}
    r = api.post(URL, json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    assert "categoria" in r.json()["faltan"]


def test_mismo_origen_url_devuelve_el_existente(api, db):
    primero = api.post(URL, json=_cuerpo(), headers=TOKEN)
    assert primero.status_code == 201, primero.text
    segundo = api.post(URL, json=_cuerpo(), headers=TOKEN)
    assert segundo.status_code == 200, segundo.text
    _valida(segundo.json())
    assert segundo.json()["duplicado"] is True
    assert segundo.json()["evento"]["id"] == primero.json()["evento"]["id"]
    assert sorted(segundo.json()["faltan"]) == ["lugar", "plazas_totales"]
    assert db.scalar(select(func.count()).select_from(Evento).where(Evento.origen_url == URL_POST)) == 1


def test_sin_url_no_se_considera_duplicado(api):
    a = api.post(URL, json=_cuerpo(url=None), headers=TOKEN)
    b = api.post(URL, json=_cuerpo(url=""), headers=TOKEN)
    assert a.status_code == b.status_code == 201
    assert a.json()["evento"]["id"] != b.json()["evento"]["id"]


def test_asocia_por_telefono(api):
    r = api.post(URL, json=_cuerpo(telefono_publicador="+34 600 000 101"), headers=TOKEN)
    assert r.status_code == 201, r.text
    assert r.json()["evento"]["publicador_id"] == AMIGOS_VELEFIQUE
    assert r.json()["evento"]["publicador_nombre"] == "Amigos de Velefique"


def test_asocia_por_fuente_antes_que_por_telefono(api):
    url = "https://www.instagram.com/barlaplazasenes/p/abc123"
    r = api.post(URL, json=_cuerpo(url=url, telefono_publicador="+34600000101"), headers=TOKEN)
    assert r.status_code == 201, r.text
    assert r.json()["evento"]["publicador_id"] == BAR_LA_PLAZA


def test_publicador_pausado_403(api, db):
    db.get(Publicador, AMIGOS_VELEFIQUE).estado = "pausado"
    db.commit()
    r = api.post(URL, json=_cuerpo(telefono_publicador="+34600000101"), headers=TOKEN)
    _error(r, 403, "publicador_pausado")
    assert db.scalar(select(func.count()).select_from(Evento).where(Evento.origen_url == URL_POST)) == 0


def test_sin_token_401(api):
    _error(api.post(URL, json=_cuerpo()), 401, "token_interno_invalido")
    _error(api.post(URL, json=_cuerpo(), headers={"X-Internal-Token": "malo"}), 401, "token_interno_invalido")


@pytest.mark.parametrize(
    "romper",
    [
        lambda c: c.pop("origen"),
        lambda c: c["extraccion"].pop("es_evento"),
        lambda c: c["origen"].update(canal="sms"),
        lambda c: c["extraccion"]["campos"]["titulo"].update(confianza="mucha"),
        lambda c: c.update(telefono_publicador="600"),
        lambda c: c.update(telefono_publicador="tg:abc"),
        lambda c: c.update(contacto_publicador="hola"),
    ],
)
def test_cuerpo_invalido_422(api, romper):
    cuerpo = _cuerpo()
    romper(cuerpo)
    _error(api.post(URL, json=cuerpo, headers=TOKEN), 422, "validacion")


def test_no_sale_en_lo_publico(api):
    r = api.post(URL, json=_cuerpo(), headers=TOKEN)
    id = r.json()["evento"]["id"]
    lista = api.get("/api/v1/eventos", params={"size": 100}).json()
    assert id not in {e["id"] for e in lista["items"]}
    lista = api.get("/api/v1/eventos", params={"size": 100, "estado": "pendiente_confirmacion"}).json()
    assert id not in {e["id"] for e in lista["items"]}
    _error(api.get(f"/api/v1/eventos/{id}"), 404, "evento_no_encontrado")
    # El bot sí la ve
    assert api.get(f"/api/v1/eventos/{id}", headers=TOKEN).status_code == 200


def test_campos_desconocidos_se_ignoran(api):
    # Un campo opcional nuevo en el contrato no debe romper al bot.
    cuerpo = _cuerpo(url="https://www.facebook.com/campo-nuevo/1", sobra=1)
    cuerpo["extraccion"]["campo_futuro"] = "x"
    r = api.post(URL, json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
