"""Chat del evento (H3.4) y anuncio fijado automático al cambiar la hora (H3.5).

Bot caído (BOT_URL vacío) salvo en los tests que lo simulan: el spam lo deciden las reglas y las preguntas las
contesta el respaldo por reglas sobre la ficha.
"""

import json
import re
from datetime import datetime, timedelta, timezone

import httpx
import pytest
from sqlalchemy import select

from app import chat, moderacion
from app.config import get_settings
from app.inscripciones import fecha_corta
from app.modelos import Evento, Inscripcion, MensajeEvento, Notificacion, Silenciado
from app.seed import sembrar
from tests.test_importar import TOKEN, VIERNES, _error
from tests.test_inscripciones import (
    AMIGOS_VELEFIQUE, ANTONIO, CARMEN, GRAFITI_EN_REVISION, JOSE, LUCIA, PACO, RUTA_SOLIDARIA, _bearer,
)
from tests.test_moderacion import TEXTO_APUESTAS
from tests.test_moderacion_rutas import _validador, _valida

MENSAJE = _validador("./schemas/mensaje_evento.json")
PAGINA = _validador("urn:openapi#/components/schemas/PaginaMensajes")
INEXISTENTE = "00000000-0000-4000-8000-000000000000"
# Lo que no debe aparecer nunca en una respuesta del chat: móviles/fijos españoles o cualquier E.164.
PATRON_TELEFONO = re.compile(r"(?:\+|00)\d[\d\s.-]{6,}\d|(?<!\d)[6789](?:[\s.-]?\d){8}(?!\d)")


@pytest.fixture
def api(cliente, db, monkeypatch):
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    chat.reiniciar_circuito_ficha()
    moderacion.reiniciar_circuito_spam()
    sembrar(db, ahora=VIERNES)
    db.commit()
    yield cliente
    get_settings.cache_clear()
    chat.reiniciar_circuito_ficha()
    moderacion.reiniciar_circuito_spam()


def _url(evento_id: str, msg_id: str | None = None) -> str:
    base = f"/api/v1/eventos/{evento_id}/mensajes"
    return f"{base}/{msg_id}" if msg_id else base


def _evento(db, estado: str = "publicado", plazas: int | None = 20, dias: int = 9) -> Evento:
    inicio = (datetime.now(timezone.utc) + timedelta(days=dias)).replace(hour=9, minute=0, second=0, microsecond=0)
    e = Evento(
        titulo="Ruta por la sierra", categoria="deportiva", municipio="Velefique", lat=37.19, lon=-2.43,
        lugar="Plaza de la Iglesia", fecha_inicio=inicio, fecha_fin=inicio + timedelta(hours=4), precio_eur=0,
        es_gratuito=True, plazas_totales=plazas, plazas_libres=plazas, estado=estado, publicador_id=AMIGOS_VELEFIQUE,
    )
    db.add(e)
    db.commit()
    return e


def _mensajes_de(dato) -> list[dict]:
    if "items" in dato:
        return dato["items"]
    if "mensaje" in dato:
        return [m for m in (dato["mensaje"], dato["respuesta_ia"]) if m is not None]
    return [dato]


def _sin_telefonos(dato) -> None:
    """Ningún campo de teléfono y ningún número en los textos (los UUID y las fechas no cuentan)."""
    assert "telefono" not in json.dumps(dato)
    for m in _mensajes_de(dato):
        for campo in ("texto", "autor_nombre"):
            assert not PATRON_TELEFONO.search(m[campo]), m[campo]


def _listar(api, evento_id: str, headers: dict | None = None) -> list[dict]:
    r = api.get(_url(evento_id), params={"size": 100}, headers=headers or {})
    assert r.status_code == 200, r.text
    _valida(PAGINA, r.json())
    _sin_telefonos(r.json())
    return r.json()["items"]


def _publicar(api, evento_id: str, usuario_id: str, status: int = 201, **cuerpo) -> dict:
    r = api.post(_url(evento_id), json=cuerpo, headers=_bearer(usuario_id))
    assert r.status_code == status, r.text
    if status == 201:
        datos = r.json()
        _valida(MENSAJE, datos["mensaje"])
        if datos["respuesta_ia"] is not None:
            _valida(MENSAJE, datos["respuesta_ia"])
        _sin_telefonos(datos)
    return r.json()


