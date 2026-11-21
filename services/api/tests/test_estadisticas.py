"""Panel del moderador (H4.1-H4.3): GET /estadisticas y POST /metrics/tokens con el seed de la demo.

Ventana de agosto a mediados de noviembre de 2026: solo entra el histórico de eventos_pasados.json (los eventos
reales de esas fechas ya terminados no los carga el seed), así que las cifras se pueden contar a mano:

| evento (pueblo, categoría)            | aforo/libres | inscritas (asistieron)  | de otro pueblo |
|---------------------------------------|--------------|-------------------------|----------------|
| 1 Cine de verano (Uleila, cultural)   | 120/35       | 4 (3)                   | 4              |
| 2 Verbena (Senés, fiestas)            | -            | -                       | -              |
| 3 Senderismo (Velefique, deportiva)   | 30/4         | 4 (4)                   | 3              |
| 4 Taller de migas (Senés, gastronomía)| 20/2         | 4 (3)                   | 3              |
| 5 Petanca (Tahal, lúdica)             | 24/10        | 4 (2)                   | 3              |
| 6 Mercadillo (Lucainena, comercio)    | -            | -                       | -              |
| 7 Concierto (Lucainena, cultural)     | 80/22        | 5 (4)                   | 5              |
| 8 Juegos (Uleila, lúdica)             | 30/12        | 1 (0) + 1 cancelada     | 1              |
"""

import json

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from ruamel.yaml import YAML

from app.config import Settings, get_settings
from app.estadisticas import coste_eur, fin_estimado
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import CONTRATOS, TOKEN, VIERNES, _error

URL = "/api/v1/estadisticas"
URL_METRICAS = "/api/v1/metrics/tokens"
CINE = "4a5a0000-0000-4000-8000-000000000001"
VERBENA = "4a5a0000-0000-4000-8000-000000000002"
PETANCA = "4a5a0000-0000-4000-8000-000000000005"
JUEGOS = "4a5a0000-0000-4000-8000-000000000008"
CABALGATA_LUCAINENA = "9d7e4f77"
CABALGATA_ULEILA = "4de907b4"
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
LUCIA_MODERADORA = "5a5e0000-0000-4000-8000-000000000002"
HISTORICO = {"desde": "2026-08-01T00:00:00+02:00", "hasta": "2026-11-15T00:00:00+01:00"}


def _openapi() -> dict:
    return json.loads(json.dumps(YAML(typ="safe").load((CONTRATOS / "openapi.yaml").read_text(encoding="utf-8"))))


def _validador(puntero: str) -> Draft202012Validator:
    """Schema de openapi.yaml en `puntero`, con sus $ref (internos y ./schemas/*.json) resueltos."""
    recursos = [
        (f"./schemas/{f.name}", Resource.from_contents(json.loads(f.read_text(encoding="utf-8"))))
        for f in (CONTRATOS / "schemas").glob("*.json")
    ]
    raiz = {"$schema": "https://json-schema.org/draft/2020-12/schema", **_openapi()}
    recursos.append(("urn:openapi", Resource.from_contents(raiz)))
    esquema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": f"urn:openapi#{puntero}"}
    registro = Registry().with_resources(recursos)
    return Draft202012Validator(esquema, registry=registro, format_checker=Draft202012Validator.FORMAT_CHECKER)


RESPUESTA = _validador("/paths/~1api~1v1~1estadisticas/get/responses/200/content/application~1json/schema")
METRICA = _validador("/components/schemas/MetricaTokens")


def _valida(validador: Draft202012Validator, dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validador.iter_errors(dato)]
    assert not errores, "\n".join(errores)


def _bearer(usuario_id: str, rol: str) -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, rol)}"}


def _metrica(proveedor="claude", modelo="claude-opus-5-5", entrada=1000, salida=2000, ts=None, **extra) -> dict:
    """Igual que el `registro` de services/bot/app/metrics.py."""
    return {
        "proveedor": proveedor,
        "modelo": modelo,
        "tarea": "extraer",
        "tokens_entrada": entrada,
        "tokens_salida": salida,
        "latencia_ms": 850,
        "ok": True,
        "ts": ts if ts is not None else VIERNES.timestamp(),
        **extra,
    }


