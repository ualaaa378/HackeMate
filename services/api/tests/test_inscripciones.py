"""Inscripciones con plazas y lista de espera (H3.2) y aviso a los inscritos al cambiar un evento (H3.5).
Bot caído (BOT_URL vacío): los avisos se guardan en cola y nada falla."""

import threading
from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import sessionmaker

from app.config import get_settings
from app.inscripciones import cancelar, fecha_corta, reactivar, tomar_plazas
from app.modelos import Evento, Inscripcion, Notificacion
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import TOKEN, VIERNES, _error
from tests.test_moderacion_rutas import _validador, _valida

INSCRIPCION = _validador("./schemas/inscripcion.json")
EVENTO = _validador("./schemas/evento.json")

CARMEN = "5a5e0000-0000-4000-8000-000000000001"
LUCIA = "5a5e0000-0000-4000-8000-000000000002"  # moderadora
ANTONIO = "5a5e0000-0000-4000-8000-000000000003"  # organizador (Amigos de Velefique)
PACO = "5a5e0000-0000-4000-8000-000000000004"  # publicador de otro pueblo
JOSE = "5a5e0000-0000-4000-8000-000000000005"
AMIGOS_VELEFIQUE = "7b0d1c52-3f7e-4c41-9a51-0f2a9c1e0a01"
RUTA_SOLIDARIA = "1e5d0000-0000-4000-8000-000000000001"
GRAFITI_EN_REVISION = "1e5d0000-0000-4000-8000-000000000009"
INEXISTENTE = "00000000-0000-4000-8000-000000000000"


def _bearer(usuario_id: str) -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, 'vecino')}"}


def _url(evento_id: str, insc_id: str | None = None) -> str:
    base = f"/api/v1/eventos/{evento_id}/inscripciones"
    return f"{base}/{insc_id}" if insc_id else base


@pytest.fixture
def api(cliente, db, monkeypatch):
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    sembrar(db, ahora=VIERNES)
    db.commit()
    yield cliente
    get_settings.cache_clear()


def _evento(db, plazas: int | None = 1, estado: str = "publicado", dias: int = 10) -> str:
    inicio = datetime.now(timezone.utc) + timedelta(days=dias)
    e = Evento(
        titulo="Taller de prueba", categoria="cultural", municipio="Velefique", lat=37.19, lon=-2.43,
        fecha_inicio=inicio, fecha_fin=inicio + timedelta(hours=2), plazas_totales=plazas, plazas_libres=plazas,
        estado=estado, publicador_id=AMIGOS_VELEFIQUE,
    )
    db.add(e)
    db.commit()
    return e.id


def _inscribir(api, evento_id: str, usuario_id: str, **cuerpo) -> dict:
    r = api.post(_url(evento_id), json=cuerpo or None, headers=_bearer(usuario_id))
    assert r.status_code == 201, r.text
    _valida(INSCRIPCION, r.json())
    return r.json()


def _plazas_libres(api, evento_id: str) -> int | None:
    return api.get(f"/api/v1/eventos/{evento_id}", headers=TOKEN).json()["plazas_libres"]


def _avisos(db, tipo: str, evento_id: str) -> list[Notificacion]:
    db.expire_all()
    return list(db.scalars(select(Notificacion).where(Notificacion.tipo == tipo, Notificacion.evento_id == evento_id)))


# --- Inscribirse ----------------------------------------------------------------------------------


def test_sin_token_401(api, db):
    _error(api.post(_url(_evento(db))), 401, "no_autenticado")
    _error(api.get(_url(RUTA_SOLIDARIA)), 401, "no_autenticado")


def test_una_plaza_el_segundo_va_a_lista_de_espera(api, db):
    id = _evento(db, plazas=1)
    primera = _inscribir(api, id, CARMEN)
    assert primera["estado"] == "confirmada" and primera["posicion_espera"] is None and primera["canal"] == "web"
    assert _plazas_libres(api, id) == 0
    segunda = _inscribir(api, id, JOSE)
    assert segunda["estado"] == "lista_espera" and segunda["posicion_espera"] == 1
    tercera = _inscribir(api, id, PACO)
    assert tercera["estado"] == "lista_espera" and tercera["posicion_espera"] == 2
    ficha = api.get(f"/api/v1/eventos/{id}", headers=TOKEN).json()
    _valida(EVENTO, ficha)
    assert ficha["inscritos"] == 1 and ficha["plazas_libres"] == 0


