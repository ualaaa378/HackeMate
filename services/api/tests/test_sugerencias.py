"""N7: GET /admin/sugerencias (participación → bot /ai/sugerir-eventos o reglas) y POST /admin/sugerencias/borrador."""

import json
from datetime import datetime, timezone

import httpx
import pytest

from app import sugerencias
from app.config import get_settings
from app.modelos import Evento, Inscripcion, MensajeEvento, Usuario
from app.rutas import sugerencias as rutas_sugerencias
from app.seed import sembrar
from app.seguridad import emitir_jwt
from tests.test_contrato_n7 import PETICION_BOT, SUGERENCIAS
from tests.test_importar import TOKEN, VIERNES

URL = "/api/v1/admin/sugerencias"
LUCIA_MODERADORA = "5a5e0000-0000-4000-8000-000000000002"
CARMEN = "5a5e0000-0000-4000-8000-000000000001"
MODERADOR = {"Authorization": f"Bearer {emitir_jwt(LUCIA_MODERADORA, 'moderador')}"}


class BotFalso:
    def __init__(self, modo="ok", propuestas=None):
        self.modo, self.propuestas, self.cuerpos = modo, propuestas, []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.cuerpos.append(json.loads(peticion.content))
        if self.modo == "caido":
            raise httpx.ConnectError("conexion rechazada", request=peticion)
        planes = self.cuerpos[-1]["planes"]
        propuestas = self.propuestas if self.propuestas is not None else [{
            "titulo": f"Vuelve {planes[0]['titulo']}",
            "categoria": planes[0]["categoria"],
            "municipio": planes[0]["municipio"],
            "fecha_aproximada": "en primavera",
            "motivo": "Se llenó y hubo lista de espera",
            "basado_en": [planes[0]["evento_id"]],
        }]
        return httpx.Response(200, json={"propuestas": propuestas, "proveedor_ia": "freellm:qwen"})


@pytest.fixture
def bot(monkeypatch):
    monkeypatch.setenv("BOT_URL", "http://bot-falso:8001")
    get_settings.cache_clear()
    b = BotFalso()
    monkeypatch.setattr(sugerencias, "_transporte", httpx.MockTransport(b))
    monkeypatch.setattr(rutas_sugerencias, "reloj", lambda: VIERNES)
    yield b
    get_settings.cache_clear()


@pytest.fixture
def api(cliente, db, bot):
    sembrar(db, ahora=VIERNES)
    db.commit()
    return cliente


def _plan_lleno(db) -> Evento:
    """Un concierto de 2 plazas: 2 inscritas, 1 en lista de espera y 2 preguntas en el chat."""
    evento = Evento(titulo="Concierto de guitarra en Tahal", categoria="cultural", municipio="Tahal", lat=37.22,
                    lon=-2.29, fecha_inicio=datetime(2026, 10, 10, 18, 0, tzinfo=timezone.utc), estado="finalizado",
                    plazas_totales=2, plazas_libres=0)
    db.add(evento)
    db.flush()
    for i, estado in enumerate(("asistio", "asistio", "lista_espera")):
        u = Usuario(nombre=f"Vecina {i}")
        db.add(u)
        db.flush()
        db.add(Inscripcion(evento_id=evento.id, usuario_id=u.id, plazas=1, estado=estado, canal="web"))
    for texto in ("¿Hay sillas?", "¿Se puede ir con niños?"):
        db.add(MensajeEvento(evento_id=evento.id, autor_nombre="Vecina", autor_rol="vecino", texto=texto,
                             tipo="pregunta"))
    db.commit()
    return evento


def test_participacion_cuenta_lista_de_espera_y_preguntas(api, db):
    lleno = _plan_lleno(db)
    plan = next(p for p in sugerencias.participacion(db) if p["evento_id"] == lleno.id)
    assert (plan["inscritos"], plan["lista_espera"], plan["asistencias"], plan["preguntas_chat"]) == (2, 1, 2, 2)
    assert plan["ocupacion"] == 1.0
    assert sugerencias.participacion(db)[0]["evento_id"] == lleno.id  # lleno y con lista de espera: el primero


def test_con_el_bot_devuelve_sus_propuestas(api, db, bot):
    lleno = _plan_lleno(db)
    r = api.get(URL, headers=MODERADOR)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert not list(SUGERENCIAS.iter_errors(datos))
    assert datos["proveedor_ia"] == "freellm:qwen"
    assert datos["items"][0]["titulo"] == "Vuelve Concierto de guitarra en Tahal"
    assert datos["items"][0]["basado_en"] == [lleno.id]
    # Lo que la API manda al bot cumple su contrato (N8)
    assert not list(PETICION_BOT.iter_errors(bot.cuerpos[-1]))


