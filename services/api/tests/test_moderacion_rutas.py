"""Bandeja y decisiones del moderador (H2.5): GET /moderacion/pendientes y POST /moderacion/{id}/decision.

Los tests crean sus propios publicadores, moderador y eventos (importar + confirmar): no dependen de lo
que traiga el seed, que solo pone los municipios y la agenda base.
"""

import json
from pathlib import Path

import pytest
from jsonschema import Draft202012Validator
from referencing import Registry, Resource
from ruamel.yaml import YAML
from sqlalchemy import select

from app.config import get_settings
from app.modelos import Evento, Notificacion, Publicador, Usuario
from app.seed import sembrar
from tests.test_importar import TOKEN, URL, VIERNES, _cuerpo, _error

CONTRATOS = Path(__file__).resolve().parents[3] / "contracts"
PENDIENTES = "/api/v1/moderacion/pendientes"
INEXISTENTE = "00000000-0000-4000-8000-000000000000"
TEL_NIVEL0 = "+34600000771"
TEL_NIVEL2 = "+34600000772"
TEL_MODERADOR = "+34600000779"
TEL_RESPONSABLE = "+34600000773"


def _validador(ref: str) -> Draft202012Validator:
    """Un schema de openapi.yaml (`urn:openapi#/components/schemas/X`) o de ./schemas, con sus $ref resueltos."""
    openapi = YAML(typ="safe").load((CONTRATOS / "openapi.yaml").read_text(encoding="utf-8"))
    componentes = json.loads(json.dumps(openapi["components"]["schemas"]))
    recursos = [
        (f"./schemas/{f.name}", Resource.from_contents(json.loads(f.read_text(encoding="utf-8"))))
        for f in (CONTRATOS / "schemas").glob("*.json")
    ]
    raiz = {"$schema": "https://json-schema.org/draft/2020-12/schema", "components": {"schemas": componentes}}
    recursos.append(("urn:openapi", Resource.from_contents(raiz)))
    esquema = {"$schema": "https://json-schema.org/draft/2020-12/schema", "$ref": ref}
    return Draft202012Validator(
        esquema, registry=Registry().with_resources(recursos), format_checker=Draft202012Validator.FORMAT_CHECKER
    )


PAGINA_PENDIENTES = _validador("urn:openapi#/components/schemas/PaginaPendientes")
EVENTO = _validador("./schemas/evento.json")


def _valida(validador: Draft202012Validator, dato: dict) -> None:
    errores = [f"{'/'.join(map(str, e.absolute_path))}: {e.message}" for e in validador.iter_errors(dato)]
    assert not errores, "\n".join(errores)


def test_resolutor_de_refs_funciona():
    assert list(PAGINA_PENDIENTES.iter_errors({"items": [{"tipo": "evento", "motivo": "x", "evento": {}}],
                                               "total": 1, "page": 1, "size": 20}))


@pytest.fixture
def api(cliente, db, monkeypatch):
    # Bot caído (sin BOT_URL): antispam por reglas y los avisos quedan en cola sin hacer fallar nada.
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    sembrar(db, ahora=VIERNES)
    db.add(Usuario(nombre="Mod de prueba", rol="moderador", telefono=TEL_MODERADOR))
    db.commit()
    yield cliente
    get_settings.cache_clear()


def _publicador(db, telefono: str, nivel: int, con_usuario: bool = False) -> Publicador:
    usuario = None
    if con_usuario:
        usuario = Usuario(nombre="Responsable", rol="publicador", telefono=TEL_RESPONSABLE)
        db.add(usuario)
        db.flush()
    p = Publicador(nombre=f"Peña {telefono[-3:]}", tipo="asociacion", municipio="Velefique", telefono=telefono,
                   estado="aprobado", nivel_confianza=nivel, usuario_id=usuario.id if usuario else None)
    db.add(p)
    db.commit()
    return p


def _evento_confirmado(api, telefono: str, n: int = 1, titulo: str | None = None, descripcion: str | None = None) -> dict:
    """Importa la Ruta Solidaria (con otra URL y título) y la confirma. Devuelve el evento resultante."""
    cuerpo = _cuerpo(url=f"https://example.org/posts/moderacion-{telefono}-{n}", telefono_publicador=telefono)
    campos = cuerpo["extraccion"]["campos"]
    campos["titulo"] = {"valor": titulo or f"Ruta de prueba número {n}", "confianza": "alta"}
    if descripcion is not None:
        campos["descripcion"] = {"valor": descripcion, "confianza": "alta"}
    r = api.post(URL, json=cuerpo, headers=TOKEN)
    assert r.status_code == 201, r.text
    id = r.json()["evento"]["id"]
    r = api.post(f"/api/v1/eventos/{id}/confirmar", json={"campos": {"lugar": "Plaza", "plazas_totales": 30}},
                 headers=TOKEN)
    assert r.status_code == 200, r.text
    return r.json()["evento"]