def _avisos(db, evento_id: str, tipo: str = "respuesta") -> list[Notificacion]:
    db.expire_all()
    return list(db.scalars(select(Notificacion).where(Notificacion.evento_id == evento_id, Notificacion.tipo == tipo)))


# --- Leer -----------------------------------------------------------------------------------------


def test_listar_publico_sin_telefonos_y_fijados_primero(api, db):
    db.add_all([
        MensajeEvento(evento_id=RUTA_SOLIDARIA, autor_nombre="Vecino +34 600 111 222", autor_rol="vecino",
                      tipo="comentario", texto="Llamadme al 600 12 34 56 o al +34612345678"),
        MensajeEvento(evento_id=RUTA_SOLIDARIA, autor_nombre="Otro", autor_rol="vecino", tipo="comentario",
                      texto="Mensaje oculto", oculto=True),
    ])
    db.commit()
    items = _listar(api, RUTA_SOLIDARIA)
    assert items and all(m["evento_id"] == RUTA_SOLIDARIA for m in items)
    fijados = [m["fijado"] for m in items]
    assert fijados == sorted(fijados, reverse=True)
    assert not any(m["oculto"] for m in items)
    assert any("[teléfono oculto]" in m["texto"] for m in items)
    for m in items:
        _valida(MENSAJE, m)


def test_ocultos_solo_para_organizador_y_moderador(api, db):
    db.add(MensajeEvento(evento_id=RUTA_SOLIDARIA, autor_nombre="X", autor_rol="vecino", tipo="comentario",
                         texto="Oculto", oculto=True))
    db.commit()
    assert not any(m["oculto"] for m in _listar(api, RUTA_SOLIDARIA, _bearer(CARMEN)))
    for quien in (_bearer(ANTONIO), _bearer(LUCIA), TOKEN):
        assert any(m["oculto"] for m in _listar(api, RUTA_SOLIDARIA, quien))


def test_evento_no_visible_o_inexistente_404(api):
    _error(api.get(_url(GRAFITI_EN_REVISION)), 404, "evento_no_encontrado")
    _error(api.get(_url(INEXISTENTE)), 404, "evento_no_encontrado")
    _error(api.get(_url("no-es-uuid")), 404, "evento_no_encontrado")


# --- Escribir -------------------------------------------------------------------------------------


def test_sin_token_401(api, db):
    e = _evento(db)
    _error(api.post(_url(e.id), json={"texto": "Hola"}), 401, "no_autenticado")
    _error(api.patch(_url(e.id, INEXISTENTE), json={"oculto": True}), 401, "no_autenticado")


def test_comentario_de_vecino(api, db):
    e = _evento(db)
    datos = _publicar(api, e.id, CARMEN, texto="¡Qué ganas!")
    m = datos["mensaje"]
    assert m["autor_id"] == CARMEN and m["autor_rol"] == "vecino" and m["tipo"] == "comentario"
    assert m["fijado"] is False and datos["respuesta_ia"] is None
    assert [x["id"] for x in _listar(api, e.id)] == [m["id"]]


def test_bot_en_nombre_de_un_vecino(api, db):
    e = _evento(db)
    _error(api.post(_url(e.id), json={"texto": "Hola"}, headers=TOKEN), 422, "falta_usuario_id")
    _error(api.post(_url(e.id), json={"texto": "Hola", "usuario_id": INEXISTENTE}, headers=TOKEN),
           404, "usuario_no_encontrado")
    r = api.post(_url(e.id), json={"texto": "Hola", "usuario_id": CARMEN}, headers=TOKEN)
    assert r.status_code == 201, r.text
    assert r.json()["mensaje"]["autor_id"] == CARMEN
    # El bot no puede hacer pasar a un vecino por organizador.
    r = api.post(_url(e.id), json={"texto": "Aviso", "tipo": "anuncio", "usuario_id": CARMEN}, headers=TOKEN)
    _error(r, 403, "prohibido")


