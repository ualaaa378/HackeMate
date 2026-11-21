"""Cambio de contrato de eventos y usuarios: frase_portada, datos_ayuntamiento (privado), imagen_url validada,
POST /eventos con sesión bearer, «Recuerdos» (estado=finalizado sin token), PATCH /usuarios/{id} y 404 genérico."""

import base64
import json

import pytest
from sqlalchemy import select

from app import chat
from app.config import get_settings
from app.modelos import Evento, Notificacion, Publicador, Usuario
from app.rutas import recomendaciones
from app.seed import sembrar
from app.seguridad import emitir_jwt
from app.serializar import evento_a_dict
from tests.test_importar import TOKEN, VIERNES, _cuerpo, _error
from tests.test_publico import EVENTO, _valida

RUTA = "1e5d0000-0000-4000-8000-000000000001"
GRAFITI_EN_REVISION = "1e5d0000-0000-4000-8000-000000000009"
ASOC_JUVENIL_TAHAL = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a07"
SENES_CULTURAL = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a04"
AMIGOS_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"
BAR_LA_PLAZA = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a03"
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
LUCIA_MODERADORA = "5a5e0000-0000-4000-8000-000000000002"
ANTONIO_PUBLICADOR = "5a5e0000-0000-4000-8000-000000000003"
PACO_PUBLICADOR = "5a5e0000-0000-4000-8000-000000000004"
INEXISTENTE = "00000000-0000-4000-8000-000000000000"
SECRETO = "Pintaríamos la pared exterior del lavadero"

DATOS_AYTO = {
    "responsable": "Rosa Pérez",
    "telefono": "+34600000999",
    "entidad": "particular",
    "publico": "mayores",
    "necesidades": ["espacio", "luz"],
    "seguro_rc": "no",
    "observaciones": "Dato privado de prueba",
}

NUEVO = {
    "titulo": "Merienda de otoño en la plaza",
    "descripcion": "Castañas asadas y juegos para todas las edades.",
    "categoria": "cultural",
    "municipio": "Tahal",
    "fecha_inicio": "2026-12-14T17:00:00+01:00",
    "frase_portada": "  Castañas, risas y vecinos  ",
    "datos_ayuntamiento": DATOS_AYTO,
}


def _bearer(usuario_id: str, rol: str = "vecino") -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, rol)}"}


def _data_url(n_bytes: int, tipo: str = "png") -> str:
    return f"data:image/{tipo};base64," + base64.b64encode(b"\x89" * n_bytes).decode()


@pytest.fixture
def api(cliente, db, monkeypatch):
    # Bot caído: antispam por reglas, sin llamadas de red, y los avisos quedan en cola.
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    sembrar(db, ahora=VIERNES)
    db.commit()
    yield cliente
    get_settings.cache_clear()


@pytest.fixture
def organizador_tahal(db) -> str:
    """Usuario responsable de la Asociación Juvenil de Tahal (publicador del grafiti en revisión)."""
    u = Usuario(nombre="Lucía Martínez", rol="publicador", telefono="+34600000107", publicador_id=ASOC_JUVENIL_TAHAL)
    db.add(u)
    db.commit()
    return u.id


# --- Modelo y seed ------------------------------------------------------------------------------------


def test_seed_carga_frase_datos_ayuntamiento_y_responsable(api, db):
    ruta = db.get(Evento, RUTA)
    assert ruta.frase_portada == "Cada paso suma: sube la sierra con nosotros por una buena causa"
    grafiti = db.get(Evento, GRAFITI_EN_REVISION)
    assert grafiti.datos_ayuntamiento["entidad"] == "asociacion"
    assert grafiti.datos_ayuntamiento["necesidades"] == ["espacio", "material", "limpieza"]

    senes = db.get(Publicador, SENES_CULTURAL)
    assert senes.identidad_verificada is True
    assert senes.responsable == {"nombre": "Carmen Ruiz Sánchez", "dni": "12345678Z", "residencia": "Senés"}
    tahal = db.get(Publicador, ASOC_JUVENIL_TAHAL)
    assert tahal.identidad_verificada is False and tahal.responsable["dni"] == "X1234567L"
    sin_datos = db.get(Publicador, AMIGOS_VELEFIQUE)
    assert sin_datos.responsable is None and sin_datos.identidad_verificada is False
    # Volver a sembrar no cambia nada (repetible).
    sembrar(db, ahora=VIERNES)
    db.commit()
    assert db.get(Publicador, SENES_CULTURAL).identidad_verificada is True