def _decidir(api, id: str, decision: str, motivo: str | None = None, headers=TOKEN):
    return api.post(f"/api/v1/moderacion/{id}/decision", json={"decision": decision, "motivo": motivo}, headers=headers)


def _bandeja(api) -> list[dict]:
    r = api.get(PENDIENTES, params={"size": 100}, headers=TOKEN)
    assert r.status_code == 200, r.text
    _valida(PAGINA_PENDIENTES, r.json())
    return r.json()["items"]


def _publicados(api) -> set[str]:
    return {e["id"] for e in api.get("/api/v1/eventos", params={"size": 100}).json()["items"]}


def _avisos(db, telefono: str) -> list[Notificacion]:
    db.expire_all()
    return list(db.scalars(select(Notificacion).where(Notificacion.telefono == telefono)).all())


# --- Seguridad ----------------------------------------------------------------------------------


def test_sin_token_401(api):
    _error(api.get(PENDIENTES), 401, "no_autenticado")
    _error(api.get(PENDIENTES, headers={"X-Internal-Token": "malo"}), 401, "no_autenticado")
    _error(_decidir(api, INEXISTENTE, "aprobar", headers={}), 401, "no_autenticado")


# --- Bandeja ------------------------------------------------------------------------------------


def test_bandeja_muestra_evento_en_revision_con_motivo(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    assert evento["estado"] == "en_revision"

    item = next(i for i in _bandeja(api) if i["tipo"] == "evento" and i["evento"]["id"] == evento["id"])
    assert item["motivo"] == "Publicación a mano: la revisa el moderador"
    assert item["score_spam"] == 0.0
    assert "publicador" not in item


def test_spam_se_queda_parado_con_su_motivo(api, db):
    _publicador(db, TEL_NIVEL2, nivel=2)
    evento = _evento_confirmado(
        api, TEL_NIVEL2, titulo="GANA DINERO FACIL con CRIPTO",
        descripcion="Casino y apuestas!!! haz clic en bit.ly/xxx y https://otro.xyz/a",
    )
    assert evento["estado"] == "en_revision"
    item = next(i for i in _bandeja(api) if i["tipo"] == "evento" and i["evento"]["id"] == evento["id"])
    assert item["motivo"].startswith("Posible spam")
    assert item["score_spam"] >= get_settings().moderacion_umbral_spam
    assert evento["id"] not in _publicados(api)


def test_bandeja_muestra_publicadores_por_aprobar_por_antiguedad(api, db):
    r = api.post("/api/v1/publicadores", headers=TOKEN, json={
        "nombre": "Club de Lectura Senés", "tipo": "asociacion", "municipio": "Senés", "telefono": "+34600000774"})
    assert r.status_code == 201, r.text
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)

    items = _bandeja(api)
    posiciones = {
        (i["tipo"], (i.get("evento") or i.get("publicador"))["id"]): n for n, i in enumerate(items)
    }
    pub = next(i for i in items if i["tipo"] == "publicador" and i["publicador"]["id"] == r.json()["id"])
    assert pub["motivo"] and pub["score_spam"] is None and "evento" not in pub
    # El publicador se pidió antes que el evento: sale antes.
    assert posiciones[("publicador", r.json()["id"])] < posiciones[("evento", evento["id"])]


def test_bandeja_paginada(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0)
    for n in range(3):
        _evento_confirmado(api, TEL_NIVEL0, n=n)
    r = api.get(PENDIENTES, params={"size": 2, "page": 1}, headers=TOKEN)
    pagina = r.json()
    _valida(PAGINA_PENDIENTES, pagina)
    assert pagina["size"] == 2 and pagina["page"] == 1 and len(pagina["items"]) == 2 and pagina["total"] >= 3


# --- Decisiones ---------------------------------------------------------------------------------


