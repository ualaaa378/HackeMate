"""Revisión a mano o automática de los publicadores: `responsable` y `actividad` (privados, solo moderador con
sesión), DNI/NIE en el alta, verificar-identidad, nivel 2 con reglas y panel del bot a través de la API."""

from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app.confianza import actividad_por_publicador, normalizar_dni
from app.config import get_settings
from app.modelos import Evento, Notificacion, Publicador, Usuario
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import TOKEN, VIERNES, _error
from tests.test_moderacion_rutas import PAGINA_PENDIENTES, _validador
from tests.test_moderacion_rutas import _valida as _valida_con

PUBLICADOR = _validador("./schemas/publicador.json")
METRICAS_BOT = _validador("urn:openapi#/components/schemas/MetricasBot")
CAIDA_SIMULADA = _validador("urn:openapi#/components/schemas/CaidaSimulada")

SENES_CULTURAL = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a04"  # responsable verificado en el fixture
ASOC_JUVENIL_TAHAL = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a07"  # responsable sin verificar
AMIGOS_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"  # sin responsable
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
INEXISTENTE = "00000000-0000-4000-8000-000000000000"
TEL_NUEVO = "+34600000888"

NUEVO = {
    "nombre": "Club Senderista Senés",
    "tipo": "asociacion",
    "municipio": "Senés",
    "telefono": TEL_NUEVO,
    "responsable": {"nombre": "Ana Gil", "dni": "12345678-z", "residencia": "Senés", "identidad_verificada": True},
}


def _valida(dato: dict) -> None:
    _valida_con(PUBLICADOR, dato)


def _bearer(usuario_id: str, rol: str) -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, rol)}"}


@pytest.fixture
def api(cliente, db, monkeypatch):
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    sembrar(db, ahora=VIERNES)
    db.commit()
    yield cliente
    get_settings.cache_clear()


@pytest.fixture
def moderador(db) -> dict:
    u = Usuario(nombre="Moderadora de prueba", rol="moderador", telefono="+34600000779")
    db.add(u)
    db.commit()
    return _bearer(u.id, "moderador")


def _ahora() -> datetime:
    return datetime.now(timezone.utc)


def _publicador(db, nivel: int = 1, responsable: dict | None = None, verificada: bool = False) -> Publicador:
    p = Publicador(nombre="Peña de prueba", tipo="asociacion", municipio="Velefique", telefono="+34600000771",
                   estado="aprobado", nivel_confianza=nivel, responsable=responsable, identidad_verificada=verificada)
    db.add(p)
    db.commit()
    return p


def _evento(db, publicador: Publicador, estado: str, hace_dias: float) -> Evento:
    creado = _ahora() - timedelta(days=hace_dias)
    e = Evento(titulo=f"Plan {estado} {hace_dias}", categoria="cultural", municipio="Velefique", lat=37.1, lon=-2.4,
               fecha_inicio=creado + timedelta(days=5), estado=estado, publicador_id=publicador.id, creado_en=creado)
    db.add(e)
    db.commit()
    return e


RESPONSABLE_OK = {"nombre": "Pepe Ruiz", "dni": "X1234567L", "residencia": "Velefique"}


def _cumple_reglas(db) -> Publicador:
    p = _publicador(db, responsable=RESPONSABLE_OK, verificada=True)
    for dias in (2, 10, 40):
        _evento(db, p, "publicado", dias)
    return p


# --- DNI / NIE ------------------------------------------------------------------------------------


@pytest.mark.parametrize("dni,esperado", [
    ("12345678Z", "12345678Z"), ("12345678-z", "12345678Z"), (" x1234567l ", "X1234567L"),
    ("Y0000000Z", "Y0000000Z"), ("Z0000000M", "Z0000000M"),
    ("12345678A", None), ("1234567Z", None), ("X1234567A", None), ("ABCDEFGHZ", None), ("", None),
])
def test_normalizar_dni(dni, esperado):
    assert normalizar_dni(dni) == esperado


# --- Privacidad -----------------------------------------------------------------------------------


def _sin_privados(dato: dict) -> None:
    assert "responsable" not in dato and "actividad" not in dato
    _valida(dato)