def test_frase_portada_es_publica(api):
    r = api.get(f"/api/v1/eventos/{RUTA}")
    assert r.status_code == 200
    _valida(EVENTO, r.json())
    assert r.json()["frase_portada"].startswith("Cada paso suma")
    lista = api.get("/api/v1/eventos", params={"size": 100}).json()["items"]
    assert any(e["frase_portada"] for e in lista)


# --- Privacidad de datos_ayuntamiento -----------------------------------------------------------------


def test_ficha_en_revision_solo_organizador_o_moderador_con_sus_datos(api, organizador_tahal):
    url = f"/api/v1/eventos/{GRAFITI_EN_REVISION}"
    _error(api.get(url), 404, "evento_no_encontrado")
    _error(api.get(url, headers=_bearer(CARMEN)), 404, "evento_no_encontrado")

    for cabeceras in (_bearer(organizador_tahal, "publicador"), _bearer(LUCIA_MODERADORA, "moderador")):
        r = api.get(url, headers=cabeceras)
        assert r.status_code == 200, r.text
        _valida(EVENTO, r.json())
        assert r.json()["datos_ayuntamiento"]["observaciones"].startswith(SECRETO)

    # El bot ve la ficha, pero no los datos privados (ni aunque mande además una sesión de moderador).
    for cabeceras in (TOKEN, {**TOKEN, **_bearer(LUCIA_MODERADORA, "moderador")}):
        r = api.get(url, headers=cabeceras)
        assert r.status_code == 200
        assert "datos_ayuntamiento" not in r.json()


def test_datos_ayuntamiento_no_se_filtran_por_rutas_publicas(api, db, monkeypatch):
    # Datos privados en todos los eventos publicados, para que cualquier fuga se note.
    for e in db.scalars(select(Evento).where(Evento.estado == "publicado")).all():
        e.datos_ayuntamiento = {**DATOS_AYTO, "observaciones": SECRETO}
    db.commit()

    def sin_fugas(r):
        assert r.status_code == 200, r.text
        assert "datos_ayuntamiento" not in r.text and SECRETO not in r.text

    sin_fugas(api.get("/api/v1/eventos", params={"size": 100}))
    sin_fugas(api.get("/api/v1/eventos", params={"size": 100}, headers=TOKEN))
    sin_fugas(api.get("/api/v1/eventos", params={"size": 100}, headers=_bearer(LUCIA_MODERADORA, "moderador")))
    sin_fugas(api.get(f"/api/v1/eventos/{RUTA}"))
    sin_fugas(api.get(f"/api/v1/eventos/{RUTA}", headers=TOKEN))
    sin_fugas(api.get(f"/api/v1/eventos/{RUTA}", headers=_bearer(CARMEN)))
    sin_fugas(api.get(f"/api/v1/eventos/{RUTA}/ics"))

    monkeypatch.setattr(recomendaciones, "reloj", lambda: VIERNES)
    r = api.get("/api/v1/recomendaciones", params={"usuario_id": CARMEN, "limite": 20}, headers=TOKEN)
    sin_fugas(r)
    assert r.json()["items"]
    sin_fugas(api.get("/api/v1/recomendaciones", params={"usuario_id": CARMEN}, headers=_bearer(CARMEN)))

    # El organizador (Antonio, de Amigos de Velefique) sí los ve en su ficha.
    r = api.get(f"/api/v1/eventos/{RUTA}", headers=_bearer(ANTONIO_PUBLICADOR, "publicador"))
    assert r.json()["datos_ayuntamiento"]["observaciones"] == SECRETO


