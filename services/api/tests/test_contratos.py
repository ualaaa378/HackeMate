"""Contratos v1: los fixtures validan contra los schemas y openapi.yaml tiene los endpoints de PLAN.md §5.2."""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from ruamel.yaml import YAML

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"
SCHEMAS = CONTRATOS / "schemas"
FIXTURES = CONTRATOS / "fixtures"

SCHEMAS_V1 = [
    "evento",
    "extraccion_evento",
    "usuario",
    "publicador",
    "inscripcion",
    "mensaje_evento",
    "notificacion",
    "lugar",
]

# fixture → schema de cada elemento (None = sin schema de entidad propio)
FIXTURE_SCHEMA = {
    "eventos.json": "evento",
    "eventos_demo.json": "evento",
    "eventos_pasados.json": "evento",
    "lugares.json": "lugar",
    "extraccion_evento.json": "extraccion_evento",
    "usuarios.json": "usuario",
    "publicadores.json": "publicador",
    "inscripciones.json": "inscripcion",
    "inscripciones_pasadas.json": "inscripcion",
    "mensajes_evento.json": "mensaje_evento",
    "notificaciones.json": "notificacion",
    "municipios.json": None,
    # Posts descargados por scripts/importar_facebook.py (A2): no es un schema del contrato.
    "facebook_posts.json": None,
}

# Tabla de PLAN.md §5.2
ENDPOINTS_PLAN = [
    ("get", "/api/v1/eventos"),
    ("get", "/api/v1/eventos/{id}"),
    ("post", "/api/v1/eventos"),
    ("patch", "/api/v1/eventos/{id}"),
    ("post", "/api/v1/eventos/importar"),
    ("post", "/api/v1/eventos/{id}/confirmar"),
    ("post", "/api/v1/eventos/{id}/inscripciones"),
    ("delete", "/api/v1/eventos/{id}/inscripciones/{insc_id}"),
    ("get", "/api/v1/eventos/{id}/mensajes"),
    ("post", "/api/v1/eventos/{id}/mensajes"),
    ("get", "/api/v1/eventos/{id}/ics"),
    ("get", "/api/v1/usuarios/me/ics"),
    ("get", "/api/v1/recomendaciones"),
    ("get", "/api/v1/moderacion/pendientes"),
    ("post", "/api/v1/moderacion/{id}/decision"),
    ("post", "/api/v1/publicadores"),
    ("post", "/api/v1/publicadores/{id}/aprobar"),
    ("post", "/api/v1/publicadores/{id}/fuentes"),
    ("post", "/api/v1/auth/google"),
    ("post", "/api/v1/auth/whatsapp/codigo"),
    ("post", "/api/v1/auth/whatsapp/verificar"),
    ("get", "/api/v1/usuarios/by-phone/{e164}"),
    ("patch", "/api/v1/usuarios/me"),
    ("get", "/api/v1/estadisticas"),
    ("post", "/api/v1/metrics/tokens"),
    ("post", "/webhook/twilio"),
    ("post", "/notify"),
    ("post", "/ai/extraer"),
    ("post", "/ai/spam"),
    ("post", "/ai/responder-ficha"),
    ("post", "/ai/preferencias"),
    ("get", "/health"),
]


def _json(ruta: Path):
    return json.loads(ruta.read_text(encoding="utf-8"))


def _validador(nombre: str) -> Draft202012Validator:
    return Draft202012Validator(_json(SCHEMAS / f"{nombre}.json"), format_checker=Draft202012Validator.FORMAT_CHECKER)


@pytest.fixture(scope="module")
def openapi():
    return YAML(typ="safe").load((CONTRATOS / "openapi.yaml").read_text(encoding="utf-8"))


@pytest.mark.parametrize("nombre", SCHEMAS_V1)
def test_schema_existe_y_es_valido(nombre):
    ruta = SCHEMAS / f"{nombre}.json"
    assert ruta.exists(), f"Falta {ruta.name}"
    Draft202012Validator.check_schema(_json(ruta))


def test_todos_los_fixtures_tienen_schema_asignado():
    sin_asignar = {p.name for p in FIXTURES.glob("*.json")} - set(FIXTURE_SCHEMA)
    assert not sin_asignar, f"Añade estos fixtures a FIXTURE_SCHEMA: {sin_asignar}"


def test_cada_schema_tiene_algun_fixture():
    assert set(SCHEMAS_V1) <= {s for s in FIXTURE_SCHEMA.values() if s}