def test_no_se_escribe_en_nombre_de_otro(api, db):
    e = _evento(db)
    r = api.post(_url(e.id), json={"texto": "Hola", "usuario_id": JOSE}, headers=_bearer(CARMEN))
    _error(r, 403, "prohibido")


def test_telefono_del_texto_queda_oculto(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, CARMEN, texto="Si alguien va en coche, que me llame al 612 345 678 o +34 950 123 456")["mensaje"]
    assert m["texto"].count("[teléfono oculto]") == 2
    db.expire_all()
    assert "612" not in db.get(MensajeEvento, m["id"]).texto


def test_spam_422(api, db):
    e = _evento(db)
    r = api.post(_url(e.id), json={"texto": TEXTO_APUESTAS}, headers=_bearer(CARMEN))
    _error(r, 422, "mensaje_spam")
    assert r.json()["error"]["details"]["score_spam"] >= get_settings().moderacion_umbral_spam
    assert _listar(api, e.id) == []


def test_en_respuesta_a_de_otro_evento_422(api, db):
    e = _evento(db)
    otro = _evento(db)
    m = _publicar(api, otro.id, CARMEN, texto="Hola")["mensaje"]
    r = api.post(_url(e.id), json={"texto": "Re", "en_respuesta_a": m["id"]}, headers=_bearer(CARMEN))
    _error(r, 422, "mensaje_no_encontrado")


def test_evento_cancelado_vecino_409_organizador_si(api, db):
    e = _evento(db, estado="cancelado")
    _error(api.post(_url(e.id), json={"texto": "Hola"}, headers=_bearer(CARMEN)), 409, "chat_cerrado")
    _publicar(api, e.id, ANTONIO, texto="Lo sentimos, se repetirá en primavera", tipo="anuncio")


# --- Preguntas y respuesta automática -------------------------------------------------------------


def test_pregunta_hora_respuesta_por_reglas(api, db):
    e = _evento(db)
    datos = _publicar(api, e.id, CARMEN, texto="¿A qué hora sale?", tipo="pregunta")
    pregunta, respuesta = datos["mensaje"], datos["respuesta_ia"]
    assert pregunta["tipo"] == "pregunta" and pregunta["respondido_por_ia"] is False
    assert respuesta is not None
    assert respuesta["autor_rol"] == "ia" and respuesta["autor_id"] is None and respuesta["autor_nombre"] == "Asistente"
    assert respuesta["tipo"] == "respuesta" and respuesta["respondido_por_ia"] is True
    assert respuesta["en_respuesta_a"] == pregunta["id"]
    assert fecha_corta(e.fecha_inicio) in respuesta["texto"]
    assert _avisos(db, e.id) == []
    assert [m["id"] for m in _listar(api, e.id)] == [pregunta["id"], respuesta["id"]]


@pytest.mark.parametrize(
    ("pregunta", "esperado"),
    [("¿Dónde es el punto de encuentro?", "Plaza de la Iglesia"), ("¿Cuánto cuesta?", "gratis"),
     ("¿Quedan plazas?", "quedan 20 plazas")],
)
def test_reglas_lugar_precio_plazas(api, db, pregunta, esperado):
    e = _evento(db)
    respuesta = _publicar(api, e.id, CARMEN, texto=pregunta, tipo="pregunta")["respuesta_ia"]
    assert respuesta is not None and esperado in respuesta["texto"]


def test_pregunta_sin_respuesta_avisa_al_organizador(api, db):
    e = _evento(db)
    datos = _publicar(api, e.id, CARMEN, texto="¿Puedo llevar al perro?", tipo="pregunta")
    assert datos["respuesta_ia"] is None
    avisos = _avisos(db, e.id)
    assert len(avisos) == 1 and "Nueva pregunta" in avisos[0].texto and "perro" in avisos[0].texto


def test_organizador_contesta_y_se_avisa_a_quien_pregunto(api, db):
    e = _evento(db)
    pregunta = _publicar(api, e.id, CARMEN, texto="¿Puedo llevar al perro?", tipo="pregunta")["mensaje"]
    respuesta = _publicar(api, e.id, ANTONIO, texto="Sí, atado", en_respuesta_a=pregunta["id"])["mensaje"]
    assert respuesta["autor_rol"] == "publicador" and respuesta["autor_nombre"] != "Asistente"
    avisos = [a for a in _avisos(db, e.id) if a.usuario_id == CARMEN]
    assert len(avisos) == 1 and "Sí, atado" in avisos[0].texto