def test_la_ficha_que_va_a_la_ia_no_lleva_datos_privados(api, db, monkeypatch):
    enviado = {}

    def falso_bot(evento_json, pregunta):
        enviado.update(evento_json)
        return True, "Sí, es gratis."

    monkeypatch.setattr(chat, "_llamar_bot_ficha", falso_bot)
    grafiti = db.get(Evento, GRAFITI_EN_REVISION)
    assert chat.respuesta_automatica(grafiti, "¿Es gratis?") == "Sí, es gratis."
    assert enviado["id"] == GRAFITI_EN_REVISION and "datos_ayuntamiento" not in enviado
    assert "datos_ayuntamiento" not in evento_a_dict(grafiti)
    assert evento_a_dict(grafiti, privados=True)["datos_ayuntamiento"]["entidad"] == "asociacion"


def test_bandeja_de_moderacion_solo_con_sesion_de_moderador(api):
    def grafiti(cabeceras):
        r = api.get("/api/v1/moderacion/pendientes", params={"size": 100}, headers=cabeceras)
        assert r.status_code == 200, r.text
        return next(i["evento"] for i in r.json()["items"] if i["tipo"] == "evento" and i["evento"]["id"] == GRAFITI_EN_REVISION)

    assert grafiti(_bearer(LUCIA_MODERADORA, "moderador"))["datos_ayuntamiento"]["seguro_rc"] == "nose"
    assert "datos_ayuntamiento" not in grafiti(TOKEN)

    r = api.post(f"/api/v1/moderacion/{GRAFITI_EN_REVISION}/decision", json={"decision": "aprobar"},
                 headers=_bearer(LUCIA_MODERADORA, "moderador"))
    assert r.status_code == 200 and r.json()["datos_ayuntamiento"]["entidad"] == "asociacion"
    # Ya publicado: el público lo ve, sin datos privados.
    r = api.get(f"/api/v1/eventos/{GRAFITI_EN_REVISION}")
    assert r.status_code == 200 and "datos_ayuntamiento" not in r.json()


def test_decision_por_el_bot_no_devuelve_datos_privados(api):
    r = api.post(f"/api/v1/moderacion/{GRAFITI_EN_REVISION}/decision", json={"decision": "rechazar"}, headers=TOKEN)
    assert r.status_code == 200 and "datos_ayuntamiento" not in r.json()


# --- POST /eventos con sesión ---------------------------------------------------------------------------


def test_vecino_propone_y_queda_en_revision_con_aviso_a_moderadores(api, db):
    r = api.post("/api/v1/eventos", json=NUEVO, headers=_bearer(CARMEN))
    assert r.status_code == 201, r.text
    creado = r.json()
    _valida(EVENTO, creado)
    assert creado["estado"] == "en_revision" and creado["publicador_id"] is None
    assert creado["origen"]["canal"] == "web"
    assert creado["frase_portada"] == "Castañas, risas y vecinos"
    # Quien lo propone ve lo que ha enviado; el público no lo ve (en revisión) y el bot, sin datos privados.
    assert creado["datos_ayuntamiento"] == DATOS_AYTO
    assert db.get(Evento, creado["id"]).datos_ayuntamiento == DATOS_AYTO
    _error(api.get(f"/api/v1/eventos/{creado['id']}"), 404, "evento_no_encontrado")
    assert "datos_ayuntamiento" not in api.get(f"/api/v1/eventos/{creado['id']}", headers=TOKEN).json()

    avisos = db.scalars(select(Notificacion).where(Notificacion.evento_id == creado["id"])).all()
    assert avisos and all(a.tipo == "moderacion" for a in avisos)
    assert {a.usuario_id for a in avisos} == {LUCIA_MODERADORA}


