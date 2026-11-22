"""P3a (apelaciones) y P4a (edad), lo que piden los profesores."""

from sqlalchemy import select

from app.modelos import Notificacion, Usuario
from app.seguridad import emitir_jwt
from tests.test_importar import TOKEN
from tests.test_moderacion_rutas import (  # noqa: F401  (fixture api)
    TEL_NIVEL0,
    TEL_RESPONSABLE,
    _decidir,
    _evento_confirmado,
    _publicador,
    _validador,
    api,
)

EVENTO = _validador("./schemas/evento.json")
USUARIO = _validador("./schemas/usuario.json")
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
MOTIVO = "Es una ruta benéfica de la asociación, no es publicidad"


def _bearer(usuario_id: str, rol: str) -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, rol)}"}


def _apelar(api, id: str, headers, motivo: str = MOTIVO, **extra):
    return api.post(f"/api/v1/eventos/{id}/apelacion", json={"motivo": motivo, **extra}, headers=headers)


def _rechazado(api, db):
    """Un plan de una asociación con responsable (usuario), rechazado por el moderador."""
    p = _publicador(db, TEL_NIVEL0, nivel=0, con_usuario=True)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    assert evento["estado"] == "en_revision"
    assert _decidir(api, evento["id"], "rechazar", "Parece publicidad").status_code == 200
    responsable = db.scalar(select(Usuario).where(Usuario.telefono == TEL_RESPONSABLE))
    return evento, p, _bearer(responsable.id, "publicador"), responsable


# --- P3a · apelaciones ---------------------------------------------------------------------------


def test_el_organizador_apela_y_vuelve_a_la_bandeja(api, db):
    evento, _, responsable, _ = _rechazado(api, db)
    r = _apelar(api, evento["id"], responsable)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert not list(EVENTO.iter_errors(datos))
    assert datos["estado"] == "en_revision"
    assert datos["moderacion"]["motivo"] == f"Apelación: {MOTIVO}"
    assert datos["apelacion"]["motivo"] == MOTIVO and datos["apelacion"]["creada_en"]
    pendientes = api.get("/api/v1/moderacion/pendientes", headers=TOKEN).json()["items"]
    assert any(p["evento"]["id"] == evento["id"] and p["motivo"].startswith("Apelación:") for p in pendientes)
    # Aviso a los moderadores
    assert db.scalar(select(Notificacion).where(Notificacion.evento_id == evento["id"],
                                                Notificacion.texto.like("Apelación de%")))


def test_solo_una_vez_y_el_segundo_rechazo_es_definitivo(api, db):
    evento, _, responsable, _ = _rechazado(api, db)
    assert _apelar(api, evento["id"], responsable).status_code == 200
    assert _decidir(api, evento["id"], "rechazar", "Sigue siendo publicidad").status_code == 200
    r = _apelar(api, evento["id"], responsable)
    assert r.status_code == 409 and r.json()["error"]["code"] == "apelacion_usada"


def test_aprobar_tras_la_apelacion_publica(api, db):
    evento, _, responsable, _ = _rechazado(api, db)
    _apelar(api, evento["id"], responsable)
    r = _decidir(api, evento["id"], "aprobar")
    assert r.status_code == 200 and r.json()["estado"] == "publicado"
    assert r.json()["apelacion"]["motivo"] == MOTIVO


def test_no_se_apela_lo_que_no_esta_rechazado(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0, con_usuario=True)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    responsable = db.scalar(select(Usuario).where(Usuario.telefono == TEL_RESPONSABLE))
    r = _apelar(api, evento["id"], _bearer(responsable.id, "publicador"))
    assert r.status_code == 409 and r.json()["error"]["code"] == "estado_invalido"


def test_solo_quien_lo_propuso(api, db):
    evento, *_ = _rechazado(api, db)
    r = _apelar(api, evento["id"], _bearer(CARMEN, "vecino"))
    assert r.status_code == 403 and r.json()["error"]["code"] == "prohibido"
    assert _apelar(api, evento["id"], {}).status_code == 401


def test_el_bot_apela_en_nombre_del_organizador(api, db):
    evento, _, _, responsable = _rechazado(api, db)
    assert _apelar(api, evento["id"], TOKEN).status_code == 422  # sin usuario_id
    assert _apelar(api, evento["id"], TOKEN, usuario_id=CARMEN).status_code == 403
    r = _apelar(api, evento["id"], TOKEN, usuario_id=responsable.id)
    assert r.status_code == 200 and r.json()["estado"] == "en_revision"


def test_motivo_de_10_a_500_caracteres(api, db):
    evento, _, responsable, _ = _rechazado(api, db)
    assert _apelar(api, evento["id"], responsable, motivo="corto").status_code == 422
    assert _apelar(api, evento["id"], responsable, motivo="x" * 501).status_code == 422