def test_ni_publico_ni_vecino_ni_bot_ven_responsable_ni_actividad(api):
    vecina = _bearer(CARMEN, "vecino")
    for cabeceras in ({}, vecina, TOKEN):
        r = api.get(f"/api/v1/publicadores/{SENES_CULTURAL}", headers=cabeceras)
        assert r.status_code == 200, r.text
        _sin_privados(r.json())
        r = api.get("/api/v1/publicadores", params={"size": 100}, headers=cabeceras)
        assert r.status_code == 200, r.text
        assert r.json()["items"]
        for p in r.json()["items"]:
            _sin_privados(p)
        assert "12345678Z" not in r.text


def test_token_interno_con_sesion_de_moderador_tampoco_ve_privados(api, moderador):
    r = api.get(f"/api/v1/publicadores/{SENES_CULTURAL}", headers={**TOKEN, **moderador})
    _sin_privados(r.json())


def test_moderador_ve_responsable_y_actividad(api, moderador):
    r = api.get(f"/api/v1/publicadores/{SENES_CULTURAL}", headers=moderador)
    assert r.status_code == 200, r.text
    dato = r.json()
    _valida(dato)
    assert dato["responsable"] == {
        "nombre": "Carmen Ruiz Sánchez", "dni": "12345678Z", "residencia": "Senés", "identidad_verificada": True,
    }
    assert set(dato["actividad"]) == {"planes_60_dias", "rechazados_60_dias", "ultimo_plan"}
    assert "telefono" in dato  # el moderador ve también el contacto

    r = api.get("/api/v1/publicadores", params={"size": 100}, headers=moderador)
    items = {p["id"]: p for p in r.json()["items"]}
    for p in items.values():
        _valida(p)
        assert "actividad" in p and "responsable" in p
    assert items[AMIGOS_VELEFIQUE]["responsable"] is None
    assert items[ASOC_JUVENIL_TAHAL]["responsable"]["identidad_verificada"] is False


def test_moderador_ve_todos_los_estados_en_la_lista(api, db, moderador):
    db.get(Publicador, AMIGOS_VELEFIQUE).estado = "solicitado"
    db.commit()
    publica = {p["id"] for p in api.get("/api/v1/publicadores", params={"size": 100}).json()["items"]}
    assert AMIGOS_VELEFIQUE not in publica
    r = api.get("/api/v1/publicadores", params={"size": 100, "estado": "solicitado"}, headers=moderador)
    assert [p["id"] for p in r.json()["items"]] == [AMIGOS_VELEFIQUE]
    assert api.get(f"/api/v1/publicadores/{AMIGOS_VELEFIQUE}", headers=moderador).status_code == 200


def test_bandeja_solo_lleva_privados_con_sesion_de_moderador(api, db, moderador):
    r = api.post("/api/v1/publicadores", json=NUEVO, headers=TOKEN)
    assert r.status_code == 201, r.text
    for cabeceras, privados in ((moderador, True), (TOKEN, False)):
        r = api.get("/api/v1/moderacion/pendientes", params={"size": 100}, headers=cabeceras)
        assert r.status_code == 200, r.text
        _valida_con(PAGINA_PENDIENTES, r.json())
        pub = next(i["publicador"] for i in r.json()["items"] if i["tipo"] == "publicador")
        assert ("responsable" in pub) is privados and ("actividad" in pub) is privados
        if privados:
            assert pub["responsable"]["dni"] == "12345678Z"


# --- Actividad ------------------------------------------------------------------------------------


def test_actividad_correcta(api, db, moderador):
    p = _publicador(db)
    _evento(db, p, "publicado", 1)
    _evento(db, p, "finalizado", 30)
    _evento(db, p, "publicado", 70)       # fuera de los 60 días
    _evento(db, p, "rechazado", 5)
    _evento(db, p, "rechazado", 100)      # fuera de los 60 días
    _evento(db, p, "en_revision", 0.5)    # no cuenta
    _evento(db, p, "cancelado", 0.2)      # no cuenta
    r = api.get(f"/api/v1/publicadores/{p.id}", headers=moderador)
    a = r.json()["actividad"]
    assert a["planes_60_dias"] == 2 and a["rechazados_60_dias"] == 1
    ultimo = datetime.fromisoformat(a["ultimo_plan"])
    assert abs((_ahora() - ultimo) - timedelta(days=1)) < timedelta(minutes=1)
    assert ultimo.utcoffset() == timedelta(hours=1)  # Europe/Madrid en noviembre