class _BotFalso:
    """Sustituye httpx.post: /ai/spam limpio y /ai/responder-ficha con la respuesta indicada."""

    def __init__(self, ficha: dict | None, status: int = 200):
        self.ficha, self.status, self.llamadas = ficha, status, []

    def __call__(self, url, json=None, headers=None, timeout=None):
        self.llamadas.append((url, json))
        peticion = httpx.Request("POST", url)
        if url.endswith("/ai/spam"):
            assert json["contexto"] == "mensaje"
            return httpx.Response(200, json={"score_spam": 0.05, "es_spam": False, "motivo": None,
                                             "proveedor_ia": "falso"}, request=peticion)
        return httpx.Response(self.status, json=self.ficha, request=peticion)


@pytest.fixture
def bot(monkeypatch):
    def _poner(ficha: dict | None, status: int = 200) -> _BotFalso:
        falso = _BotFalso(ficha, status)
        monkeypatch.setenv("BOT_URL", "http://bot-falso:8001")
        get_settings.cache_clear()
        monkeypatch.setattr(httpx, "post", falso)
        return falso

    return _poner


def test_pregunta_con_bot_usa_la_ia(api, db, bot):
    e = _evento(db)
    falso = bot({"puede_responder": True, "respuesta": "Hay recorrido corto de 4 km. Info: 600 999 888",
                 "proveedor_ia": "falso"})
    respuesta = _publicar(api, e.id, CARMEN, texto="¿Hay recorrido corto?", tipo="pregunta")["respuesta_ia"]
    assert respuesta["texto"].startswith("Hay recorrido corto de 4 km") and "[teléfono oculto]" in respuesta["texto"]
    url, cuerpo = falso.llamadas[-1]
    assert url.endswith("/ai/responder-ficha")
    assert cuerpo["pregunta"] == "¿Hay recorrido corto?" and cuerpo["evento"]["id"] == e.id


def test_se_pregunta_al_bot_antes_de_escribir_en_la_base(api, db, bot, motor, monkeypatch):
    """Mientras se espera a /ai/responder-ficha, la sesión no ha escrito nada: otra conexión puede escribir
    (en SQLite, sin esperar al bloqueo de escritura) y el mensaje aún no está en la base."""
    e = _evento(db)
    falso = bot({"puede_responder": True, "respuesta": "Sí, hay recorrido corto.", "proveedor_ia": "falso"})
    vistos = []
    original = falso.__call__

    def _mira_la_base(url, json=None, headers=None, timeout=None):
        if url.endswith("/ai/responder-ficha"):
            with motor.connect() as c:
                c.exec_driver_sql("PRAGMA busy_timeout = 0")  # si hubiera un bloqueo de escritura, falla ya
                c.exec_driver_sql("UPDATE eventos SET titulo = titulo WHERE id = ?", (e.id,))
                c.commit()
                vistos.append(c.exec_driver_sql("SELECT count(*) FROM mensajes_evento WHERE evento_id = ?",
                                                (e.id,)).scalar())
        return original(url, json=json, headers=headers, timeout=timeout)

    monkeypatch.setattr(httpx, "post", _mira_la_base)
    respuesta = _publicar(api, e.id, CARMEN, texto="¿Hay recorrido corto?", tipo="pregunta")["respuesta_ia"]
    assert respuesta is not None
    assert vistos == [0]


def test_bot_no_sabe_avisa_al_organizador(api, db, bot):
    e = _evento(db)
    bot({"puede_responder": False, "respuesta": None})
    # Aunque las reglas sabrían la hora, manda el bot: no está seguro, decide el organizador.
    assert _publicar(api, e.id, CARMEN, texto="¿A qué hora sale?", tipo="pregunta")["respuesta_ia"] is None
    assert len(_avisos(db, e.id)) == 1