def test_sin_limite_siempre_confirmada(api, db):
    id = _evento(db, plazas=None)
    for u in (CARMEN, JOSE, PACO):
        assert _inscribir(api, id, u)["estado"] == "confirmada"
    assert _plazas_libres(api, id) is None


def test_varias_plazas_que_no_caben_van_a_espera(api, db):
    id = _evento(db, plazas=2)
    assert _inscribir(api, id, CARMEN, plazas=3)["estado"] == "lista_espera"
    assert _inscribir(api, id, JOSE, plazas=2)["estado"] == "confirmada"
    assert _plazas_libres(api, id) == 0


def test_doble_inscripcion_409(api, db):
    id = _evento(db)
    _inscribir(api, id, CARMEN)
    _error(api.post(_url(id), headers=_bearer(CARMEN)), 409, "ya_inscrito")


def test_cancelar_sube_al_siguiente_y_le_avisa(api, db):
    id = _evento(db, plazas=1)
    carmen = _inscribir(api, id, CARMEN)
    jose = _inscribir(api, id, JOSE)
    paco = _inscribir(api, id, PACO)

    r = api.delete(_url(id, carmen["id"]), headers=_bearer(CARMEN))
    assert r.status_code == 200, r.text
    _valida(INSCRIPCION, r.json())
    assert r.json()["estado"] == "cancelada"

    lista = {i["usuario_id"]: i for i in api.get(_url(id), headers=TOKEN).json()}
    assert lista[JOSE]["estado"] == "confirmada" and lista[JOSE]["posicion_espera"] is None
    assert lista[PACO]["estado"] == "lista_espera" and lista[PACO]["posicion_espera"] == 1
    assert _plazas_libres(api, id) == 0

    avisos = _avisos(db, "confirmacion", id)
    assert [a.usuario_id for a in avisos] == [JOSE]
    assert "Taller de prueba" in avisos[0].texto and avisos[0].estado_envio == "pendiente"
    assert jose["id"] != paco["id"]


def test_cancelar_desde_la_espera_renumera_y_no_libera_plazas(api, db):
    id = _evento(db, plazas=1)
    _inscribir(api, id, CARMEN)
    jose = _inscribir(api, id, JOSE)
    _inscribir(api, id, PACO)
    assert api.delete(_url(id, jose["id"]), headers=_bearer(JOSE)).status_code == 200
    lista = {i["usuario_id"]: i for i in api.get(_url(id), headers=TOKEN).json()}
    assert lista[CARMEN]["estado"] == "confirmada" and lista[PACO]["posicion_espera"] == 1
    assert _plazas_libres(api, id) == 0 and _avisos(db, "confirmacion", id) == []


def test_volver_a_apuntarse_tras_cancelar(api, db):
    id = _evento(db, plazas=1)
    carmen = _inscribir(api, id, CARMEN)
    api.delete(_url(id, carmen["id"]), headers=_bearer(CARMEN))
    otra = _inscribir(api, id, CARMEN)
    assert otra["id"] == carmen["id"] and otra["estado"] == "confirmada"
    assert _plazas_libres(api, id) == 0


def test_cancelar_permisos_y_404(api, db):
    id = _evento(db)
    carmen = _inscribir(api, id, CARMEN)
    _error(api.delete(_url(id, carmen["id"]), headers=_bearer(JOSE)), 403, "prohibido")
    _error(api.delete(_url(id, carmen["id"]), headers=_bearer(PACO)), 403, "prohibido")
    _error(api.delete(_url(id, INEXISTENTE), headers=_bearer(CARMEN)), 404, "inscripcion_no_encontrada")
    _error(api.delete(_url(RUTA_SOLIDARIA, carmen["id"]), headers=_bearer(CARMEN)), 404, "inscripcion_no_encontrada")
    # El organizador y la moderadora sí pueden
    assert api.delete(_url(id, carmen["id"]), headers=_bearer(ANTONIO)).status_code == 200
    jose = _inscribir(api, id, JOSE)
    assert api.delete(_url(id, jose["id"]), headers=_bearer(LUCIA)).json()["estado"] == "cancelada"