def test_actividad_vacia_y_una_sola_consulta_para_la_pagina(db, api):
    p1, p2 = _publicador(db), _publicador(db)
    _evento(db, p1, "publicado", 3)
    resultado = actividad_por_publicador(db, [p1.id, p2.id])
    assert resultado[p1.id]["planes_60_dias"] == 1
    assert resultado[p2.id] == {"planes_60_dias": 0, "rechazados_60_dias": 0, "ultimo_plan": None}
    assert actividad_por_publicador(db, []) == {}


# --- Alta con responsable -------------------------------------------------------------------------


def test_alta_con_responsable_normaliza_dni_e_ignora_identidad_verificada(api, db, moderador):
    r = api.post("/api/v1/publicadores", json=NUEVO, headers=TOKEN)
    assert r.status_code == 201, r.text
    _sin_privados(r.json())  # la respuesta va al bot: sin datos personales
    p = db.get(Publicador, r.json()["id"])
    db.refresh(p)
    assert p.responsable == {"nombre": "Ana Gil", "dni": "12345678Z", "residencia": "Senés"}
    assert p.identidad_verificada is False


def test_alta_con_dni_invalido_422(api, db):
    cuerpo = {**NUEVO, "responsable": {**NUEVO["responsable"], "dni": "12345678A"}}
    r = api.post("/api/v1/publicadores", json=cuerpo, headers=TOKEN)
    _error(r, 422, "dni_invalido")
    assert r.json()["error"]["details"] == {"campo": "responsable.dni"}
    assert db.scalar(select(Publicador).where(Publicador.telefono == TEL_NUEVO)) is None


def test_alta_con_responsable_incompleto_422(api):
    cuerpo = {**NUEVO, "responsable": {"nombre": "Ana Gil"}}
    _error(api.post("/api/v1/publicadores", json=cuerpo, headers=TOKEN), 422, "validacion")


# --- verificar-identidad --------------------------------------------------------------------------


def _verificar(api, id: str, cuerpo: dict | None = None, headers=None):
    return api.post(f"/api/v1/publicadores/{id}/verificar-identidad", json=cuerpo, headers=headers or {})


def test_verificar_identidad(api, db, moderador):
    r = _verificar(api, ASOC_JUVENIL_TAHAL, headers=moderador)
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["responsable"]["identidad_verificada"] is True
    r = _verificar(api, ASOC_JUVENIL_TAHAL, {"identidad_verificada": False}, headers=moderador)
    assert r.json()["responsable"]["identidad_verificada"] is False
    db.expire_all()
    assert db.get(Publicador, ASOC_JUVENIL_TAHAL).identidad_verificada is False
    # El bot (token interno) también puede, pero no recibe los datos personales.
    r = _verificar(api, ASOC_JUVENIL_TAHAL, headers=TOKEN)
    assert r.status_code == 200
    _sin_privados(r.json())
    db.expire_all()
    assert db.get(Publicador, ASOC_JUVENIL_TAHAL).identidad_verificada is True


def test_verificar_identidad_errores(api, moderador):
    _error(_verificar(api, AMIGOS_VELEFIQUE, headers=moderador), 409, "sin_datos_responsable")
    _error(_verificar(api, INEXISTENTE, headers=moderador), 404, "publicador_no_encontrado")
    _error(_verificar(api, ASOC_JUVENIL_TAHAL), 401, "no_autenticado")
    _error(_verificar(api, ASOC_JUVENIL_TAHAL, headers=_bearer(CARMEN, "vecino")), 403, "rol_insuficiente")
    _error(_verificar(api, ASOC_JUVENIL_TAHAL, {"identidad_verificada": "quizá"}, headers=moderador),
           422, "validacion")


# --- Nivel de confianza ---------------------------------------------------------------------------


def _aprobar(api, id: str, cuerpo: dict | None, headers):
    return api.post(f"/api/v1/publicadores/{id}/aprobar", json=cuerpo, headers=headers)


def test_nivel_2_sin_reglas_409_con_lo_que_falta(api, db, moderador):
    p = _publicador(db, responsable=RESPONSABLE_OK, verificada=False)
    _evento(db, p, "publicado", 120)
    _evento(db, p, "rechazado", 3)
    r = _aprobar(api, p.id, {"aprobar": True, "nivel_confianza": 2}, moderador)
    _error(r, 409, "reglas_confianza_no_cumplidas")
    assert r.json()["error"]["details"]["faltan"] == [
        "identidad_verificada", "planes_60_dias", "rechazados_60_dias", "ultimo_plan",
    ]
    db.expire_all()
    assert db.get(Publicador, p.id).nivel_confianza == 1