def test_bot_sin_responder_ficha_cae_a_reglas(api, db, bot):
    e = _evento(db)
    bot({"detail": "Not Found"}, status=404)
    respuesta = _publicar(api, e.id, CARMEN, texto="¿A qué hora sale?", tipo="pregunta")["respuesta_ia"]
    assert respuesta is not None and fecha_corta(e.fecha_inicio) in respuesta["texto"]


# --- Anuncios, fijar y ocultar --------------------------------------------------------------------


def test_vecino_no_publica_anuncios(api, db):
    e = _evento(db)
    r = api.post(_url(e.id), json={"texto": "Aviso", "tipo": "anuncio"}, headers=_bearer(CARMEN))
    _error(r, 403, "prohibido")


@pytest.mark.parametrize("usuario", [ANTONIO, LUCIA])
def test_organizador_y_moderador_publican_anuncio_fijado(api, db, usuario):
    e = _evento(db)
    _publicar(api, e.id, CARMEN, texto="Primero")
    m = _publicar(api, e.id, usuario, texto="Traed agua", tipo="anuncio")["mensaje"]
    assert m["tipo"] == "anuncio" and m["fijado"] is True
    assert m["autor_rol"] == ("publicador" if usuario == ANTONIO else "moderador")
    assert _listar(api, e.id)[0]["id"] == m["id"]


def test_publicador_de_otro_evento_es_vecino(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, PACO, texto="Allí estaremos")["mensaje"]
    assert m["autor_rol"] == "vecino"
    _error(api.post(_url(e.id), json={"texto": "x", "tipo": "anuncio"}, headers=_bearer(PACO)), 403, "prohibido")


def test_fijar_y_ocultar_permisos(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, JOSE, texto="Comentario")["mensaje"]
    _error(api.patch(_url(e.id, m["id"]), json={"fijado": True}, headers=_bearer(CARMEN)), 403, "prohibido")
    _error(api.patch(_url(e.id, m["id"]), json={"oculto": True}, headers=_bearer(CARMEN)), 403, "prohibido")

    r = api.patch(_url(e.id, m["id"]), json={"fijado": True}, headers=_bearer(ANTONIO))
    assert r.status_code == 200, r.text
    _valida(MENSAJE, r.json())
    assert r.json()["fijado"] is True

    r = api.patch(_url(e.id, m["id"]), json={"oculto": True}, headers=_bearer(LUCIA))
    assert r.status_code == 200 and r.json()["oculto"] is True
    assert _listar(api, e.id) == []
    assert _listar(api, e.id, _bearer(LUCIA))[0]["id"] == m["id"]

    r = api.patch(_url(e.id, m["id"]), json={"oculto": False, "fijado": False}, headers=TOKEN)
    assert r.status_code == 200 and r.json()["oculto"] is False and r.json()["fijado"] is False


def test_autor_oculta_el_suyo_pero_no_lo_fija(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, CARMEN, texto="Me equivoqué de evento")["mensaje"]
    _error(api.patch(_url(e.id, m["id"]), json={"fijado": True}, headers=_bearer(CARMEN)), 403, "prohibido")
    r = api.patch(_url(e.id, m["id"]), json={"oculto": True}, headers=_bearer(CARMEN))
    assert r.status_code == 200 and r.json()["oculto"] is True


def test_autor_no_vuelve_a_mostrar_un_mensaje_ocultado_por_moderacion(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, CARMEN, texto="Comentario que la moderadora oculta")["mensaje"]
    r = api.patch(_url(e.id, m["id"]), json={"oculto": True}, headers=_bearer(LUCIA))
    assert r.status_code == 200 and r.json()["oculto"] is True

    _error(api.patch(_url(e.id, m["id"]), json={"oculto": False}, headers=_bearer(CARMEN)), 403, "prohibido")
    _error(api.patch(_url(e.id, m["id"]), json={"oculto": True, "fijado": False}, headers=_bearer(CARMEN)), 403,
           "prohibido")
    _error(api.patch(_url(e.id, m["id"]), json={}, headers=_bearer(CARMEN)), 403, "prohibido")
    assert _listar(api, e.id) == []
    assert _listar(api, e.id, _bearer(LUCIA))[0]["oculto"] is True