def test_propuestas_del_bot_que_no_cuadran_se_descartan(api, db, bot):
    _plan_lleno(db)
    bot.propuestas = [
        {"titulo": "Concierto en Madrid", "categoria": "cultural", "municipio": "Madrid", "motivo": "x"},
        {"titulo": "Algo", "categoria": "inventada", "municipio": "Tahal", "motivo": "x"},
    ]
    datos = api.get(URL, headers=MODERADOR).json()
    assert datos["proveedor_ia"] == "reglas" and datos["items"]  # nada válido: propone por reglas


def test_sin_bot_propone_por_reglas(api, db, bot):
    lleno = _plan_lleno(db)
    bot.modo = "caido"
    r = api.get(URL, params={"limite": 1}, headers=MODERADOR)
    assert r.status_code == 200, r.text
    datos = r.json()
    assert not list(SUGERENCIAS.iter_errors(datos))
    assert datos["proveedor_ia"] == "reglas" and len(datos["items"]) == 1
    propuesta = datos["items"][0]
    assert propuesta["titulo"] == "Otra edición de «Concierto de guitarra en Tahal»"
    assert propuesta["motivo"] == ("«Concierto de guitarra en Tahal» se llenó (2 de 2), hubo 1 en lista de espera "
                                   "y 2 preguntas en el chat")
    assert propuesta["fecha_aproximada"] == "en octubre de 2027" and propuesta["basado_en"] == [lleno.id]


def test_filtro_por_municipio(api, db):
    _plan_lleno(db)
    datos = api.get(URL, params={"municipio": "Senés"}, headers=MODERADOR).json()
    assert all(p["municipio"] == "Senés" for p in datos["basado_en"])


def test_solo_moderadores(api):
    assert api.get(URL).status_code == 401
    vecina = {"Authorization": f"Bearer {emitir_jwt(CARMEN, 'vecino')}"}
    assert api.get(URL, headers=vecina).status_code == 403
    assert api.get(URL, headers=TOKEN).status_code == 200  # servicio interno


def test_crear_borrador_lo_deja_en_la_bandeja(api, db):
    lleno = _plan_lleno(db)
    propuesta = api.get(URL, headers=MODERADOR).json()["items"][0]
    r = api.post(f"{URL}/borrador", json=propuesta | {"fecha_inicio": "2027-04-17T18:00:00+02:00"}, headers=MODERADOR)
    assert r.status_code == 201, r.text
    evento = r.json()
    assert evento["estado"] == "en_revision" and evento["municipio"] == "Tahal"
    assert evento["fecha_inicio"] == "2027-04-17T18:00:00+02:00"
    assert evento["origen"]["canal"] == "panel"
    pendientes = api.get("/api/v1/moderacion/pendientes", headers=MODERADOR).json()["items"]
    en_bandeja = next(p for p in pendientes if p["evento"]["id"] == evento["id"])
    assert en_bandeja["motivo"].startswith(f"Propuesto por la IA a partir de «{lleno.titulo}»")
    r = api.post(f"/api/v1/moderacion/{evento['id']}/decision", json={"decision": "aprobar", "motivo": None},
                 headers=MODERADOR)
    assert r.status_code == 200 and r.json()["estado"] == "publicado"


def test_crear_borrador_valida(api):
    base = {"titulo": "X", "categoria": "cultural", "municipio": "Madrid", "motivo": "m",
            "fecha_inicio": "2027-04-17T18:00:00+02:00"}
    r = api.post(f"{URL}/borrador", json=base, headers=MODERADOR)
    assert r.status_code == 422 and r.json()["error"]["code"] == "municipio_no_encontrado"
    sin_fecha = {k: v for k, v in base.items() if k != "fecha_inicio"} | {"municipio": "Tahal"}
    assert api.post(f"{URL}/borrador", json=sin_fecha, headers=MODERADOR).status_code == 422
    vecina = {"Authorization": f"Bearer {emitir_jwt(CARMEN, 'vecino')}"}
    assert api.post(f"{URL}/borrador", json=base | {"municipio": "Tahal"}, headers=vecina).status_code == 403


def test_n5a_ocupacion_cuenta_las_plazas_ocupadas_del_plan(api, db):
    # Las migas del seed llenaron 18 de 20 plazas, aunque desde la plataforma solo se apuntaran 4: la tarjeta de
    # ideas de la IA tiene que decir lo mismo que «Ocupación por tipo de plan» del panel (gastronomía 90 %).
    migas = next(p for p in sugerencias.participacion(db) if p["titulo"].startswith("Taller de cocina: migas"))
    assert migas["inscritos"] == 4
    assert migas["ocupacion"] == 0.9
    propuesta = sugerencias.por_reglas([migas], 1, datetime(2026, 11, 21, tzinfo=timezone.utc))[0]
    assert "se ocupó el 90 % (18 de 20 plazas)" in propuesta["motivo"]