@pytest.mark.parametrize("fixture,schema", [(f, s) for f, s in FIXTURE_SCHEMA.items() if s])
def test_fixture_valida_contra_schema(fixture, schema):
    datos = _json(FIXTURES / fixture)
    elementos = datos if isinstance(datos, list) else [datos]
    assert elementos, f"{fixture} está vacío"
    validador = _validador(schema)
    errores = [
        f"[{i}] {'/'.join(map(str, e.absolute_path))}: {e.message}"
        for i, el in enumerate(elementos)
        for e in validador.iter_errors(el)
    ]
    assert not errores, f"{fixture} no valida contra {schema}.json:\n" + "\n".join(errores)


def test_municipios():
    nombres = {m["nombre"] for m in _json(FIXTURES / "municipios.json")}
    assert nombres == {"Lucainena de las Torres", "Senés", "Velefique", "Uleila del Campo", "Tahal"}


def test_fixtures_coherentes_entre_si():
    publicadores = {p["id"] for p in _json(FIXTURES / "publicadores.json")}
    usuarios = {u["id"] for u in _json(FIXTURES / "usuarios.json")}
    eventos = _json(FIXTURES / "eventos.json") + _json(FIXTURES / "eventos_demo.json")
    ids_eventos = {e["id"] for e in eventos}
    assert len(ids_eventos) == len(eventos), "IDs de evento repetidos entre eventos.json y eventos_demo.json"
    municipios = {m["nombre"] for m in _json(FIXTURES / "municipios.json")}

    # Los eventos reales aún no tienen publicador dado de alta (publicador_id = null)
    for e in eventos:
        assert e["publicador_id"] is None or e["publicador_id"] in publicadores, e["titulo"]
        assert e["municipio"] in municipios, e["titulo"]
    for lugar in _json(FIXTURES / "lugares.json"):
        assert lugar["municipio"] in municipios, lugar["nombre"]
    for i in _json(FIXTURES / "inscripciones.json"):
        assert i["evento_id"] in ids_eventos and i["usuario_id"] in usuarios
    for m in _json(FIXTURES / "mensajes_evento.json"):
        assert m["evento_id"] in ids_eventos

    # Histórico del panel (H4.3): actividades ya celebradas y su asistencia
    pasados = _json(FIXTURES / "eventos_pasados.json")
    ids_pasados = {e["id"] for e in pasados}
    assert len(ids_pasados) == len(pasados) and not ids_pasados & ids_eventos
    for e in pasados:
        assert e["estado"] == "finalizado", e["titulo"]
        assert e["publicador_id"] is None or e["publicador_id"] in publicadores, e["titulo"]
        assert e["municipio"] in municipios, e["titulo"]
    parejas = set()
    for i in _json(FIXTURES / "inscripciones_pasadas.json"):
        assert i["evento_id"] in ids_pasados and i["usuario_id"] in usuarios
        assert (i["evento_id"], i["usuario_id"]) not in parejas
        parejas.add((i["evento_id"], i["usuario_id"]))


def test_extraccion_ruta_solidaria_lista_lo_que_falta():
    ruta = _json(FIXTURES / "extraccion_evento.json")[0]
    assert set(ruta["faltan"]) == {"plazas_totales", "lugar"}


def test_openapi_tiene_los_endpoints_del_plan(openapi):
    assert openapi["openapi"].startswith("3.1")
    faltan = [f"{m.upper()} {r}" for m, r in ENDPOINTS_PLAN if m not in openapi["paths"].get(r, {})]
    assert not faltan, "Endpoints de PLAN.md §5.2 que faltan en openapi.yaml:\n" + "\n".join(faltan)


def test_openapi_referencias_resuelven(openapi):
    componentes = openapi["components"]["schemas"]
    rotas = []

    def recorrer(nodo):
        if isinstance(nodo, dict):
            ref = nodo.get("$ref")
            if isinstance(ref, str):
                if ref.startswith("./"):
                    if not (CONTRATOS / ref[2:]).exists():
                        rotas.append(ref)
                elif ref.startswith("#/components/"):
                    _, _, tipo, nombre = ref.split("/", 3)
                    if nombre not in openapi["components"].get(tipo, {}):
                        rotas.append(ref)
            for v in nodo.values():
                recorrer(v)
        elif isinstance(nodo, list):
            for v in nodo:
                recorrer(v)

    recorrer(openapi)
    assert componentes
    assert not rotas, f"$ref rotas: {sorted(set(rotas))}"


def test_openapi_enums_coinciden_con_schemas(openapi):
    evento = _json(SCHEMAS / "evento.json")["properties"]
    comp = openapi["components"]["schemas"]
    assert comp["Categoria"]["enum"] == evento["categoria"]["enum"]
    assert comp["EstadoEvento"]["enum"] == evento["estado"]["enum"]