def test_patch_mensaje_404(api, db):
    e = _evento(db)
    otro = _evento(db)
    m = _publicar(api, otro.id, CARMEN, texto="Hola")["mensaje"]
    _error(api.patch(_url(e.id, m["id"]), json={"oculto": True}, headers=_bearer(ANTONIO)), 404, "mensaje_no_encontrado")
    _error(api.patch(_url(e.id, INEXISTENTE), json={"oculto": True}, headers=_bearer(ANTONIO)), 404,
           "mensaje_no_encontrado")


# --- Silenciar (H3.4) ------------------------------------------------------------------------------


def _silenciar(api, evento_id: str, msg_id: str, headers: dict, valor: bool = True):
    return api.patch(_url(evento_id, msg_id), json={"silenciar_autor": valor}, headers=headers)


@pytest.mark.parametrize("gestor", [ANTONIO, LUCIA])
def test_organizador_o_moderador_silencia_y_des_silencia(api, db, gestor):
    e = _evento(db)
    m = _publicar(api, e.id, CARMEN, texto="Comentario")["mensaje"]
    r = _silenciar(api, e.id, m["id"], _bearer(gestor))
    assert r.status_code == 200, r.text
    _valida(MENSAJE, r.json())
    assert db.get(Silenciado, (e.id, CARMEN)).por == gestor

    _error(api.post(_url(e.id), json={"texto": "Otra vez"}, headers=_bearer(CARMEN)), 403, "usuario_silenciado")
    r = api.post(_url(e.id), json={"texto": "Por el bot", "usuario_id": CARMEN}, headers=TOKEN)
    _error(r, 403, "usuario_silenciado")
    # Solo en ese evento: en otro sigue escribiendo; y silenciar dos veces no falla.
    _publicar(api, _evento(db).id, CARMEN, texto="En otro evento sí")
    assert _silenciar(api, e.id, m["id"], _bearer(gestor)).status_code == 200

    assert _silenciar(api, e.id, m["id"], _bearer(gestor), False).status_code == 200
    db.expire_all()
    assert db.get(Silenciado, (e.id, CARMEN)) is None
    _publicar(api, e.id, CARMEN, texto="Ya puedo")


def test_bot_silencia_con_token(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, JOSE, texto="Comentario")["mensaje"]
    assert _silenciar(api, e.id, m["id"], TOKEN).status_code == 200
    assert db.get(Silenciado, (e.id, JOSE)).por == "bot"


def test_vecino_ni_autor_pueden_silenciar(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, JOSE, texto="Comentario")["mensaje"]
    _error(_silenciar(api, e.id, m["id"], _bearer(CARMEN)), 403, "prohibido")
    _error(_silenciar(api, e.id, m["id"], _bearer(JOSE)), 403, "prohibido")
    _error(_silenciar(api, e.id, m["id"], _bearer(PACO)), 403, "prohibido")
    assert db.get(Silenciado, (e.id, JOSE)) is None


@pytest.mark.parametrize("autor", [ANTONIO, LUCIA])
def test_no_se_silencia_al_organizador_ni_a_un_moderador(api, db, autor):
    e = _evento(db)
    m = _publicar(api, e.id, autor, texto="Aviso", tipo="anuncio")["mensaje"]
    otro = LUCIA if autor == ANTONIO else ANTONIO
    _error(_silenciar(api, e.id, m["id"], _bearer(otro)), 409, "no_silenciable")
    assert db.get(Silenciado, (e.id, autor)) is None


def test_no_se_silencia_a_la_ia(api, db):
    e = _evento(db)
    respuesta = _publicar(api, e.id, CARMEN, texto="¿A qué hora empieza?", tipo="pregunta")["respuesta_ia"]
    assert respuesta is not None
    _error(_silenciar(api, e.id, respuesta["id"], _bearer(LUCIA)), 409, "no_silenciable")


def test_silenciar_y_ocultar_a_la_vez(api, db):
    e = _evento(db)
    m = _publicar(api, e.id, CARMEN, texto="Comentario")["mensaje"]
    r = api.patch(_url(e.id, m["id"]), json={"oculto": True, "silenciar_autor": True}, headers=_bearer(ANTONIO))
    assert r.status_code == 200 and r.json()["oculto"] is True
    assert db.get(Silenciado, (e.id, CARMEN)) is not None