def test_nivel_2_sin_responsable_falta_identidad(api, db, moderador):
    p = _publicador(db, responsable=None, verificada=True)
    for dias in (1, 2, 3):
        _evento(db, p, "publicado", dias)
    r = _aprobar(api, p.id, {"nivel_confianza": 2}, moderador)
    _error(r, 409, "reglas_confianza_no_cumplidas")
    assert r.json()["error"]["details"]["faltan"] == ["identidad_verificada"]


def test_nivel_2_con_reglas_y_vuelta_a_mano(api, db, moderador):
    p = _cumple_reglas(db)
    r = _aprobar(api, p.id, {"aprobar": True, "nivel_confianza": 2}, moderador)
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["estado"] == "aprobado" and r.json()["nivel_confianza"] == 2
    assert r.json()["actividad"]["planes_60_dias"] == 3
    # Sin nivel, no cambia nada.
    assert _aprobar(api, p.id, {"aprobar": True}, moderador).json()["nivel_confianza"] == 2
    # Vuelta a revisión a mano (los niveles 0 y 1 no exigen nada).
    r = _aprobar(api, p.id, {"nivel_confianza": 0}, moderador)
    assert r.status_code == 200 and r.json()["nivel_confianza"] == 0
    db.expire_all()
    avisos = db.scalars(select(Notificacion).where(Notificacion.telefono == p.telefono)).all()
    textos = [n.texto for n in avisos]
    assert len(textos) == 2 and "revisión automática" in textos[0] and "revisaremos" in textos[1]


def test_bot_cambia_nivel_sin_ver_privados(api, db):
    p = _cumple_reglas(db)
    r = _aprobar(api, p.id, {"nivel_confianza": 2}, TOKEN)
    assert r.status_code == 200, r.text
    _sin_privados(r.json())
    assert r.json()["nivel_confianza"] == 2


def test_aprobar_solicitud_directamente_a_nivel_2_exige_reglas(api, db, moderador):
    r = api.post("/api/v1/publicadores", json=NUEVO, headers=TOKEN)
    id = r.json()["id"]
    r = _aprobar(api, id, {"aprobar": True, "nivel_confianza": 2}, moderador)
    _error(r, 409, "reglas_confianza_no_cumplidas")
    assert set(r.json()["error"]["details"]["faltan"]) == {"identidad_verificada", "planes_60_dias", "ultimo_plan"}
    db.expire_all()
    assert db.get(Publicador, id).estado == "solicitado"
    # Con nivel 0 sí se aprueba.
    r = _aprobar(api, id, {"aprobar": True, "nivel_confianza": 0}, moderador)
    assert r.status_code == 200 and r.json()["estado"] == "aprobado"
    _valida(r.json())
    assert r.json()["responsable"]["identidad_verificada"] is False


def test_pausado_no_cambia_de_nivel(api, db, moderador):
    p = _cumple_reglas(db)
    p.estado = "pausado"
    db.commit()
    _error(_aprobar(api, p.id, {"nivel_confianza": 2}, moderador), 409, "estado_invalido")


def test_pausar_devuelve_privados_al_moderador(api, db, moderador):
    r = api.post(f"/api/v1/publicadores/{SENES_CULTURAL}/pausar", json={"que": "publicador", "pausado": True},
                 headers=moderador)
    assert r.status_code == 200, r.text
    _valida(r.json())
    assert r.json()["estado"] == "pausado" and r.json()["responsable"]["dni"] == "12345678Z"


def test_cambiar_nivel_permisos(api, db):
    p = _cumple_reglas(db)
    _error(_aprobar(api, p.id, {"nivel_confianza": 2}, {}), 401, "no_autenticado")
    _error(_aprobar(api, p.id, {"nivel_confianza": 2}, _bearer(CARMEN, "vecino")), 403, "rol_insuficiente")


# --- Panel del bot a través de la API -------------------------------------------------------------

METRICAS = {
    "totales": {"gemini": {"llamadas": 3, "entrada": 1200, "salida": 300, "fallos": 0}},
    "ultimas": [],
    "eventos_en_cola": 0,
    "caida_simulada": False,
}


