"""POST /eventos/{id}/confirmar (H2.3 + H2.4): el publicador completa lo que falta y pasa a moderación."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select

from app.config import get_settings
from app.modelos import Evento, Publicador
from app.seed import sembrar
from tests.test_importar import BAR_LA_PLAZA, TOKEN, URL, VIERNES, _cuerpo, _error, _valida

AMIGOS_VELEFIQUE_TEL = "+34600000101"
BAR_LA_PLAZA_TEL = "+34600000103"
NUEVO_TEL = "+34600000999"
RUTA_SOLIDARIA_SEED = "1e5d0000-0000-4000-8000-000000000001"
APUESTAS_SEED = "1e5d0000-0000-4000-8000-000000000010"
OTRO_TITULO = "Marcha nocturna por la Sierra de Velefique"


def _url_confirmar(id: str) -> str:
    return f"/api/v1/eventos/{id}/confirmar"


@pytest.fixture
def api(cliente, db, monkeypatch):
    # Sin bot: el antispam usa las reglas locales (y no espera a un host que no existe).
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    sembrar(db, ahora=VIERNES)
    db.commit()
    yield cliente
    get_settings.cache_clear()


def _importar(api, telefono: str | None = BAR_LA_PLAZA_TEL, url: str | None = None, **campos) -> dict:
    """Importa la Ruta Solidaria (o lo que indiquen `campos`) y devuelve la respuesta."""
    cuerpo = _cuerpo(url=url, telefono_publicador=telefono) if telefono else _cuerpo(url=url)
    for nombre, valor in campos.items():
        cuerpo["extraccion"]["campos"][nombre] = (
            {"valor": None, "confianza": "falta"} if valor is None else {"valor": valor, "confianza": "alta"}
        )
    r = api.post(URL, json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    return r.json()


def _confirmar(api, id: str, campos: dict | None = None, headers=TOKEN):
    return api.post(_url_confirmar(id), json={"campos": campos or {}, "confirmado_por": "whatsapp"}, headers=headers)


def _publicados(api) -> set[str]:
    return {e["id"] for e in api.get("/api/v1/eventos", params={"size": 100}).json()["items"]}


def _nuevo_publicador(db, nivel: int = 0) -> Publicador:
    p = Publicador(nombre="Peña nueva", tipo="asociacion", municipio="Senés", telefono=NUEVO_TEL,
                   estado="aprobado", nivel_confianza=nivel)
    db.add(p)
    db.commit()
    return p


def test_ruta_solidaria_completa_faltan(api):
    # El seed ya tiene la Ruta Solidaria publicada: la importada se señala como posible duplicado.
    importado = _importar(api, telefono=AMIGOS_VELEFIQUE_TEL)
    assert sorted(importado["faltan"]) == ["lugar", "plazas_totales"]
    id = importado["evento"]["id"]

    r = _confirmar(api, id, {"lugar": "Plaza de la Iglesia", "plazas_totales": 40})
    assert r.status_code == 200, r.text
    datos = r.json()
    _valida(datos)
    assert datos["faltan"] == []
    assert datos["duplicado"] is False
    assert datos["posible_duplicado_de"] == RUTA_SOLIDARIA_SEED
    evento = datos["evento"]
    assert evento["lugar"] == "Plaza de la Iglesia"
    assert evento["plazas_totales"] == 40 and evento["plazas_libres"] == 40
    assert evento["estado"] == "en_revision"
    assert evento["moderacion"]["motivo"] == "Posible duplicado de «II Ruta Solidaria Sierra de Velefique»"
    assert evento["moderacion"]["score_spam"] == 0.0
    assert id not in _publicados(api)


def test_a_mano_va_a_revision_aunque_sea_su_categoria_habitual(api):
    # Amigos de Velefique publica «a mano» (nivel 0): ya no hay semiautomático por categoría habitual.
    id = _importar(api, telefono=AMIGOS_VELEFIQUE_TEL, titulo=OTRO_TITULO)["evento"]["id"]
    r = _confirmar(api, id, {"lugar": "Plaza de la Iglesia", "plazas_totales": 40})
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["posible_duplicado_de"] is None
    evento = r.json()["evento"]
    assert evento["estado"] == "en_revision"
    assert evento["moderacion"]["motivo"] == "Publicación a mano: la revisa el moderador"
    assert id not in _publicados(api)


def test_nivel_1_obsoleto_cuenta_como_a_mano(api, db):
    _nuevo_publicador(db, nivel=1)
    id = _importar(api, telefono=NUEVO_TEL, titulo=OTRO_TITULO)["evento"]["id"]
    r = _confirmar(api, id, {"lugar": "Plaza", "plazas_totales": 10})
    assert r.status_code == 200, r.text
    assert r.json()["evento"]["estado"] == "en_revision"
    assert r.json()["evento"]["moderacion"]["motivo"] == "Publicación a mano: la revisa el moderador"


def test_nivel_2_texto_normal_publica(api):
    id = _importar(api, titulo="Menú del domingo en la plaza", categoria="gastronomia", municipio="Senés",
                   descripcion="Migas, gurullos y postre casero.")["evento"]["id"]
    r = _confirmar(api, id)
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["evento"]["estado"] == "publicado"
    # Los opcionales que falten no bloquean; siguen en `faltan` por si el bot quiere pedirlos.
    assert sorted(r.json()["faltan"]) == ["lugar", "plazas_totales"]
    assert id in _publicados(api)


def test_nivel_0_a_revision_con_motivo(api, db):
    _nuevo_publicador(db, nivel=0)
    id = _importar(api, telefono=NUEVO_TEL, titulo=OTRO_TITULO)["evento"]["id"]
    r = _confirmar(api, id, {"lugar": "Plaza", "plazas_totales": 10})
    assert r.status_code == 200, r.text
    _valida(r.json())
    evento = r.json()["evento"]
    assert evento["estado"] == "en_revision"
    assert evento["moderacion"]["motivo"] == "Publicación a mano: la revisa el moderador"
    assert id not in _publicados(api)


def test_nivel_2_con_spam_se_queda_en_revision(api, db):
    id = _importar(api, titulo="¡¡GANA DINERO con APUESTAS!! bit.ly/x", categoria="gastronomia",
                   descripcion="¡¡GANA DINERO con APUESTAS!! bit.ly/x")["evento"]["id"]
    r = _confirmar(api, id, {"lugar": "Online", "plazas_totales": 100})
    assert r.status_code == 200, r.text
    _valida(r.json())
    evento = r.json()["evento"]
    assert evento["estado"] == "en_revision"
    assert evento["moderacion"]["motivo"].startswith("Posible spam")
    assert "apuesta" in evento["moderacion"]["motivo"]
    assert evento["moderacion"]["score_spam"] >= get_settings().moderacion_umbral_spam
    assert id not in _publicados(api)
    guardado = db.scalar(select(Evento).where(Evento.id == id).execution_options(populate_existing=True))
    assert guardado.motivo_moderacion.startswith("Posible spam")


def test_sin_fecha_no_confirma_hasta_darla(api):
    id = _importar(api, titulo=OTRO_TITULO, fecha_inicio=None)["evento"]["id"]
    r = _confirmar(api, id, {"lugar": "Plaza"})
    _error(r, 422, "faltan_campos")
    assert r.json()["error"]["details"]["faltan"] == ["fecha_inicio"]
    # No se ha guardado nada: sigue pendiente y con lo que faltaba.
    ficha = api.get(f"/api/v1/eventos/{id}", headers=TOKEN).json()
    assert ficha["estado"] == "pendiente_confirmacion" and ficha["lugar"] is None

    r = _confirmar(api, id, {"fecha_inicio": "2026-11-29T09:00:00", "lugar": "Plaza", "plazas_totales": 20})
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["faltan"] == []
    assert r.json()["evento"]["fecha_inicio"] == "2026-11-29T09:00:00+01:00"
    assert r.json()["evento"]["estado"] == "publicado"


def test_municipio_provisional_hay_que_confirmarlo(api):
    id = _importar(api, municipio=None)["evento"]["id"]
    _error(_confirmar(api, id), 422, "faltan_campos")
    _error(_confirmar(api, id, {"municipio": "Atlantis"}), 422, "municipio_no_encontrado")
    r = _confirmar(api, id, {"municipio": "velefique"})
    assert r.status_code == 200, r.text
    assert r.json()["evento"]["municipio"] == "Velefique"


def test_confirmar_dos_veces_409(api):
    id = _importar(api)["evento"]["id"]
    assert _confirmar(api, id).status_code == 200
    _error(_confirmar(api, id), 409, "estado_invalido")


def test_inexistente_404(api):
    _error(_confirmar(api, "00000000-0000-4000-8000-000000000000"), 404, "evento_no_encontrado")


def test_sin_token_401(api):
    id = _importar(api)["evento"]["id"]
    r = _confirmar(api, id, headers={})
    assert r.status_code == 401, r.text


def test_publicador_pausado_403(api, db):
    id = _importar(api)["evento"]["id"]
    bar = db.get(Publicador, BAR_LA_PLAZA)
    bar.estado = "pausado"
    db.commit()
    _error(_confirmar(api, id), 403, "publicador_pausado")


def test_posible_duplicado_va_a_revision(api):
    # El primero lo publica el Bar La Plaza (automática, nivel 2).
    primero = _importar(api, titulo=OTRO_TITULO)["evento"]["id"]
    assert _confirmar(api, primero, {"lugar": "Plaza", "plazas_totales": 40}).json()["evento"]["estado"] == "publicado"
    # Lo mismo, llegado por otro lado y publicado por alguien de nivel 2.
    segundo = _importar(api, url="https://example.org/otro-post", titulo=OTRO_TITULO.upper())["evento"]["id"]
    r = _confirmar(api, segundo, {"lugar": "Plaza", "plazas_totales": 40})
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["posible_duplicado_de"] == primero
    assert r.json()["evento"]["estado"] == "en_revision"
    assert "Posible duplicado" in r.json()["evento"]["moderacion"]["motivo"]


def test_campos_invalidos_422(api):
    id = _importar(api)["evento"]["id"]
    assert _confirmar(api, id, {"plazas_totales": -1}).status_code == 422
    assert _confirmar(api, id, {"titulo": None}).status_code == 422
    _error(_confirmar(api, id, {"fecha_fin": "2026-11-01T09:00:00+01:00"}), 422, "fechas_invalidas")


# --- Revisión H2 (ronda 1) --------------------------------------------------------------------------

def _fixture_demo(id: str) -> dict:
    ruta = Path(__file__).resolve().parents[3] / "contracts" / "fixtures" / "eventos_demo.json"
    return next(e for e in json.loads(ruta.read_text(encoding="utf-8")) if e["id"] == id)


def test_apuestas_de_la_demo_sin_bot_se_queda_en_revision(api):
    """El texto exacto del fixture de apuestas, de Bar La Plaza (nivel 2) y sin bot: deciden las reglas."""
    spam = _fixture_demo(APUESTAS_SEED)
    importado = _importar(api, url="https://example.org/posts/apuestas", titulo=spam["titulo"],
                          descripcion=spam["descripcion"], categoria="gastronomia")
    id = importado["evento"]["id"]
    assert importado["evento"]["publicador_id"] == BAR_LA_PLAZA
    r = _confirmar(api, id, {"lugar": "Bar La Plaza", "plazas_totales": 50})
    assert r.status_code == 200, r.text
    _valida(r.json())
    evento = r.json()["evento"]
    assert evento["estado"] == "en_revision"
    assert evento["moderacion"]["motivo"].startswith("Posible spam")
    assert "apuesta" in evento["moderacion"]["motivo"]
    assert evento["moderacion"]["score_spam"] >= get_settings().moderacion_umbral_spam
    assert id not in _publicados(api)


def test_publicador_rechazado_403_al_importar_y_al_confirmar(api, db):
    id = _importar(api)["evento"]["id"]
    bar = db.get(Publicador, BAR_LA_PLAZA)
    bar.estado = "rechazado"
    db.commit()
    _error(_confirmar(api, id), 403, "publicador_rechazado")
    cuerpo = _cuerpo(url="https://example.org/posts/otro", telefono_publicador=BAR_LA_PLAZA_TEL)
    _error(api.post(URL, json=cuerpo, headers=TOKEN), 403, "publicador_rechazado")


def test_mismo_origen_url_a_la_vez_devuelve_el_existente(api, db, monkeypatch):
    """Simula la carrera: la primera comprobación no ve el otro evento (aún no estaba guardado), la de justo
    antes del commit sí. Responde 200 con el que ya existía y no crea otro."""
    from app.rutas import importar

    url = "https://example.org/posts/carrera"
    primero = _importar(api, url=url)["evento"]["id"]
    real = importar._primero_con_url
    llamadas = []

    def primero_con_url(db, u, excluir_id=None):
        llamadas.append(excluir_id)
        return None if len(llamadas) == 1 else real(db, u, excluir_id)

    monkeypatch.setattr(importar, "_primero_con_url", primero_con_url)
    r = api.post(URL, json=_cuerpo(url=url, telefono_publicador=BAR_LA_PLAZA_TEL), headers=TOKEN)
    assert r.status_code == 200, r.text
    assert r.json()["duplicado"] is True and r.json()["evento"]["id"] == primero
    assert len(llamadas) == 2
    db.expire_all()
    assert db.scalars(select(Evento.id).where(Evento.origen_url == url)).all() == [primero]


def test_aviso_a_moderadores_tras_confirmar_sale_en_segundo_plano(api, db, monkeypatch):
    """Confirmar crea el aviso `pendiente` y lo envía una BackgroundTask tras el commit."""
    import httpx

    from app import notificaciones
    from app.modelos import Notificacion, Usuario

    db.add(Usuario(nombre="Moderadora", rol="moderador", telefono="+34600000888"))
    db.commit()
    id = _importar(api, telefono=NUEVO_TEL, titulo=OTRO_TITULO)["evento"]["id"]  # sin publicador: a revisión
    recibidas = []
    monkeypatch.setattr(notificaciones, "_transporte", httpx.MockTransport(
        lambda p: recibidas.append(json.loads(p.content)) or httpx.Response(200, json={"enviado": True})))
    monkeypatch.setenv("BOT_URL", "http://bot-falso:8001")
    get_settings.cache_clear()
    from app import moderacion
    monkeypatch.setattr(moderacion, "_llamar_bot_spam", lambda *a: None)  # sin red para /ai/spam
    r = _confirmar(api, id, {"lugar": "Plaza", "plazas_totales": 10})
    assert r.status_code == 200 and r.json()["evento"]["estado"] == "en_revision"
    assert "+34600000888" in [c["telefono"] for c in recibidas]
    db.expire_all()
    avisos = db.scalars(select(Notificacion).where(Notificacion.evento_id == id)).all()
    assert len(avisos) == len(recibidas) and all(a.estado_envio == "enviada" for a in avisos)


def test_mismo_origen_url_guardados_a_la_vez_se_queda_el_mas_antiguo(api, db, monkeypatch):
    """Si ni la comprobación previa ni la de antes del commit ven al otro (dos commits casi simultáneos), al
    volver a mirar ya guardado se queda el más antiguo y el nuevo se borra."""
    from app.rutas import importar

    url = "https://example.org/posts/carrera-2"
    primero = _importar(api, url=url)["evento"]["id"]
    real = importar._primero_con_url
    llamadas = []

    def primero_con_url(db, u, excluir_id=None):
        llamadas.append(excluir_id)
        return None if len(llamadas) <= 2 else real(db, u, excluir_id)

    monkeypatch.setattr(importar, "_primero_con_url", primero_con_url)
    r = api.post(URL, json=_cuerpo(url=url, telefono_publicador=BAR_LA_PLAZA_TEL), headers=TOKEN)
    assert r.status_code == 200, r.text
    assert r.json()["duplicado"] is True and r.json()["evento"]["id"] == primero
    db.expire_all()
    assert db.scalars(select(Evento.id).where(Evento.origen_url == url)).all() == [primero]