def test_el_bot_inscribe_en_nombre_del_vecino(api, db):
    id = _evento(db)
    r = api.post(_url(id), json={"usuario_id": JOSE}, headers=TOKEN)
    assert r.status_code == 201, r.text
    _valida(INSCRIPCION, r.json())
    assert r.json()["usuario_id"] == JOSE and r.json()["canal"] == "whatsapp"
    _error(api.post(_url(id), headers=TOKEN), 422, "falta_usuario_id")
    _error(api.post(_url(id), json={"usuario_id": INEXISTENTE}, headers=TOKEN), 404, "usuario_no_encontrado")
    # Un vecino no se apunta en nombre de otro
    _error(api.post(_url(id), json={"usuario_id": JOSE}, headers=_bearer(CARMEN)), 403, "prohibido")


def test_solo_eventos_publicados_y_futuros(api, db):
    _error(api.post(_url(GRAFITI_EN_REVISION), headers=_bearer(CARMEN)), 404, "evento_no_encontrado")
    _error(api.post(_url(INEXISTENTE), headers=_bearer(CARMEN)), 404, "evento_no_encontrado")
    _error(api.post(_url(_evento(db, estado="cancelado")), headers=_bearer(CARMEN)), 409, "evento_no_inscribible")
    _error(api.post(_url(_evento(db, dias=-3)), headers=_bearer(CARMEN)), 409, "evento_terminado")


# --- Lista de inscritos y asistencia --------------------------------------------------------------


def test_lista_solo_organizador_y_moderador(api, db):
    _error(api.get(_url(RUTA_SOLIDARIA), headers=_bearer(JOSE)), 403, "prohibido")
    _error(api.get(_url(RUTA_SOLIDARIA), headers=_bearer(PACO)), 403, "prohibido")  # publicador de otro evento
    for cabeceras in (_bearer(ANTONIO), _bearer(LUCIA), TOKEN):
        r = api.get(_url(RUTA_SOLIDARIA), headers=cabeceras)
        assert r.status_code == 200, r.text
        assert r.json(), "la Ruta Solidaria tiene inscritos en el seed"
        for i in r.json():
            _valida(INSCRIPCION, i)
            assert "telefono" not in i
        assert any(i["usuario_id"] == JOSE and i["usuario_nombre"] == "José" for i in r.json())


def test_marcar_asistencia(api, db):
    id = _evento(db, plazas=1)
    carmen = _inscribir(api, id, CARMEN)
    jose = _inscribir(api, id, JOSE)
    _error(api.patch(_url(id, carmen["id"]), json={"estado": "asistio"}, headers=_bearer(CARMEN)), 403, "prohibido")
    r = api.patch(_url(id, carmen["id"]), json={"estado": "asistio"}, headers=_bearer(ANTONIO))
    assert r.status_code == 200, r.text
    _valida(INSCRIPCION, r.json())
    assert r.json()["estado"] == "asistio"
    _error(api.patch(_url(id, jose["id"]), json={"estado": "asistio"}, headers=TOKEN), 409, "inscripcion_sin_plaza")
    _error(api.patch(_url(id, carmen["id"]), json={"estado": "cancelada"}, headers=TOKEN), 422, "validacion")
    # Con la asistencia marcada ya no se cancela
    _error(api.delete(_url(id, carmen["id"]), headers=_bearer(CARMEN)), 409, "inscripcion_cerrada")


# --- Concurrencia ---------------------------------------------------------------------------------


def test_la_ultima_plaza_no_se_vende_dos_veces(api, db, motor):
    """La sesión B ha leído el evento con 1 plaza libre; mientras, A se la lleva. B no la vende otra vez."""
    id = _evento(db, plazas=1)
    sesion_b = sessionmaker(bind=motor, expire_on_commit=False)()
    try:
        evento_b = sesion_b.get(Evento, id)
        assert evento_b.plazas_libres == 1
        assert _inscribir(api, id, CARMEN)["estado"] == "confirmada"
        assert tomar_plazas(sesion_b, evento_b, 1) is False
        sesion_b.rollback()
    finally:
        sesion_b.close()
    assert _inscribir(api, id, JOSE)["estado"] == "lista_espera"
    assert _plazas_libres(api, id) == 0