def test_vecino_no_puede_publicar_a_nombre_de_otro(api):
    r = api.post("/api/v1/eventos", json={**NUEVO, "publicador_id": ASOC_JUVENIL_TAHAL}, headers=_bearer(CARMEN))
    _error(r, 403, "prohibido")
    r = api.post("/api/v1/eventos", json={**NUEVO, "publicador_id": BAR_LA_PLAZA},
                 headers=_bearer(ANTONIO_PUBLICADOR, "publicador"))
    _error(r, 403, "prohibido")


def test_publicador_de_confianza_publica_con_su_entidad(api, db):
    r = api.post("/api/v1/eventos", json={**NUEVO, "categoria": "gastronomia", "municipio": "Uleila del Campo"},
                 headers=_bearer(PACO_PUBLICADOR, "publicador"))
    assert r.status_code == 201, r.text
    assert r.json()["publicador_id"] == BAR_LA_PLAZA and r.json()["estado"] == "publicado"
    assert r.json()["moderacion"]["score_spam"] is not None
    assert not db.scalars(select(Notificacion).where(Notificacion.evento_id == r.json()["id"])).all()
    # Puede indicar su propio publicador_id.
    r = api.post("/api/v1/eventos", json={**NUEVO, "titulo": "Tapas de invierno", "categoria": "gastronomia",
                                          "publicador_id": BAR_LA_PLAZA},
                 headers=_bearer(PACO_PUBLICADOR, "publicador"))
    assert r.status_code == 201 and r.json()["publicador_id"] == BAR_LA_PLAZA


def test_publicador_nivel_1_fuera_de_lo_habitual_queda_en_revision(api):
    r = api.post("/api/v1/eventos", json={**NUEVO, "categoria": "gastronomia"},
                 headers=_bearer(ANTONIO_PUBLICADOR, "publicador"))
    assert r.status_code == 201, r.text
    assert r.json()["publicador_id"] == AMIGOS_VELEFIQUE and r.json()["estado"] == "en_revision"


def test_publicador_pausado_no_puede_proponer(api, db):
    db.get(Publicador, AMIGOS_VELEFIQUE).estado = "pausado"
    db.commit()
    _error(api.post("/api/v1/eventos", json=NUEVO, headers=_bearer(ANTONIO_PUBLICADOR, "publicador")),
           403, "publicador_pausado")


def test_moderador_publica_directo(api):
    r = api.post("/api/v1/eventos", json={**NUEVO, "publicador_id": ASOC_JUVENIL_TAHAL},
                 headers=_bearer(LUCIA_MODERADORA, "moderador"))
    assert r.status_code == 201, r.text
    creado = r.json()
    assert creado["estado"] == "publicado" and creado["publicador_id"] == ASOC_JUVENIL_TAHAL
    assert creado["moderacion"]["revisado_por"] == "Lucía (moderadora)"
    assert api.get(f"/api/v1/eventos/{creado['id']}").status_code == 200


def test_token_interno_como_siempre_y_sin_datos_privados(api):
    r = api.post("/api/v1/eventos", json=NUEVO, headers=TOKEN)
    assert r.status_code == 201, r.text
    assert r.json()["estado"] == "en_revision" and r.json()["origen"]["canal"] == "manual"
    assert "datos_ayuntamiento" not in r.json()


def test_validacion_de_frase_y_datos_ayuntamiento(api):
    _error(api.post("/api/v1/eventos", json={**NUEVO, "frase_portada": "x" * 91}, headers=_bearer(CARMEN)),
           422, "validacion")
    malos = {**DATOS_AYTO, "seguro_rc": "quizas"}
    _error(api.post("/api/v1/eventos", json={**NUEVO, "datos_ayuntamiento": malos}, headers=_bearer(CARMEN)),
           422, "validacion")
    # Lo desconocido dentro de datos_ayuntamiento (la web manda a veces frase_portada ahí) se ignora.
    r = api.post("/api/v1/eventos", json={**NUEVO, "datos_ayuntamiento": {**DATOS_AYTO, "frase_portada": "x"}},
                 headers=_bearer(CARMEN))
    assert r.status_code == 201 and r.json()["datos_ayuntamiento"] == DATOS_AYTO