def test_el_aviso_de_rechazo_lleva_el_evento(api, db):
    """Para que el bot ponga [Apelar] (P3b)."""
    evento, p, _, responsable = _rechazado(api, db)
    aviso = db.scalars(select(Notificacion).where(Notificacion.usuario_id == responsable.id)).all()[-1]
    assert aviso.evento_id == evento["id"] and "Parece publicidad" in aviso.texto


def test_un_vecino_sin_asociacion_tambien_apela(api, db):
    vecina = Usuario(nombre="Rosa", rol="vecino", telefono="+34600000555", municipio="Senés")
    db.add(vecina)
    db.commit()
    r = api.post("/api/v1/eventos", headers=_bearer(vecina.id, "vecino"), json={
        "titulo": "Merienda en la plaza", "categoria": "gastronomia", "municipio": "Senés",
        "fecha_inicio": "2026-12-14T17:00:00+01:00"})
    assert r.status_code == 201, r.text
    evento = r.json()
    assert evento["estado"] == "en_revision"
    assert _decidir(api, evento["id"], "rechazar", "Falta el lugar").status_code == 200
    aviso = db.scalars(select(Notificacion).where(Notificacion.usuario_id == vecina.id)).all()[-1]
    assert aviso.evento_id == evento["id"]  # también se entera del rechazo
    r = _apelar(api, evento["id"], _bearer(vecina.id, "vecino"), motivo="Es en la plaza de la iglesia, a las 5")
    assert r.status_code == 200 and r.json()["estado"] == "en_revision"


# --- P4a · edad ----------------------------------------------------------------------------------


def test_alta_con_edad(api):
    r = api.post("/api/v1/usuarios", json={"telefono": "+34600000601", "nombre": "Ana", "edad": 72}, headers=TOKEN)
    assert r.status_code == 201, r.text
    assert r.json()["edad"] == 72 and not list(USUARIO.iter_errors(r.json()))


def test_menos_de_14_edad_minima(api):
    r = api.post("/api/v1/usuarios", json={"telefono": "+34600000602", "edad": 13}, headers=TOKEN)
    assert r.status_code == 422 and r.json()["error"]["code"] == "edad_minima"
    r = api.post("/api/v1/usuarios", json={"telefono": "+34600000603", "edad": 121}, headers=TOKEN)
    assert r.status_code == 422 and r.json()["error"]["code"] == "validacion"
    r = api.post("/api/v1/usuarios", json={"telefono": "+34600000604", "edad": 14}, headers=TOKEN)
    assert r.status_code == 201 and r.json()["edad"] == 14


def test_sin_edad_queda_en_null(api):
    r = api.post("/api/v1/usuarios", json={"telefono": "+34600000605"}, headers=TOKEN)
    assert r.status_code == 201 and r.json()["edad"] is None


def test_editar_la_edad_en_el_perfil(api):
    yo = _bearer(CARMEN, "vecino")
    r = api.patch("/api/v1/usuarios/me", json={"edad": 68}, headers=yo)
    assert r.status_code == 200 and r.json()["edad"] == 68
    r = api.patch("/api/v1/usuarios/me", json={"edad": 10}, headers=yo)
    assert r.status_code == 422 and r.json()["error"]["code"] == "edad_minima"
    assert api.patch("/api/v1/usuarios/me", json={"edad": None}, headers=yo).json()["edad"] is None


def test_vincular_crea_el_usuario_con_edad(api):
    r = api.post("/api/v1/usuarios/vincular", headers=TOKEN, json={
        "telefono": "+34600000606", "contacto": "tg:4242", "nombre": "Pepe", "edad": 80})
    assert r.status_code in (200, 201), r.text
    assert r.json()["edad"] == 80
    r = api.post("/api/v1/usuarios/vincular", headers=TOKEN, json={
        "telefono": "+34600000607", "contacto": "tg:4243", "edad": 9})
    assert r.status_code == 422 and r.json()["error"]["code"] == "edad_minima"


def test_alta_de_asociacion_con_la_edad_del_responsable(api):
    cuerpo = {"nombre": "Club de Petanca", "tipo": "asociacion", "municipio": "Tahal", "telefono": "+34600000608",
              "responsable": {"nombre": "Luis Gil", "dni": "12345678Z", "residencia": "Tahal", "edad": 13}}
    r = api.post("/api/v1/publicadores", json=cuerpo, headers=TOKEN)
    assert r.status_code == 422 and r.json()["error"]["code"] == "edad_minima"
    assert r.json()["error"]["details"]["campo"] == "responsable.edad"
    cuerpo["responsable"]["edad"] = 55
    r = api.post("/api/v1/publicadores", json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    ficha = api.get(f"/api/v1/publicadores/{r.json()['id']}", headers=_bearer(
        "5a5e0000-0000-4000-8000-000000000002", "moderador")).json()
    assert ficha["responsable"]["edad"] == 55