def test_hilos_a_la_vez_por_la_ultima_plaza(api, db, motor):
    id = _evento(db, plazas=1)
    fabrica = sessionmaker(bind=motor, expire_on_commit=False)
    salida = threading.Barrier(5)
    resultados = []

    def _intentar():
        with fabrica() as s:
            evento = s.get(Evento, id)
            salida.wait()
            resultados.append(tomar_plazas(s, evento, 1))
            s.commit()

    hilos = [threading.Thread(target=_intentar) for _ in range(5)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(30)
    assert sorted(resultados) == [False, False, False, False, True]
    assert _plazas_libres(api, id) == 0


def _a_la_vez(motor, n: int, accion) -> list:
    """Lanza `accion(sesion)` en `n` hilos que salen a la vez (cada uno con su sesión) y hace commit."""
    fabrica = sessionmaker(bind=motor, expire_on_commit=False)
    salida = threading.Barrier(n)
    resultados = []

    def _hilo():
        with fabrica() as s:
            preparado = accion(s, None)  # lee el estado antes de la salida, como haría cada petición
            salida.wait()
            resultados.append(accion(s, preparado))
            s.commit()

    hilos = [threading.Thread(target=_hilo) for _ in range(n)]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(30)
    return resultados


def test_hilos_cancelan_a_la_vez_la_misma_inscripcion(api, db, motor):
    id = _evento(db, plazas=3)
    insc = _inscribir(api, id, CARMEN)
    assert _plazas_libres(api, id) == 2

    def _cancelar(s, preparado):
        if preparado is None:
            evento, inscripcion = s.get(Evento, id), s.get(Inscripcion, insc["id"])
            assert inscripcion.estado == "confirmada"
            return evento, inscripcion
        return cancelar(s, *preparado)[0]

    resultados = _a_la_vez(motor, 6, _cancelar)
    assert sorted(resultados) == [False] * 5 + [True]
    assert _plazas_libres(api, id) == 3  # una sola plaza devuelta


def test_peticiones_delete_repetidas_devuelven_200_y_una_plaza(api, db):
    id = _evento(db, plazas=3)
    insc = _inscribir(api, id, CARMEN)
    for _ in range(3):
        r = api.delete(_url(id, insc["id"]), headers=_bearer(CARMEN))
        assert r.status_code == 200, r.text
        assert r.json()["estado"] == "cancelada"
    assert _plazas_libres(api, id) == 3


def test_hilos_se_reinscriben_a_la_vez_tras_cancelar(api, db, motor):
    id = _evento(db, plazas=6)
    insc = _inscribir(api, id, CARMEN)
    api.delete(_url(id, insc["id"]), headers=_bearer(CARMEN))
    assert _plazas_libres(api, id) == 6

    def _reactivar(s, preparado):
        if preparado is None:
            evento, inscripcion = s.get(Evento, id), s.get(Inscripcion, insc["id"])
            assert inscripcion.estado == "cancelada"
            return evento, inscripcion
        return reactivar(s, *preparado, plazas=1, canal="web")

    resultados = _a_la_vez(motor, 6, _reactivar)
    assert sorted(resultados) == [False] * 5 + [True]
    assert _plazas_libres(api, id) == 5  # una sola plaza descontada
    r = api.post(_url(id), headers=_bearer(CARMEN))
    assert r.status_code == 409 and r.json()["error"]["code"] == "ya_inscrito"


def test_hilos_cancelan_y_promocionan_a_una_sola_de_la_espera(api, db, motor):
    id = _evento(db, plazas=1)
    carmen = _inscribir(api, id, CARMEN)
    assert _inscribir(api, id, JOSE)["estado"] == "lista_espera"

    def _cancelar(s, preparado):
        if preparado is None:
            return s.get(Evento, id), s.get(Inscripcion, carmen["id"])
        return cancelar(s, *preparado)[0]

    _a_la_vez(motor, 4, _cancelar)
    db.expire_all()
    jose = db.scalar(select(Inscripcion).where(Inscripcion.evento_id == id, Inscripcion.usuario_id == JOSE))
    assert jose.estado == "confirmada"
    assert _plazas_libres(api, id) == 0
    assert len(_avisos(db, "confirmacion", id)) == 1


# --- Cambios en el evento (H3.5) ------------------------------------------------------------------


def test_cambio_de_hora_avisa_a_cada_inscrito(api, db):
    # En el seed José ya está confirmado en la Ruta Solidaria; se apuntan dos más y uno cancela.
    _inscribir(api, RUTA_SOLIDARIA, CARMEN)
    paco = _inscribir(api, RUTA_SOLIDARIA, PACO)
    api.delete(_url(RUTA_SOLIDARIA, paco["id"]), headers=_bearer(PACO))
    db.expire_all()
    activos = db.scalars(
        select(Inscripcion.usuario_id).where(
            Inscripcion.evento_id == RUTA_SOLIDARIA, Inscripcion.estado.in_(("confirmada", "lista_espera"))
        )
    ).all()
    assert sorted(activos) == sorted([CARMEN, JOSE])
    del_seed = {a.id for a in _avisos(db, "cambio_evento", RUTA_SOLIDARIA)}  # el seed trae un aviso de ejemplo

    r = api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"fecha_inicio": "2026-11-29T10:00:00+01:00"}, headers=TOKEN)
    assert r.status_code == 200, r.text
    _valida(EVENTO, r.json())

    avisos = [a for a in _avisos(db, "cambio_evento", RUTA_SOLIDARIA) if a.id not in del_seed]
    assert sorted(a.usuario_id for a in avisos) == sorted(activos)
    for a in avisos:
        assert "II Ruta Solidaria Sierra de Velefique" in a.texto
        assert "cambia de hora: ahora el dom 29 a las 10:00" in a.texto  # 29-11-2026 es domingo
        assert a.estado_envio == "pendiente"  # bot caído: en cola

    # Sin cambio real de hora no se avisa otra vez
    api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"fecha_inicio": "2026-11-29T10:00:00+01:00"}, headers=TOKEN)
    assert len(_avisos(db, "cambio_evento", RUTA_SOLIDARIA)) == len(del_seed) + len(activos)