# --- imagen_url ---------------------------------------------------------------------------------------


@pytest.mark.parametrize("imagen", ["ftp://example.org/a.png", "no es una url", "data:text/html;base64,PGI+",
                                    "data:image/png;base64,", "javascript:alert(1)"])
def test_imagen_invalida_422(api, imagen):
    _error(api.post("/api/v1/eventos", json={**NUEVO, "imagen_url": imagen}, headers=TOKEN), 422, "imagen_invalida")


def test_imagen_demasiado_grande_422(api):
    grande = _data_url(1536 * 1024 + 10, "webp")
    _error(api.post("/api/v1/eventos", json={**NUEVO, "imagen_url": grande}, headers=TOKEN), 422, "imagen_invalida")


def test_imagen_data_url_grande_cabe_y_se_guarda(api, db):
    imagen = _data_url(1400 * 1024, "jpeg")
    r = api.post("/api/v1/eventos", json={**NUEVO, "imagen_url": imagen}, headers=TOKEN)
    assert r.status_code == 201, r.text
    db.expire_all()
    assert db.get(Evento, r.json()["id"]).imagen_url == imagen
    r = api.post("/api/v1/eventos", json={**NUEVO, "imagen_url": "https://example.org/cartel.webp"}, headers=TOKEN)
    assert r.status_code == 201 and r.json()["imagen_url"] == "https://example.org/cartel.webp"


def test_patch_valida_imagen_y_edita_frase_y_datos(api, organizador_tahal):
    url = f"/api/v1/eventos/{GRAFITI_EN_REVISION}"
    org = _bearer(organizador_tahal, "publicador")
    _error(api.patch(url, json={"imagen_url": "fichero.png"}, headers=org), 422, "imagen_invalida")
    r = api.patch(url, json={"imagen_url": _data_url(100), "frase_portada": "Color para el lavadero",
                             "datos_ayuntamiento": DATOS_AYTO}, headers=org)
    assert r.status_code == 200, r.text
    assert r.json()["frase_portada"] == "Color para el lavadero"
    assert r.json()["datos_ayuntamiento"] == DATOS_AYTO
    # El bot edita, pero no recibe los datos privados.
    r = api.patch(url, json={"frase_portada": ""}, headers=TOKEN)
    assert r.status_code == 200 and r.json()["frase_portada"] is None and "datos_ayuntamiento" not in r.json()
    r = api.patch(url, json={"datos_ayuntamiento": None}, headers=org)
    assert r.json()["datos_ayuntamiento"] is None


def test_confirmar_acepta_frase_portada_y_datos_ayuntamiento(api, db):
    r = api.post("/api/v1/eventos/importar", json=_cuerpo(url=None, publicador_id=BAR_LA_PLAZA), headers=TOKEN)
    assert r.status_code == 201, r.text
    evento_id = r.json()["evento"]["id"]
    campos = {"frase_portada": "Ven con hambre", "datos_ayuntamiento": DATOS_AYTO, "imagen_url": _data_url(50)}
    r = api.post(f"/api/v1/eventos/{evento_id}/confirmar", json={"campos": campos}, headers=TOKEN)
    assert r.status_code == 200, r.text
    assert r.json()["evento"]["frase_portada"] == "Ven con hambre"
    assert "datos_ayuntamiento" not in r.json()["evento"]
    db.expire_all()
    assert db.get(Evento, evento_id).datos_ayuntamiento == DATOS_AYTO


def test_confirmar_con_imagen_invalida_422_sin_cambios(api, db):
    r = api.post("/api/v1/eventos/importar", json=_cuerpo(url=None, publicador_id=BAR_LA_PLAZA), headers=TOKEN)
    evento_id = r.json()["evento"]["id"]
    r = api.post(f"/api/v1/eventos/{evento_id}/confirmar",
                 json={"campos": {"imagen_url": "cartel.jpg", "frase_portada": "No se guarda"}}, headers=TOKEN)
    _error(r, 422, "imagen_invalida")
    db.expire_all()
    evento = db.get(Evento, evento_id)
    assert evento.estado == "pendiente_confirmacion" and evento.frase_portada is None