# --- Cambio de hora (H3.5) ------------------------------------------------------------------------


def test_cambio_de_hora_crea_anuncio_fijado(api, db):
    e = _evento(db)
    _publicar(api, e.id, CARMEN, texto="Allí estaré")
    nueva = (e.fecha_inicio + timedelta(hours=1)).isoformat()
    r = api.patch(f"/api/v1/eventos/{e.id}", json={"fecha_inicio": nueva}, headers=_bearer(ANTONIO))
    assert r.status_code == 200, r.text
    primero = _listar(api, e.id)[0]
    assert primero["tipo"] == "anuncio" and primero["fijado"] is True and primero["autor_rol"] == "publicador"
    assert "cambia de hora" in primero["texto"]
    assert fecha_corta(e.fecha_inicio + timedelta(hours=1)) in primero["texto"]


def test_editar_sin_cambiar_hora_no_crea_anuncio(api, db):
    e = _evento(db)
    r = api.patch(f"/api/v1/eventos/{e.id}", json={"descripcion": "Nueva descripción"}, headers=_bearer(ANTONIO))
    assert r.status_code == 200, r.text
    assert _listar(api, e.id) == []


# --- Planes terminados: solo comentarios y fotos de quien fue ----------------------------------------------

FOTO = "data:image/webp;base64,UklGRiQAAABXRUJQVlA4IBgAAAAwAQCdASoBAAEAAwA0JaQAA3AA/vuUAAA="
CINE_PASADO = "4a5a0000-0000-4000-8000-000000000001"  # eventos_pasados.json (finalizado)


def _inscribir(db, evento: Evento, usuario_id: str, estado: str = "asistio") -> None:
    db.add(Inscripcion(evento_id=evento.id, usuario_id=usuario_id, estado=estado, plazas=1, canal="web"))
    db.commit()


@pytest.fixture(params=["finalizado", "publicado_pasado"])
def pasado(request, db):
    if request.param == "finalizado":
        return _evento(db, estado="finalizado", dias=-10)
    return _evento(db, dias=-10)


def test_plan_pasado_comentario_con_foto_de_inscrito(api, db, pasado):
    _inscribir(db, pasado, CARMEN, "asistio")
    m = _publicar(api, pasado.id, CARMEN, texto="¡Qué buen día!", imagen_url=FOTO)["mensaje"]
    assert m["tipo"] == "comentario" and m["imagen_url"] == FOTO
    # GET (público, sin sesión) muestra la foto
    items = _listar(api, pasado.id)
    assert [i["imagen_url"] for i in items] == [FOTO]
    for i in items:
        _valida(MENSAJE, i)
    # Inscrito que luego no fue, o confirmado sin marcar asistencia, también
    _inscribir(db, pasado, JOSE, "no_asistio")
    _publicar(api, pasado.id, JOSE, texto="No pude ir, qué pena", imagen_url="https://ejemplo.org/foto.jpg")


def test_plan_pasado_foto_de_no_inscrito_403(api, db, pasado):
    _error(api.post(_url(pasado.id), json={"texto": "Mira", "imagen_url": FOTO}, headers=_bearer(CARMEN)),
           403, "sin_permiso")
    # Una inscripción cancelada o en lista de espera no cuenta
    _inscribir(db, pasado, JOSE, "cancelada")
    _error(api.post(_url(pasado.id), json={"texto": "Mira", "imagen_url": FOTO}, headers=_bearer(JOSE)),
           403, "sin_permiso")
    # Sin foto, cualquiera con sesión puede comentar
    m = _publicar(api, pasado.id, CARMEN, texto="Me hubiera gustado ir")["mensaje"]
    assert m["imagen_url"] is None


def test_plan_pasado_foto_de_organizador_y_moderador(api, db, pasado):
    assert _publicar(api, pasado.id, ANTONIO, texto="Gracias a todos", imagen_url=FOTO)["mensaje"]["imagen_url"] == FOTO
    assert _publicar(api, pasado.id, LUCIA, texto="Bonita jornada", imagen_url=FOTO)["mensaje"]["imagen_url"] == FOTO