@pytest.fixture
def api(cliente, db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


@pytest.fixture
def precios(monkeypatch):
    tabla = {
        "gemini": {"entrada": 0, "salida": 0},
        "freellm": {"entrada": 0, "salida": 0},
        "reglas": {"entrada": 0, "salida": 0},
        "claude": {"entrada": 5.0, "salida": 25.0},
    }
    monkeypatch.setattr(get_settings(), "precios_tokens_eur_mtok", tabla)
    return tabla


# --- Cifras con el seed ---------------------------------------------------------------------------


def test_historico_cuadra_con_el_seed(api):
    r = api.get(URL, params=HISTORICO, headers=TOKEN)
    assert r.status_code == 200, r.text
    datos = r.json()
    _valida(RESPUESTA, datos)
    assert datos["periodo"] == HISTORICO
    assert datos["actividades"] == 8
    assert datos["pct_importadas_auto"] == 62.5  # 5 de 8 llegaron solas (Facebook, Instagram, web)
    assert datos["inscripciones"] == 22 and datos["asistencias"] == 16
    assert datos["pct_otro_pueblo"] == pytest.approx(100 * 19 / 22, abs=0.05)
    assert datos["ocupacion_por_categoria"] == {
        "cultural": pytest.approx(143 / 200, abs=1e-3),
        "deportiva": pytest.approx(26 / 30, abs=1e-3),
        "gastronomia": pytest.approx(18 / 20, abs=1e-3),
        "ludica": pytest.approx(32 / 54, abs=1e-3),
    }
    assert all(0 <= v <= 1 for v in datos["ocupacion_por_categoria"].values())
    assert datos["asistencias"] <= datos["inscripciones"]
    pares = {(s["evento_a"], s["evento_b"]) for s in datos["solapamientos"]}
    assert pares == {(VERBENA, CINE), (PETANCA, JUEGOS)}
    # Las métricas de tokens del periodo: ninguna (no se ha registrado nada)
    assert datos["tokens"] == {"por_proveedor": {}, "coste_total_eur": 0.0}


def test_sin_desde_solo_los_choques_que_no_han_pasado(api):
    # N5a: sin periodo, el panel enseña los choques que aún pueden arreglarse (las dos cabalgatas de Reyes),
    # no los del verano o el otoño que ya pasaron. Las cifras sí siguen contando todo.
    datos = api.get(URL, headers=TOKEN).json()
    _valida(RESPUESTA, datos)
    ids = {i for s in datos["solapamientos"] for i in (s["evento_a"], s["evento_b"])}
    assert not ids & {CINE, VERBENA, PETANCA, JUEGOS}
    assert any(
        {s["evento_a"][:8], s["evento_b"][:8]} == {CABALGATA_LUCAINENA, CABALGATA_ULEILA}
        for s in datos["solapamientos"]
    )
    assert datos["actividades"] == 18 + 8


def test_solapamiento_de_demo_cine_de_uleila_con_fiestas(api):
    datos = api.get(URL, params={"desde": "2026-01-01T00:00:00+01:00"}, headers=TOKEN).json()
    _valida(RESPUESTA, datos)
    cine = [s for s in datos["solapamientos"] if CINE in (s["evento_a"], s["evento_b"])]
    assert len(cine) == 1
    assert cine[0]["motivo"].startswith(
        "«Cine de verano en Uleila del Campo» (Uleila del Campo) coincide con «Verbena de verano en Senés» (Senés)"
    )
    assert "fiestas" in cine[0]["motivo"]
    petanca = next(s for s in datos["solapamientos"] if PETANCA in (s["evento_a"], s["evento_b"]))
    assert "misma categoría (ludica)" in petanca["motivo"]
    # Las dos cabalgatas de Reyes (Lucainena y Uleila, 5 de enero, sin hora) también coinciden
    assert any(
        {s["evento_a"][:8], s["evento_b"][:8]} == {CABALGATA_LUCAINENA, CABALGATA_ULEILA}
        for s in datos["solapamientos"]
    )
    # Desde enero entran también los publicados que vienen y los finalizados; nada en revisión
    assert datos["actividades"] == 18 + 8


def test_filtro_por_municipio(api):
    datos = api.get(URL, params=HISTORICO | {"municipio": "Senés"}, headers=TOKEN).json()
    _valida(RESPUESTA, datos)
    assert datos["actividades"] == 2  # verbena y taller de migas
    assert datos["pct_importadas_auto"] == 100.0
    assert datos["inscripciones"] == 4 and datos["asistencias"] == 3
    assert datos["pct_otro_pueblo"] == 75.0  # José (Tahal, 2) y Antonio (Velefique, 1) de 4
    assert datos["ocupacion_por_categoria"] == {"gastronomia": 0.9}
    assert [(s["evento_a"], s["evento_b"]) for s in datos["solapamientos"]] == [(VERBENA, CINE)]


def test_periodo_sin_actividades_da_ceros(api):
    datos = api.get(URL, params={"desde": "2030-01-01T00:00:00+01:00"}, headers=TOKEN).json()
    _valida(RESPUESTA, datos)
    assert datos["actividades"] == 0 and datos["inscripciones"] == 0
    assert datos["pct_importadas_auto"] == 0.0 and datos["pct_otro_pueblo"] == 0.0
    assert datos["ocupacion_por_categoria"] == {} and datos["solapamientos"] == []


def test_fecha_sin_zona_se_entiende_en_hora_de_madrid(api):
    datos = api.get(URL, params={"desde": "2026-08-01T00:00:00"}, headers=TOKEN).json()
    assert datos["periodo"]["desde"] == "2026-08-01T00:00:00+02:00"


def _importadas(datos: dict) -> int:
    return round(datos["pct_importadas_auto"] * datos["actividades"] / 100)


def _importar_y_confirmar(api, titulo: str, canal: str, publicador_id: str, url: str | None) -> dict:
    """Lo mismo que hacen scripts/importar_facebook.py (canal facebook) y el bot (telegram)."""
    from tests.test_importar import _extraccion

    extraccion = _extraccion()
    extraccion["campos"]["titulo"]["valor"] = titulo
    cuerpo = {
        "extraccion": extraccion,
        "origen": {"canal": canal, "url": url, "importado_auto": canal == "facebook"},
        "publicador_id": publicador_id,
    }
    r = api.post("/api/v1/eventos/importar", json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    id_ = r.json()["evento"]["id"]
    r = api.post(f"/api/v1/eventos/{id_}/confirmar", json={"campos": {}}, headers=TOKEN)
    assert r.status_code == 200, r.text
    return r.json()["evento"]


def test_lo_importado_de_facebook_cuenta_en_el_porcentaje(api):
    """A4: lo que entra por la ingesta de Facebook sube `pct_importadas_auto` (tras aprobarlo, D4); lo de Telegram, no."""
    antes = api.get(URL, headers=TOKEN).json()

    ayto = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a02"  # Ayto. Lucainena, automática
    fb = _importar_y_confirmar(api, "Mercadillo navideño", "facebook", ayto, "https://www.facebook.com/p/1")
    assert fb["estado"] == "en_revision" and fb["origen"]["importado_auto"] is True  # D4: siempre a la bandeja
    assert api.get(URL, headers=TOKEN).json()["actividades"] == antes["actividades"]
    r = api.post(f"/api/v1/moderacion/{fb['id']}/decision", json={"decision": "aprobar", "motivo": None},
                 headers=_bearer(LUCIA_MODERADORA, "moderador"))
    assert r.status_code == 200, r.text
    tg = _importar_y_confirmar(api, "Taller de belenes", "telegram", ayto, None)
    assert tg["estado"] == "publicado" and tg["origen"]["importado_auto"] is False

    despues = api.get(URL, headers=TOKEN).json()
    _valida(RESPUESTA, despues)
    assert despues["actividades"] == antes["actividades"] + 2
    assert _importadas(despues) == _importadas(antes) + 1

    # Un post de Facebook de una asociación «a mano» no cuenta hasta que el moderador lo aprueba
    amigos = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"
    revision = _importar_y_confirmar(api, "Concierto de villancicos", "facebook", amigos, "https://www.facebook.com/p/2")
    assert revision["estado"] == "en_revision"
    assert api.get(URL, headers=TOKEN).json()["actividades"] == despues["actividades"]

    r = api.post(f"/api/v1/moderacion/{revision['id']}/decision", json={"decision": "aprobar", "motivo": None},
                 headers=_bearer(LUCIA_MODERADORA, "moderador"))
    assert r.status_code == 200, r.text
    final = api.get(URL, headers=TOKEN).json()
    assert final["actividades"] == despues["actividades"] + 1
    assert _importadas(final) == _importadas(despues) + 1


def test_rechazados_y_en_revision_no_cuentan(api, db):
    from app.modelos import Evento

    antes = api.get(URL, headers=TOKEN).json()["actividades"]
    db.add(Evento(titulo="Rechazado", categoria="ludica", municipio="Tahal", lat=37.2, lon=-2.28,
                  fecha_inicio=VIERNES, estado="rechazado"))
    db.commit()
    assert api.get(URL, headers=TOKEN).json()["actividades"] == antes


def test_fin_estimado():
    from datetime import datetime, timedelta, timezone
    from zoneinfo import ZoneInfo

    madrid = ZoneInfo("Europe/Madrid")
    sin_hora = datetime(2027, 1, 5, 0, 0, tzinfo=madrid)
    assert fin_estimado(sin_hora, None, madrid) == datetime(2027, 1, 6, 0, 0, tzinfo=madrid)
    con_hora = datetime(2026, 11, 28, 12, 0, tzinfo=madrid).astimezone(timezone.utc)
    assert fin_estimado(con_hora, None, madrid) == con_hora + timedelta(hours=2)
    assert fin_estimado(con_hora, con_hora + timedelta(hours=5), madrid) == con_hora + timedelta(hours=5)


# --- Permisos -----------------------------------------------------------------------------------


def test_permisos_estadisticas(api):
    _error(api.get(URL), 401, "no_autenticado")
    _error(api.get(URL, headers=_bearer(CARMEN, "vecino")), 403, "rol_insuficiente")
    assert api.get(URL, headers=_bearer(LUCIA_MODERADORA, "moderador")).status_code == 200
    assert api.get(URL, headers=TOKEN).status_code == 200


def test_permisos_metricas(api):
    _error(api.post(URL_METRICAS, json=_metrica()), 401, "token_interno_invalido")
    _error(api.post(URL_METRICAS, json=_metrica(), headers={"X-Internal-Token": "otro"}), 401, "token_interno_invalido")
    moderadora = _bearer(LUCIA_MODERADORA, "moderador")
    _error(api.post(URL_METRICAS, json=_metrica(), headers=moderadora), 401, "token_interno_invalido")


# --- Tokens y coste -----------------------------------------------------------------------------


def test_metrica_del_bot_valida_contra_el_contrato():
    _valida(METRICA, _metrica())


def test_conversacion_con_el_bot_sube_el_coste(api, precios):
    antes = api.get(URL, headers=TOKEN).json()["tokens"]
    assert antes["coste_total_eur"] == 0.0

    # Gemini falla una vez, responde, y luego Claude remata: lo que mandaría el bot en una conversación
    for cuerpo in (
        _metrica("gemini", "gemini-2.5-flash", 0, 0, ok=False),
        _metrica("gemini", "gemini-2.5-flash", 500, 100),
        _metrica("claude", "claude-opus-5-5", 1000, 2000),
        _metrica("reglas", "reglas", 0, 0),
    ):
        r = api.post(URL_METRICAS, json=cuerpo, headers=TOKEN)
        assert r.status_code == 202, r.text

    tokens = api.get(URL, headers=_bearer(LUCIA_MODERADORA, "moderador")).json()["tokens"]
    assert tokens["por_proveedor"]["gemini"] == {"llamadas": 2, "entrada": 500, "salida": 100, "coste_eur": 0.0}
    assert tokens["por_proveedor"]["reglas"] == {"llamadas": 1, "entrada": 0, "salida": 0, "coste_eur": 0.0}
    claude = tokens["por_proveedor"]["claude"]
    assert claude["llamadas"] == 1 and claude["entrada"] == 1000 and claude["salida"] == 2000
    assert claude["coste_eur"] == pytest.approx((1000 * 5 + 2000 * 25) / 1e6)  # 0,055 €
    assert tokens["coste_total_eur"] == pytest.approx(0.055)
    assert tokens["coste_total_eur"] > antes["coste_total_eur"]

    # Otra llamada a Claude: el acumulado suma lo registrado
    api.post(URL_METRICAS, json=_metrica("claude", "claude-opus-5-5", 2000, 400), headers=TOKEN)
    tokens = api.get(URL, headers=TOKEN).json()["tokens"]
    assert tokens["por_proveedor"]["claude"]["llamadas"] == 2
    assert tokens["coste_total_eur"] == pytest.approx(0.055 + (2000 * 5 + 400 * 25) / 1e6)


def test_tokens_por_periodo(api, precios):
    api.post(URL_METRICAS, json=_metrica(ts=VIERNES.timestamp()), headers=TOKEN)
    assert api.get(URL, params=HISTORICO, headers=TOKEN).json()["tokens"]["por_proveedor"] == {}
    periodo = {"desde": "2026-11-20T00:00:00+01:00", "hasta": "2026-11-21T00:00:00+01:00"}
    assert api.get(URL, params=periodo, headers=TOKEN).json()["tokens"]["por_proveedor"]["claude"]["llamadas"] == 1


def test_sin_ts_usa_la_hora_de_llegada_y_campos_minimos(api, precios):
    minimo = {"proveedor": "freellm", "tarea": "spam", "tokens_entrada": 10, "tokens_salida": 5}
    _valida(METRICA, minimo)
    assert api.post(URL_METRICAS, json=minimo, headers=TOKEN).status_code == 202
    assert api.get(URL, headers=TOKEN).json()["tokens"]["por_proveedor"]["freellm"]["entrada"] == 10


def test_modelo_largo_se_recorta(api, db):
    from app.modelos import MetricaTokens

    r = api.post(URL_METRICAS, json=_metrica("freellm", "x" * 300, 1, 1), headers=TOKEN)
    assert r.status_code == 202
    assert len(db.query(MetricaTokens).one().modelo) == 80


@pytest.mark.parametrize(
    "cambio",
    [{"tokens_entrada": -1}, {"tokens_salida": "muchos"}, {"proveedor": ""}, {"latencia_ms": -5}],
)
def test_metrica_invalida_422(api, cambio):
    _error(api.post(URL_METRICAS, json=_metrica() | cambio, headers=TOKEN), 422, "validacion")


def test_metrica_sin_campos_obligatorios_422(api):
    cuerpo = _metrica()
    del cuerpo["tarea"]
    _error(api.post(URL_METRICAS, json=cuerpo, headers=TOKEN), 422, "validacion")


def test_coste_por_modelo_manda_sobre_el_del_proveedor(precios):
    precios["claude:claude-haiku"] = {"entrada": 1.0, "salida": 5.0}
    assert coste_eur("claude", "claude-haiku", 1_000_000, 1_000_000) == pytest.approx(6.0)
    assert coste_eur("claude", "claude-opus-5-5", 1_000_000, 0) == pytest.approx(5.0)
    assert coste_eur("gemini", "gemini-2.5-flash", 1_000_000, 1_000_000) == 0.0
    assert coste_eur("desconocido", None, 1_000_000, 1_000_000) == 0.0  # lo que no está en la tabla, gratis


def test_precios_desde_variable_de_entorno(monkeypatch):
    monkeypatch.setenv("PRECIOS_TOKENS_EUR_MTOK", '{"claude":{"entrada":3,"salida":15}}')
    assert Settings(_env_file=None).precios_tokens_eur_mtok == {"claude": {"entrada": 3.0, "salida": 15.0}}
    monkeypatch.delenv("PRECIOS_TOKENS_EUR_MTOK")
    por_defecto = Settings(_env_file=None).precios_tokens_eur_mtok
    assert por_defecto["gemini"] == por_defecto["freellm"] == por_defecto["reglas"] == {"entrada": 0, "salida": 0}
    assert por_defecto["claude"]["salida"] > 0