def test_aprobar_publica_y_avisa_al_publicador(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0, con_usuario=True)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    # Al quedar en revisión se avisa a los moderadores (con el bot caído queda en cola).
    avisos_mod = [n for n in _avisos(db, TEL_MODERADOR) if n.evento_id == evento["id"]]
    assert len(avisos_mod) == 1 and avisos_mod[0].tipo == "moderacion"
    assert "Publicación a mano" in avisos_mod[0].texto and avisos_mod[0].estado_envio == "pendiente"

    r = _decidir(api, evento["id"], "aprobar")
    assert r.status_code == 200, r.text
    _valida(EVENTO, r.json())
    assert r.json()["estado"] == "publicado"
    assert r.json()["moderacion"]["revisado_por"]
    assert evento["id"] in _publicados(api)
    assert evento["id"] not in {i.get("evento", {}).get("id") for i in _bandeja(api)}

    # El aviso va al usuario responsable del publicador (por usuario_id).
    avisos = _avisos(db, TEL_RESPONSABLE)
    assert len(avisos) == 1 and avisos[0].evento_id == evento["id"] and "publicado" in avisos[0].texto
    assert avisos[0].usuario_id is not None


def test_aprobaciones_no_lo_pasan_a_automatica(api, db):
    # Solo hay dos modos: por muchas aprobaciones, una asociación «a mano» sigue a mano.
    p = _publicador(db, TEL_NIVEL0, nivel=0)
    n = get_settings().moderacion_aprobaciones_subir_nivel
    for i in range(n):
        evento = _evento_confirmado(api, TEL_NIVEL0, n=i)
        assert _decidir(api, evento["id"], "aprobar").status_code == 200
    db.expire_all()
    assert db.get(Publicador, p.id).nivel_confianza == 0
    assert db.get(Publicador, p.id).aprobaciones == n
    assert all("nivel" not in a.texto for a in _avisos(db, TEL_NIVEL0))
    assert _evento_confirmado(api, TEL_NIVEL0, n=99, titulo="Carrera popular de otoño")["estado"] == "en_revision"