def test_plan_pasado_bot_en_nombre_de_inscrito(api, db, pasado):
    _inscribir(db, pasado, CARMEN, "confirmada")
    r = api.post(_url(pasado.id), json={"texto": "Foto", "imagen_url": FOTO, "usuario_id": CARMEN}, headers=TOKEN)
    assert r.status_code == 201, r.text
    _valida(MENSAJE, r.json()["mensaje"])
    r = api.post(_url(pasado.id), json={"texto": "Foto", "imagen_url": FOTO, "usuario_id": JOSE}, headers=TOKEN)
    _error(r, 403, "sin_permiso")


@pytest.mark.parametrize("tipo", ["pregunta", "anuncio"])
def test_plan_pasado_solo_comentarios_409(api, db, pasado, tipo):
    _inscribir(db, pasado, CARMEN)
    for quien in (CARMEN, ANTONIO):
        r = api.post(_url(pasado.id), json={"texto": "¿Se repite?", "tipo": tipo}, headers=_bearer(quien))
        _error(r, 409, "evento_finalizado")
    assert _listar(api, pasado.id) == []


@pytest.mark.parametrize(
    ("imagen", "status", "code"),
    [
        ("data:image/svg+xml;base64,PHN2Zz4=", 422, "imagen_invalida"),
        ("data:text/html;base64,PGI+", 422, "imagen_invalida"),
        ("data:image/png;base64,no es base64!", 422, "imagen_invalida"),
        ("data:image/png;base64,", 422, "imagen_invalida"),
        ("javascript:alert(1)", 422, "imagen_invalida"),
        ("ftp://ejemplo.org/a.png", 422, "imagen_invalida"),
        ("https://" + "a" * 2100 + ".org/a.png", 422, "imagen_invalida"),
        ("data:image/jpeg;base64," + "A" * (2 * 1024 * 1024 * 4 // 3 + 8), 413, "imagen_demasiado_grande"),
    ],
)
def test_plan_pasado_foto_invalida(api, db, pasado, imagen, status, code):
    _inscribir(db, pasado, CARMEN)
    _error(api.post(_url(pasado.id), json={"texto": "Foto", "imagen_url": imagen}, headers=_bearer(CARMEN)),
           status, code)
    assert _listar(api, pasado.id) == []


def test_foto_en_plan_futuro_403(api, db):
    e = _evento(db)
    _inscribir(db, e, CARMEN, "confirmada")
    _error(api.post(_url(e.id), json={"texto": "Foto", "imagen_url": FOTO}, headers=_bearer(CARMEN)),
           403, "sin_permiso")
    _error(api.post(_url(e.id), json={"texto": "Foto", "imagen_url": FOTO}, headers=_bearer(ANTONIO)),
           403, "sin_permiso")


def test_plan_cancelado_sigue_con_chat_cerrado(api, db):
    e = _evento(db, estado="cancelado", dias=-10)
    _error(api.post(_url(e.id), json={"texto": "Hola"}, headers=_bearer(CARMEN)), 409, "chat_cerrado")


def test_chat_publico_de_plan_pasado_del_seed(api, db):
    # La ficha y el chat de los planes pasados del seed se pueden abrir sin sesión
    r = api.get(f"/api/v1/eventos/{CINE_PASADO}")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "finalizado"
    ficha = db.get(Evento, CINE_PASADO)
    _inscribir(db, ficha, CARMEN)
    m = _publicar(api, CINE_PASADO, CARMEN, texto="Gran noche de cine", imagen_url=FOTO)["mensaje"]
    assert [i["id"] for i in _listar(api, CINE_PASADO) if i["imagen_url"] == FOTO] == [m["id"]]


def test_mas_de_8_mensajes_por_minuto_da_429(api, db):
    e = _evento(db)
    for i in range(8):
        _publicar(api, e.id, CARMEN, texto=f"Mensaje {i}")
    r = api.post(_url(e.id), json={"texto": "Uno más"}, headers=_bearer(CARMEN))
    _error(r, 429, "demasiados_mensajes")
    # Otra persona no se ve afectada, y la moderadora no tiene límite
    _publicar(api, e.id, JOSE, texto="Yo también voy")
    for i in range(9):
        _publicar(api, e.id, LUCIA, texto=f"Aviso {i}")