def test_cancelar_evento_y_cambiar_lugar_avisan(api, db):
    id = _evento(db, plazas=1)
    _inscribir(api, id, CARMEN)
    _inscribir(api, id, JOSE)  # lista de espera: también se le avisa
    api.patch(f"/api/v1/eventos/{id}", json={"lugar": "Plaza del pueblo"}, headers=TOKEN)
    avisos = _avisos(db, "cambio_evento", id)
    assert len(avisos) == 2 and all("cambia de lugar: ahora en Plaza del pueblo" in a.texto for a in avisos)
    api.patch(f"/api/v1/eventos/{id}", json={"estado": "cancelado"}, headers=TOKEN)
    avisos = _avisos(db, "cambio_evento", id)
    assert len(avisos) == 4 and sum("Se ha cancelado" in a.texto for a in avisos) == 2


def test_cambio_de_fecha_dice_fecha(api, db):
    id = _evento(db)
    _inscribir(api, id, CARMEN)
    evento = db.get(Evento, id)
    nueva = evento.fecha_inicio + timedelta(days=1)
    api.patch(f"/api/v1/eventos/{id}", json={"fecha_inicio": nueva.isoformat(), "fecha_fin": None}, headers=TOKEN)
    [aviso] = _avisos(db, "cambio_evento", id)
    assert f"cambia de fecha: ahora el {fecha_corta(nueva)}" in aviso.texto


def test_editar_evento_permisos(api, db):
    _error(api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"titulo": "Otro titulo"}), 401, "no_autenticado")
    for vecino in (JOSE, PACO):
        _error(
            api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"titulo": "Otro titulo"}, headers=_bearer(vecino)),
            403, "prohibido",
        )
    for quien in (ANTONIO, LUCIA):
        r = api.patch(f"/api/v1/eventos/{RUTA_SOLIDARIA}", json={"titulo": f"Ruta de {quien[-1]}"}, headers=_bearer(quien))
        assert r.status_code == 200, r.text


def test_mas_plazas_suben_la_lista_de_espera(api, db):
    id = _evento(db, plazas=1)
    _inscribir(api, id, CARMEN)
    _inscribir(api, id, JOSE)
    r = api.patch(f"/api/v1/eventos/{id}", json={"plazas_totales": 2}, headers=_bearer(ANTONIO))
    assert r.status_code == 200, r.text
    assert r.json()["plazas_libres"] == 0 and r.json()["inscritos"] == 2
    assert [a.usuario_id for a in _avisos(db, "confirmacion", id)] == [JOSE]