def test_rechazar_no_sale_en_la_agenda(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    r = _decidir(api, evento["id"], "rechazar", "Es una actividad privada")
    assert r.status_code == 200, r.text
    _valida(EVENTO, r.json())
    assert r.json()["estado"] == "rechazado"
    assert r.json()["moderacion"]["motivo"] == "Es una actividad privada"
    assert evento["id"] not in _publicados(api)
    assert "Es una actividad privada" in _avisos(db, TEL_NIVEL0)[-1].texto


def test_restaurar_un_rechazado_lo_devuelve_a_la_bandeja(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    assert _decidir(api, evento["id"], "rechazar", "Por error").status_code == 200
    avisos_antes = len(_avisos(db, TEL_NIVEL0))

    r = _decidir(api, evento["id"], "restaurar")
    assert r.status_code == 200, r.text
    _valida(EVENTO, r.json())
    assert r.json()["estado"] == "en_revision"
    assert r.json()["moderacion"]["motivo"] == "Restaurado por moderación: pendiente de revisar de nuevo"
    assert len(_avisos(db, TEL_NIVEL0)) == avisos_antes
    assert _decidir(api, evento["id"], "aprobar").status_code == 200
    assert evento["id"] in _publicados(api)


def test_restaurar_solo_desde_rechazado(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    _error(_decidir(api, evento["id"], "restaurar"), 409, "estado_invalido")
    assert _decidir(api, evento["id"], "aprobar").status_code == 200
    _error(_decidir(api, evento["id"], "restaurar"), 409, "estado_invalido")


def test_retirar_un_publicado_lo_quita_de_la_agenda(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    assert _decidir(api, evento["id"], "aprobar").status_code == 200
    assert evento["id"] in _publicados(api)

    r = _decidir(api, evento["id"], "retirar", "Información falsa")
    assert r.status_code == 200, r.text
    _valida(EVENTO, r.json())
    assert r.json()["estado"] == "archivado"
    assert r.json()["moderacion"]["motivo"] == "Información falsa"
    assert evento["id"] not in _publicados(api)
    assert api.get(f"/api/v1/eventos/{evento['id']}").status_code == 404


def test_retirar_sin_motivo_usa_el_de_por_defecto(api, db):
    # En el contrato Decision.motivo es opcional.
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    assert _decidir(api, evento["id"], "aprobar").status_code == 200
    r = _decidir(api, evento["id"], "retirar")
    assert r.status_code == 200, r.text
    assert r.json()["estado"] == "archivado"
    assert r.json()["moderacion"]["motivo"] == "Retirado por moderación"
    assert "se ha retirado" in _avisos(db, TEL_NIVEL0)[-1].texto


def test_decision_en_estado_incorrecto_409(api, db):
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    _error(_decidir(api, evento["id"], "retirar", "no procede"), 409, "estado_invalido")
    assert _decidir(api, evento["id"], "aprobar").status_code == 200
    _error(_decidir(api, evento["id"], "aprobar"), 409, "estado_invalido")
    _error(_decidir(api, evento["id"], "rechazar"), 409, "estado_invalido")
    # Uno que aún espera la confirmación del publicador tampoco se decide aquí.
    r = api.post(URL, json=_cuerpo(url="https://example.org/otro", telefono_publicador=TEL_NIVEL0), headers=TOKEN)
    _error(_decidir(api, r.json()["evento"]["id"], "aprobar"), 409, "estado_invalido")


def test_decision_404_y_422(api):
    _error(_decidir(api, INEXISTENTE, "aprobar"), 404, "evento_no_encontrado")
    _error(_decidir(api, "no-es-uuid", "aprobar"), 404, "evento_no_encontrado")
    _error(_decidir(api, INEXISTENTE, "borrar"), 422, "validacion")


def test_decision_no_falla_con_bot_caido(api, db, monkeypatch):
    monkeypatch.setenv("BOT_URL", "http://127.0.0.1:9")
    get_settings.cache_clear()
    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    assert _decidir(api, evento["id"], "aprobar").status_code == 200
    db.expire_all()
    assert db.scalar(select(Evento.estado).where(Evento.id == evento["id"])) == "publicado"
    assert all(n.estado_envio == "pendiente" for n in _avisos(db, TEL_NIVEL0))


def test_decision_concurrente_solo_una_gana(api, db, motor):
    """Dos moderadores aprueban a la vez: el segundo tenía el evento cargado aún `en_revision`, pero el UPDATE
    condicionado no cambia nada, recibe 409 y no suma otra aprobación ni deja otro aviso."""
    from fastapi import BackgroundTasks
    from sqlalchemy.orm import Session

    from app.errores import ErrorApi
    from app.rutas.moderacion import Decision, decidir

    p = _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    with Session(bind=motor, expire_on_commit=False) as segundo:
        assert segundo.get(Evento, evento["id"]).estado == "en_revision"  # lo carga antes que gane el primero
        assert _decidir(api, evento["id"], "aprobar").status_code == 200
        with pytest.raises(ErrorApi) as error:
            decidir(evento["id"], Decision(decision="aprobar"), BackgroundTasks(), "otro moderador", segundo)
        assert error.value.status == 409 and error.value.code == "estado_invalido"
    db.expire_all()
    assert db.get(Publicador, p.id).aprobaciones == 1
    assert len([n for n in _avisos(db, TEL_NIVEL0) if n.evento_id == evento["id"]]) == 1


def test_aviso_sale_tras_el_commit_en_segundo_plano(api, db, motor, monkeypatch):
    """El aviso se crea `pendiente` en la transacción y lo envía una BackgroundTask cuando la decisión ya está
    guardada (el TestClient ejecuta las tareas al terminar la respuesta)."""
    import httpx
    from sqlalchemy.orm import Session

    from app import notificaciones

    _publicador(db, TEL_NIVEL0, nivel=0)
    evento = _evento_confirmado(api, TEL_NIVEL0)
    vistos = []

    def bot(peticion: httpx.Request) -> httpx.Response:
        with Session(bind=motor) as otra:  # lo que ve otra conexión: ya está confirmado
            vistos.append(otra.scalar(select(Evento.estado).where(Evento.id == evento["id"])))
        return httpx.Response(200, json={"enviado": True})

    monkeypatch.setenv("BOT_URL", "http://bot-falso:8001")
    get_settings.cache_clear()
    monkeypatch.setattr(notificaciones, "_transporte", httpx.MockTransport(bot))
    assert _decidir(api, evento["id"], "aprobar").status_code == 200
    assert vistos and set(vistos) == {"publicado"}  # el del publicador y los de A10 a interesados
    avisos = [n for n in _avisos(db, TEL_NIVEL0) if n.evento_id == evento["id"]]
    assert len(avisos) == 1 and avisos[0].estado_envio == "enviada" and avisos[0].intentos == 1
