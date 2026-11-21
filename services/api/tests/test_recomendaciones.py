"""Recomendador (H3.6): reglas con motivo legible (app/recomendador.py) y GET /recomendaciones."""

import json
import uuid
from datetime import datetime, timedelta, timezone

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from ruamel.yaml import YAML

from app.modelos import Evento, Inscripcion, Usuario
from app.recomendador import Razon, componer_motivo, normalizar, recomendar
from app.rutas import recomendaciones
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_importar import CONTRATOS, TOKEN, VIERNES, _error

URL = "/api/v1/recomendaciones"
RUTA = "1e5d0000-0000-4000-8000-000000000001"
VISITA_HORNOS = "1e5d0000-0000-4000-8000-000000000002"
TALLER_ESPARTO = "1e5d0000-0000-4000-8000-000000000004"
GRAFITI_EN_REVISION = "1e5d0000-0000-4000-8000-000000000009"
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
LUCIA_MODERADORA = "5a5e0000-0000-4000-8000-000000000002"
ANTONIO_PUBLICADOR = "5a5e0000-0000-4000-8000-000000000003"
JOSE = "5a5e0000-0000-4000-8000-000000000005"


def _validador_respuesta() -> Draft202012Validator:
    """Schema 200 de GET /recomendaciones en openapi.yaml, con sus $ref resueltos."""
    openapi = YAML(typ="safe").load((CONTRATOS / "openapi.yaml").read_text(encoding="utf-8"))
    openapi = json.loads(json.dumps(openapi))
    recursos = [
        (f"./schemas/{f.name}", Resource.from_contents(json.loads(f.read_text(encoding="utf-8"))))
        for f in (CONTRATOS / "schemas").glob("*.json")
    ]
    raiz = {"$schema": "https://json-schema.org/draft/2020-12/schema", **openapi}
    recursos.append(("urn:openapi", Resource.from_contents(raiz)))
    puntero = "urn:openapi#/paths/~1api~1v1~1recomendaciones/get/responses/200/content/application~1json/schema"
    esquema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": puntero}
    registro = Registry().with_resources(recursos)
    return Draft202012Validator(esquema, registry=registro, format_checker=Draft202012Validator.FORMAT_CHECKER)


RESPUESTA = _validador_respuesta()


def _valida(dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in RESPUESTA.iter_errors(dato)]
    assert not errores, "\n".join(errores)


def _bearer(usuario_id: str, rol: str = "vecino") -> dict:
    return {"Authorization": f"Bearer {emitir_jwt(usuario_id, rol)}"}


@pytest.fixture
def api(cliente, db, monkeypatch):
    monkeypatch.setattr(recomendaciones, "reloj", lambda: VIERNES)
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


def test_resolutor_de_refs_funciona():
    assert list(RESPUESTA.iter_errors({"items": [{"evento": {}, "puntuacion": 1, "motivo": "x"}]}))


# --- lógica --------------------------------------------------------------------------------------


def test_normalizar_etiquetas():
    assert normalizar("Visita_guiada") == normalizar("visita guiada") == "visita guiada"
    assert normalizar("Artesanía") == "artesania"


def test_componer_motivo_ordena_y_limita():
    razones = [
        Razon("fecha", 1.0, "es dentro de 9 días"),
        Razon("plazas", 1.5, "quedan las últimas 8 plazas"),
        Razon("gustos", 7.0, "te gusta el senderismo"),
        Razon("distancia", 1.6, "es en Velefique (a 5 km)"),
        Razon("historial", 0.5, None),
    ]
    assert componer_motivo(razones) == "Te gusta el senderismo, es en Velefique (a 5 km) y quedan las últimas 8 plazas"
    assert componer_motivo([]) == "Es un plan en la comarca que aún no has visto"
    assert componer_motivo([Razon("fecha", 1.0, "es mañana")]) == "Es mañana"