@pytest.fixture
def bot(api, monkeypatch):
    """Simula el bot en BOT_URL: guarda las llamadas y responde lo que diga `bot.respuesta`."""
    monkeypatch.setenv("BOT_URL", "http://bot-falso:8001/")
    get_settings.cache_clear()

    class Bot:
        llamadas: list[dict] = []
        respuesta: httpx.Response | Exception | None = None

    def falso(metodo, url, json=None, headers=None, timeout=None):
        Bot.llamadas.append({"metodo": metodo, "url": url, "json": json, "headers": headers, "timeout": timeout})
        if isinstance(Bot.respuesta, Exception):
            raise Bot.respuesta
        return Bot.respuesta

    Bot.llamadas = []
    monkeypatch.setattr(httpx, "request", falso)
    return Bot


def test_metricas_del_bot(api, bot, moderador):
    bot.respuesta = httpx.Response(200, json=METRICAS)
    r = api.get("/api/v1/admin/bot/metricas", headers=moderador)
    assert r.status_code == 200, r.text
    assert r.json() == METRICAS
    _valida_con(METRICAS_BOT, r.json())
    llamada = bot.llamadas[0]
    assert (llamada["metodo"], llamada["url"]) == ("GET", "http://bot-falso:8001/metrics")
    assert llamada["headers"] == {"X-Internal-Token": get_settings().internal_token}
    assert llamada["timeout"] == 3.0
    # También con el token interno.
    assert api.get("/api/v1/admin/bot/metricas", headers=TOKEN).status_code == 200


def test_simular_caida(api, bot, moderador):
    bot.respuesta = httpx.Response(200, json={"activa": True})
    r = api.post("/api/v1/admin/bot/simular-caida", json={"activa": True}, headers=moderador)
    assert r.status_code == 200, r.text
    assert r.json() == {"activa": True}
    _valida_con(CAIDA_SIMULADA, r.json())
    llamada = bot.llamadas[0]
    assert (llamada["metodo"], llamada["url"], llamada["json"]) == (
        "POST", "http://bot-falso:8001/admin/simular-caida", {"activa": True},
    )
    assert llamada["headers"]["X-Internal-Token"] == get_settings().internal_token


def test_bot_caido_503(api, bot, moderador):
    bot.respuesta = httpx.ConnectError("conexión rechazada")
    _error(api.get("/api/v1/admin/bot/metricas", headers=moderador), 503, "bot_no_disponible")
    bot.respuesta = httpx.ReadTimeout("lento")
    _error(api.post("/api/v1/admin/bot/simular-caida", json={"activa": False}, headers=moderador),
           503, "bot_no_disponible")


def test_bot_sin_configurar_503(api, moderador):
    _error(api.get("/api/v1/admin/bot/metricas", headers=moderador), 503, "bot_no_disponible")


def test_bot_con_error_502(api, bot, moderador):
    bot.respuesta = httpx.Response(401, json={"detail": "token"})
    r = api.get("/api/v1/admin/bot/metricas", headers=moderador)
    _error(r, 502, "bot_no_disponible")
    assert r.json()["error"]["details"] == {"status": 401}
    bot.respuesta = httpx.Response(200, text="no es json")
    _error(api.get("/api/v1/admin/bot/metricas", headers=moderador), 502, "bot_no_disponible")
    bot.respuesta = httpx.Response(200, json={"otra": "cosa"})
    _error(api.post("/api/v1/admin/bot/simular-caida", json={"activa": True}, headers=moderador),
           502, "bot_no_disponible")


def test_panel_del_bot_permisos(api, bot):
    bot.respuesta = httpx.Response(200, json=METRICAS)
    _error(api.get("/api/v1/admin/bot/metricas"), 401, "no_autenticado")
    _error(api.get("/api/v1/admin/bot/metricas", headers=_bearer(CARMEN, "vecino")), 403, "rol_insuficiente")
    _error(api.post("/api/v1/admin/bot/simular-caida", json={"activa": True}), 401, "no_autenticado")
    _error(api.post("/api/v1/admin/bot/simular-caida", json={"activa": True}, headers=_bearer(CARMEN, "vecino")),
           403, "rol_insuficiente")
    assert bot.llamadas == []


def test_simular_caida_cuerpo_invalido_422(api, bot, moderador):
    _error(api.post("/api/v1/admin/bot/simular-caida", json={}, headers=moderador), 422, "validacion")
    _error(api.post("/api/v1/admin/bot/simular-caida", json={"activa": "si"}, headers=moderador), 422, "validacion")
    assert bot.llamadas == []