# --- «Recuerdos»: GET /eventos?estado=finalizado sin token ------------------------------------------------


def test_recuerdos_lista_planes_finalizados_sin_token(api, db):
    r = api.get("/api/v1/eventos", params={"estado": "finalizado", "size": 100})
    assert r.status_code == 200
    items = r.json()["items"]
    esperados = set(db.scalars(select(Evento.id).where(Evento.estado == "finalizado")).all())
    assert esperados and {e["id"] for e in items} == esperados
    assert "4a5a0000-0000-4000-8000-000000000001" in esperados  # histórico del seed
    for e in items:
        _valida(EVENTO, e)
        assert e["estado"] == "finalizado" and "datos_ayuntamiento" not in e


def test_otros_estados_sin_token_se_cambian_por_publicado(api):
    r = api.get("/api/v1/eventos", params={"estado": "en_revision", "size": 100})
    assert r.status_code == 200 and r.json()["items"]
    assert {e["estado"] for e in r.json()["items"]} == {"publicado"}
    r = api.get("/api/v1/eventos", params={"estado": "en_revision", "size": 100}, headers=TOKEN)
    assert {e["estado"] for e in r.json()["items"]} == {"en_revision"}


# --- PATCH /usuarios/{id} -------------------------------------------------------------------------------


def test_bot_guarda_preferencias_del_usuario(api, db):
    r = api.patch(f"/api/v1/usuarios/{CARMEN}",
                  json={"gustos": ["deportiva", "cultural", "deportiva"], "municipio": "Tahal", "formato_aviso": "audio"},
                  headers=TOKEN)
    assert r.status_code == 200, r.text
    u = r.json()
    assert u["gustos"] == ["deportiva", "cultural"] and u["formato_aviso"] == "audio" and u["municipio"] == "Tahal"
    assert (u["lat"], u["lon"]) == (37.2219, -2.2853)
    db.expire_all()
    assert db.get(Usuario, CARMEN).formato_aviso == "audio"


def test_patch_usuario_errores(api):
    url = f"/api/v1/usuarios/{CARMEN}"
    _error(api.patch(url, json={"gustos": ["deportiva"]}), 401, "token_interno_invalido")
    _error(api.patch(url, json={"gustos": ["deportiva"]}, headers=_bearer(CARMEN)), 401, "token_interno_invalido")
    _error(api.patch(f"/api/v1/usuarios/{INEXISTENTE}", json={}, headers=TOKEN), 404, "usuario_no_encontrado")
    _error(api.patch("/api/v1/usuarios/no-es-uuid", json={}, headers=TOKEN), 404, "usuario_no_encontrado")
    _error(api.patch(url, json={"municipio": "Almería"}, headers=TOKEN), 422, "municipio_no_encontrado")
    _error(api.patch(url, json={"formato_aviso": "video"}, headers=TOKEN), 422, "validacion")
    _error(api.patch(url, json={"telefono": "+34600000205"}, headers=TOKEN), 409, "telefono_en_uso")


def test_patch_usuarios_me_sigue_igual(api):
    r = api.patch("/api/v1/usuarios/me", json={"formato_aviso": "audio"}, headers=_bearer(CARMEN))
    assert r.status_code == 200 and r.json()["id"] == CARMEN and r.json()["formato_aviso"] == "audio"
    _error(api.patch("/api/v1/usuarios/me", json={}, headers=TOKEN), 401, "no_autenticado")


# --- Ruta inexistente --------------------------------------------------------------------------------------


@pytest.mark.parametrize("metodo,ruta", [("get", "/api/v1/no-existe"), ("post", "/nada"), ("get", "/api/v1/eventos/x/y/z")])
def test_ruta_inexistente_404_no_encontrado(api, metodo, ruta):
    r = getattr(api, metodo)(ruta)
    _error(r, 404, "no_encontrado")
    assert json.loads(r.text)["error"]["message"]