def test_completo_se_dice_siempre():
    razones = [
        Razon("gustos", 3.0, "te gusta la cultura"),
        Razon("distancia", 2.0, "es en tu pueblo (Senés)"),
        Razon("fecha", 1.0, "es mañana"),
        Razon("plazas", -3.0, "está completo, pero puedes apuntarte a la lista de espera"),
    ]
    motivo = componer_motivo(razones)
    assert motivo.endswith("y está completo, pero puedes apuntarte a la lista de espera")
    assert "es mañana" not in motivo  # máximo 3 razones


def test_carmen_ruta_solidaria_primera_con_motivo(db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    lista = recomendar(db, db.get(Usuario, CARMEN), VIERNES, limite=5)
    primera = lista[0]
    assert primera.evento.id == RUTA
    assert primera.motivo.startswith("Te gusta el senderismo")
    assert "Velefique (a 5 km)" in primera.motivo
    # N6: 39 plazas libres reales (40 − 1 confirmada), no las 8 inventadas del fixture: ya no son «las últimas»
    assert "plazas" not in primera.motivo and primera.evento.plazas_libres == 39
    assert primera.distancia_km == pytest.approx(4.9, abs=0.3)
    assert primera.puntuacion > lista[1].puntuacion
    assert [r.puntuacion for r in lista] == sorted((r.puntuacion for r in lista), reverse=True)


def test_excluye_inscritos_pasados_no_publicados_y_propios(db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    # José está confirmado en la Ruta (seed): no se le recomienda otra vez.
    assert RUTA not in {r.evento.id for r in recomendar(db, db.get(Usuario, JOSE), VIERNES, limite=20)}
    # Carmen está libre en el seed (paso 4 del guion); una vez apuntada, deja de recomendársele.
    db.add(Inscripcion(evento_id=RUTA, usuario_id=CARMEN, estado="confirmada"))
    db.commit()
    ids = {r.evento.id for r in recomendar(db, db.get(Usuario, CARMEN), VIERNES, limite=20)}
    assert RUTA not in ids
    assert GRAFITI_EN_REVISION not in ids
    eventos = {e.id: e for e in db.query(Evento).all()}
    assert all(eventos[i].estado == "publicado" and eventos[i].fecha_inicio >= VIERNES for i in ids)
    # Antonio publica la Ruta (Amigos de Velefique): no se recomienda su propio evento.
    ids_antonio = {r.evento.id for r in recomendar(db, db.get(Usuario, ANTONIO_PUBLICADOR), VIERNES, limite=20)}
    assert RUTA not in ids_antonio


def test_cancelada_vuelve_a_recomendarse(db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    inscripcion = Inscripcion(evento_id=RUTA, usuario_id=CARMEN, estado="confirmada")
    db.add(inscripcion)
    db.commit()
    assert RUTA not in {r.evento.id for r in recomendar(db, db.get(Usuario, CARMEN), VIERNES, limite=20)}
    inscripcion.estado = "cancelada"
    db.commit()
    assert recomendar(db, db.get(Usuario, CARMEN), VIERNES, limite=1)[0].evento.id == RUTA


def test_completo_penaliza_y_avisa_lista_de_espera(db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    carmen = db.get(Usuario, CARMEN)
    antes = {r.evento.id: r for r in recomendar(db, carmen, VIERNES, limite=20)}
    db.get(Evento, TALLER_ESPARTO).plazas_libres = 0
    db.commit()
    despues = {r.evento.id: r for r in recomendar(db, carmen, VIERNES, limite=20)}
    assert despues[TALLER_ESPARTO].puntuacion < antes[TALLER_ESPARTO].puntuacion
    assert "lista de espera" in despues[TALLER_ESPARTO].motivo


def test_historial_suma(db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    carmen = db.get(Usuario, CARMEN)
    antes = {r.evento.id: r.puntuacion for r in recomendar(db, carmen, VIERNES, limite=20)}
    # Carmen fue a la visita guiada de Lucainena (cultural): los demás planes culturales le suben.
    db.add(Inscripcion(evento_id=VISITA_HORNOS, usuario_id=CARMEN, estado="asistio"))
    db.commit()
    culturales = [r for r in recomendar(db, carmen, VIERNES, limite=20) if r.evento.categoria == "cultural"]
    assert culturales
    assert VISITA_HORNOS not in {r.evento.id for r in culturales}
    for r in culturales:
        assert r.puntuacion == pytest.approx(antes[r.evento.id] + 1.0)


def test_mas_cerca_y_mas_pronto_puntua_mas(db):
    sembrar(db, ahora=VIERNES)
    db.commit()
    # Usuario sin gustos en Senés: dos eventos iguales salvo distancia y fecha.
    usuario = Usuario(id=str(uuid.uuid4()), nombre="Prueba", municipio="Senés", lat=37.1983, lon=-2.3447)
    db.add(usuario)
    base = dict(categoria="ludica", etiquetas=[], estado="publicado", es_gratuito=True)
    cerca = Evento(titulo="Cerca y pronto", municipio="Senés", lat=37.1983, lon=-2.3447,
                   fecha_inicio=VIERNES + timedelta(days=1), **base)
    lejos = Evento(titulo="Lejos y tarde", municipio="Lucainena de las Torres", lat=37.0406, lon=-2.2017,
                   fecha_inicio=VIERNES + timedelta(days=25), **base)
    db.add_all([cerca, lejos])
    db.commit()
    puntos = {r.evento.titulo: r for r in recomendar(db, usuario, VIERNES, limite=50)}
    assert puntos["Cerca y pronto"].puntuacion > puntos["Lejos y tarde"].puntuacion
    assert puntos["Cerca y pronto"].motivo == "Es en tu pueblo (Senés) y es mañana"


def test_usuario_sin_ubicacion_ni_gustos(db):
    sembrar(db, ahora=VIERNES)
    usuario = Usuario(id=str(uuid.uuid4()), nombre="Sin datos")
    db.add(usuario)
    db.commit()
    lista = recomendar(db, usuario, VIERNES, limite=5)
    assert lista and all(r.distancia_km is None and r.motivo for r in lista)


# --- GET /recomendaciones ------------------------------------------------------------------------


def test_ruta_carmen_por_api_con_token_interno(api, db):
    r = api.get(URL, params={"usuario_id": CARMEN}, headers=TOKEN)
    assert r.status_code == 200, r.text
    cuerpo = r.json()
    _valida(cuerpo)
    assert len(cuerpo["items"]) == 5  # límite por defecto
    primera = cuerpo["items"][0]
    assert primera["evento"]["id"] == RUTA
    assert primera["motivo"] == "Te gusta el senderismo, es en Velefique (a 5 km) y es dentro de 9 días"
    assert primera["distancia_km"] == pytest.approx(4.9, abs=0.3)


def test_limite(api):
    r = api.get(URL, params={"usuario_id": JOSE, "limite": 2}, headers=TOKEN)
    assert r.status_code == 200
    assert len(r.json()["items"]) == 2
    _error(api.get(URL, params={"usuario_id": JOSE, "limite": 0}, headers=TOKEN), 422, "validacion")
    _error(api.get(URL, params={"usuario_id": JOSE, "limite": 21}, headers=TOKEN), 422, "validacion")


def test_propio_usuario_con_jwt(api):
    r = api.get(URL, params={"usuario_id": CARMEN}, headers=_bearer(CARMEN))
    assert r.status_code == 200, r.text
    _valida(r.json())


def test_moderador_ve_las_de_otro(api):
    r = api.get(URL, params={"usuario_id": CARMEN}, headers=_bearer(LUCIA_MODERADORA, "moderador"))
    assert r.status_code == 200, r.text


def test_otro_vecino_403(api):
    _error(api.get(URL, params={"usuario_id": CARMEN}, headers=_bearer(JOSE)), 403, "prohibido")


def test_sin_credenciales_401(api):
    _error(api.get(URL, params={"usuario_id": CARMEN}), 401, "no_autenticado")


def test_usuario_inexistente_404(api):
    _error(api.get(URL, params={"usuario_id": str(uuid.uuid4())}, headers=TOKEN), 404, "usuario_no_encontrado")


def test_usuario_id_obligatorio_y_uuid(api):
    _error(api.get(URL, headers=TOKEN), 422, "validacion")
    _error(api.get(URL, params={"usuario_id": "carmen"}, headers=TOKEN), 422, "validacion")
