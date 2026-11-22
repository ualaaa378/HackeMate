"""Cola de avisos (H4.5): POST {BOT_URL}/notify con el bot simulado por httpx.MockTransport."""

import json
from pathlib import Path

import httpx
import pytest
from jsonschema import Draft202012Validator, FormatChecker
from sqlalchemy import select

from app import notificaciones
from app.config import get_settings
from app.modelos import Notificacion, Usuario
from app.notificaciones import destino_de, notificar, notificar_moderadores, reintentar_pendientes
from app.seed import sembrar

ESQUEMA = json.loads(
    (Path(__file__).resolve().parents[3] / "contracts" / "schemas" / "notificacion.json").read_text(encoding="utf-8")
)
VALIDADOR = Draft202012Validator(ESQUEMA, format_checker=FormatChecker())


@pytest.fixture(autouse=True)
def ajustes(monkeypatch):
    monkeypatch.setenv("BOT_URL", "http://bot-falso:8001")
    monkeypatch.setenv("INTERNAL_TOKEN", "token-de-prueba")
    monkeypatch.setenv("NOTIFICACIONES_MAX_INTENTOS", "3")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


class Bot:
    """Bot simulado: guarda lo que recibe y responde según `modo` (ok, caido, lento, error, rechaza)."""

    def __init__(self, modo="ok"):
        self.modo = modo
        self.recibidas: list[httpx.Request] = []

    def __call__(self, peticion: httpx.Request) -> httpx.Response:
        self.recibidas.append(peticion)
        if self.modo == "caido":
            raise httpx.ConnectError("conexion rechazada", request=peticion)
        if self.modo == "lento":
            raise httpx.ReadTimeout("timeout", request=peticion)
        if self.modo == "error":
            return httpx.Response(500, json={"detail": "boom"})
        if self.modo == "rechaza":
            return httpx.Response(422, json={"detail": "telefono"})
        return httpx.Response(200, json={"enviado": True})

    def cuerpos(self) -> list[dict]:
        return [json.loads(p.content) for p in self.recibidas]


@pytest.fixture
def bot(monkeypatch):
    b = Bot()
    monkeypatch.setattr(notificaciones, "_transporte", httpx.MockTransport(b))
    return b


def _usuario(db, **extra) -> Usuario:
    u = Usuario(nombre=extra.pop("nombre", "Carmen"), **extra)
    db.add(u)
    db.commit()
    return u


def test_destino_de_usuario_con_telegram(db):
    u = _usuario(db, telefono="+34600000201", telegram_id="123456")
    assert destino_de(u) == ("+34600000201", "tg:123456")
    assert destino_de(_usuario(db, nombre="Pepe", telefono="+34600000202")) == ("+34600000202", None)


def test_bot_ok_enviada_con_cuerpo_del_contrato(db, bot):
    u = _usuario(db, telefono="+34600000201", telegram_id="123456", formato_aviso="audio")
    n = notificar(db, tipo="cambio_evento", texto="Cambio de hora", usuario=u, botones=["Vale", "No voy", "Otro", "Sobra"])
    db.commit()

    assert n.estado_envio == "enviada" and n.intentos == 1 and n.enviada_en is not None and n.ultimo_error is None
    peticion = bot.recibidas[0]
    assert str(peticion.url) == "http://bot-falso:8001/notify"
    assert peticion.headers["X-Internal-Token"] == "token-de-prueba"
    cuerpo = bot.cuerpos()[0]
    assert cuerpo["telefono"] == "+34600000201"
    assert cuerpo["contacto"] == "tg:123456"
    assert cuerpo["formato"] == "audio"
    assert cuerpo["usuario_id"] == u.id
    assert cuerpo["botones"] == ["Vale", "No voy", "Otro"]
    assert "plantilla" not in cuerpo
    assert not list(VALIDADOR.iter_errors(cuerpo))


def test_plantilla_y_parametros_en_el_cuerpo(db, bot):
    n = notificar(db, tipo="recomendacion", texto="Hola", telefono="+34 600 000 203",
                  plantilla="aviso_evento", parametros=["Ruta", "domingo"])
    assert n.estado_envio == "enviada"
    cuerpo = bot.cuerpos()[0]
    assert cuerpo["telefono"] == "+34600000203" and "contacto" not in cuerpo
    assert cuerpo["plantilla"] == "aviso_evento" and cuerpo["parametros"] == ["Ruta", "domingo"]
    assert not list(VALIDADOR.iter_errors(cuerpo))


@pytest.mark.parametrize("modo", ["caido", "lento", "error"])
def test_bot_caido_o_lento_queda_pendiente_sin_excepcion(db, bot, modo):
    bot.modo = modo
    u = _usuario(db, telefono="+34600000201")
    n = notificar(db, tipo="anuncio", texto="Hola", usuario=u)
    db.commit()
    db.expire_all()
    guardada = db.get(Notificacion, n.id)
    assert guardada.estado_envio == "pendiente"
    assert guardada.intentos == 1
    assert guardada.ultimo_error


def test_sin_bot_url_queda_pendiente(db, bot, monkeypatch):
    monkeypatch.setenv("BOT_URL", "")
    get_settings.cache_clear()
    n = notificar(db, tipo="anuncio", texto="Hola", telefono="+34600000201")
    assert n.estado_envio == "pendiente" and "BOT_URL" in n.ultimo_error and not bot.recibidas


def test_usuario_solo_telegram_recibe_el_aviso(db, bot):
    """A9 (D1): sin teléfono, el aviso sale por su Telegram (`contacto`) y el cuerpo no lleva `telefono`."""
    u = _usuario(db, telegram_id="99")
    n = notificar(db, tipo="anuncio", texto="Hola", usuario=u)
    db.commit()
    assert n.estado_envio == "enviada" and n.contacto == "tg:99" and n.telefono is None
    cuerpo = bot.cuerpos()[-1]
    assert cuerpo["contacto"] == "tg:99" and "telefono" not in cuerpo
    assert not list(VALIDADOR.iter_errors(cuerpo))


def test_sin_telefono_ni_contacto_se_guarda_como_fallida(db, bot):
    n = notificar(db, tipo="anuncio", texto="Hola", usuario=_usuario(db))
    db.commit()
    assert n.estado_envio == "fallida" and n.ultimo_error == "sin destino" and not bot.recibidas


def test_reintentar_con_bot_ok_envia(db, bot):
    bot.modo = "caido"
    a = notificar(db, tipo="anuncio", texto="Uno", telefono="+34600000201")
    b = notificar(db, tipo="anuncio", texto="Dos", telefono="+34600000202")
    db.commit()
    assert {a.estado_envio, b.estado_envio} == {"pendiente"}

    bot.modo = "ok"
    assert reintentar_pendientes(db) == 2
    db.commit()
    assert a.estado_envio == b.estado_envio == "enviada"
    assert a.intentos == b.intentos == 2


def test_reintentar_para_si_el_bot_sigue_caido(db, bot):
    bot.modo = "caido"
    for i in range(3):
        notificar(db, tipo="anuncio", texto=f"Aviso {i}", telefono="+34600000201")
    db.commit()
    bot.recibidas.clear()
    assert reintentar_pendientes(db) == 0
    assert len(bot.recibidas) == 1  # no espera el timeout de cada uno


def test_tras_n_fallos_pasa_a_fallida(db, bot):
    bot.modo = "lento"
    n = notificar(db, tipo="anuncio", texto="Hola", telefono="+34600000201")
    reintentar_pendientes(db)
    assert n.estado_envio == "pendiente" and n.intentos == 2
    reintentar_pendientes(db)
    assert n.estado_envio == "fallida" and n.intentos == 3
    bot.modo = "ok"
    assert reintentar_pendientes(db) == 0  # las fallidas ya no se reintentan
    assert n.estado_envio == "fallida"


def test_rechazo_del_bot_no_frena_la_cola(db, bot):
    bot.modo = "rechaza"
    notificar(db, tipo="anuncio", texto="Uno", telefono="+34600000201")
    notificar(db, tipo="anuncio", texto="Dos", telefono="+34600000202")
    bot.recibidas.clear()
    reintentar_pendientes(db)
    assert len(bot.recibidas) == 2


def test_notificar_moderadores_una_por_moderador(db, bot):
    sembrar(db)
    _usuario(db, nombre="Otra moderadora", rol="moderador", telefono="+34600000299", telegram_id="777")
    moderadores = db.scalars(select(Usuario).where(Usuario.rol == "moderador")).all()
    assert len(moderadores) >= 2

    avisos = notificar_moderadores(db, "moderacion", "Hay un evento en revisión", evento_id=None)
    db.commit()
    assert len(avisos) == len(moderadores)
    assert {a.usuario_id for a in avisos} == {m.id for m in moderadores}
    assert all(a.estado_envio == "enviada" and a.tipo == "moderacion" for a in avisos)
    assert {c.get("contacto") for c in bot.cuerpos()} >= {"tg:777"}


# --- Envío después del commit (enviar=False + BackgroundTasks) ------------------------------------


def test_enviar_false_no_llama_al_bot(db, bot):
    n = notificar(db, tipo="anuncio", texto="Hola", telefono="+34600000201", enviar=False)
    db.commit()
    assert n.estado_envio == "pendiente" and n.intentos == 0 and not bot.recibidas
    solo_tg = notificar(db, tipo="anuncio", texto="Hola", usuario=_usuario(db, telegram_id="98"), enviar=False)
    assert solo_tg.estado_envio == "pendiente"
    sin_destino = notificar(db, tipo="anuncio", texto="Hola", usuario=_usuario(db), enviar=False)
    assert sin_destino.estado_envio == "fallida" and sin_destino.ultimo_error == "sin destino"


@pytest.mark.parametrize("modo, estado, intentos", [("ok", "enviada", 1), ("caido", "pendiente", 1)])
def test_enviar_avisos_con_sesion_propia(db, motor, bot, modo, estado, intentos):
    bot.modo = modo
    n = notificar(db, tipo="anuncio", texto="Hola", telefono="+34600000201", enviar=False)
    db.commit()
    assert notificaciones.enviar_avisos(motor, [n.id]) == (1 if modo == "ok" else 0)
    db.expire_all()
    guardada = db.get(Notificacion, n.id)
    assert guardada.estado_envio == estado and guardada.intentos == intentos


def test_enviar_avisos_tras_n_fallos_fallida(db, motor, bot):
    bot.modo = "lento"
    n = notificar(db, tipo="anuncio", texto="Hola", telefono="+34600000201", enviar=False)
    db.commit()
    for _ in range(3):
        notificaciones.enviar_avisos(motor, [n.id])
    db.expire_all()
    assert db.get(Notificacion, n.id).estado_envio == "fallida"


@pytest.mark.parametrize("modo, esperadas", [("caido", 1), ("lento", 1), ("error", 1), ("rechaza", 3)])
def test_lote_para_en_cuanto_el_bot_no_responde(db, motor, bot, modo, esperadas):
    bot.modo = modo
    ids = [notificar(db, tipo="anuncio", texto=f"Aviso {i}", telefono="+34600000201", enviar=False).id
           for i in range(3)]
    db.commit()
    notificaciones.enviar_avisos(motor, ids)
    assert len(bot.recibidas) == esperadas


def test_enviar_en_segundo_plano_programa_solo_pendientes(db, motor, bot):
    from fastapi import BackgroundTasks

    tareas = BackgroundTasks()
    a = notificar(db, tipo="anuncio", texto="Uno", telefono="+34600000201", enviar=False)
    b = notificar(db, tipo="anuncio", texto="Dos", usuario=_usuario(db), enviar=False)  # sin destino: fallida
    db.commit()
    assert notificaciones.enviar_en_segundo_plano(tareas, db, [a, b, None]) == [a.id]
    assert not bot.recibidas  # aún no: corre después de la respuesta
    assert len(tareas.tasks) == 1
    tarea = tareas.tasks[0]
    tarea.func(*tarea.args, **tarea.kwargs)
    db.expire_all()
    assert db.get(Notificacion, a.id).estado_envio == "enviada" and len(bot.recibidas) == 1


# --- Tarea de fondo de reintentos (H4.5) ----------------------------------------------------------


def test_ciclo_reintentos_envia_y_guarda_con_sesion_propia(db, motor, bot):
    from sqlalchemy.orm import sessionmaker

    from app.notificaciones import ciclo_reintentos

    bot.modo = "caido"
    n = notificar(db, tipo="anuncio", texto="Hola", telefono="+34600000201")
    db.commit()
    assert n.estado_envio == "pendiente"

    bot.modo = "ok"
    assert ciclo_reintentos(sessionmaker(bind=motor, expire_on_commit=False)) == 1
    db.expire_all()
    assert db.get(Notificacion, n.id).estado_envio == "enviada"  # el commit es del propio ciclo


def test_ciclo_reintentos_no_lanza_si_falla_la_base(bot):
    from app.notificaciones import ciclo_reintentos

    def fabrica_rota():
        raise RuntimeError("base caida")

    assert ciclo_reintentos(fabrica_rota) == 0


def test_bucle_de_fondo_llama_al_ciclo_y_se_cancela(monkeypatch):
    import asyncio

    from app import main

    llamadas = []
    monkeypatch.setattr(main, "ciclo_reintentos", lambda: llamadas.append(1) or 0)

    async def probar():
        tarea = asyncio.create_task(main.bucle_reintentos(0.01))
        while len(llamadas) < 2:
            await asyncio.sleep(0.01)
        tarea.cancel()
        try:
            await tarea
        except asyncio.CancelledError:
            pass

    asyncio.run(asyncio.wait_for(probar(), 5))
    assert len(llamadas) >= 2


def test_bucle_de_fondo_sobrevive_a_excepciones(monkeypatch):
    import asyncio

    from app import main

    llamadas = []

    def falla():
        llamadas.append(1)
        raise RuntimeError("boom")

    monkeypatch.setattr(main, "ciclo_reintentos", falla)

    async def probar():
        tarea = asyncio.create_task(main.bucle_reintentos(0.01))
        while len(llamadas) < 3:
            await asyncio.sleep(0.01)
        tarea.cancel()

    asyncio.run(asyncio.wait_for(probar(), 5))
    assert len(llamadas) >= 3


# --- Robustez de la cola ---------------------------------------------------------------------------


def test_reintentar_tras_un_fallo_de_base_deja_la_sesion_usable(db, bot, monkeypatch, caplog):
    """Si algo falla a mitad (p. ej. un flush roto), se hace rollback: el commit de ciclo_reintentos no lanza
    PendingRollbackError y la sesión sigue sirviendo."""
    from sqlalchemy.orm import sessionmaker

    from app.notificaciones import ciclo_reintentos

    def _lote_roto(sesion, avisos):
        sesion.add(Usuario(nombre=None))  # NOT NULL: el flush falla y la sesión queda pendiente de rollback
        sesion.flush()

    monkeypatch.setattr(notificaciones, "_enviar_lote", _lote_roto)
    assert reintentar_pendientes(db) == 0
    db.commit()  # sin PendingRollbackError
    assert db.scalars(select(Notificacion)).all() is not None

    caplog.clear()
    assert ciclo_reintentos(sessionmaker(bind=db.get_bind(), expire_on_commit=False)) == 0
    assert not [r for r in caplog.records if "ciclo de reintento" in r.getMessage()]


def test_dos_envios_a_la_vez_del_mismo_aviso_salen_una_vez(db, motor, bot, monkeypatch):
    """enviar_avisos (segundo plano) y el bucle de reintentos cogen el mismo aviso a la vez: gracias a la reserva
    sobre `intentos`, el bot lo recibe una sola vez."""
    import threading

    from sqlalchemy.orm import sessionmaker

    from app.notificaciones import ciclo_reintentos

    n = notificar(db, tipo="anuncio", texto="Hola", telefono="+34600000201", enviar=False)
    db.commit()

    salida = threading.Barrier(2)
    reservar = notificaciones._reservar

    def _reservar_a_la_vez(sesion, aviso):
        assert aviso.intentos == 0  # los dos lo han leído pendiente y sin intentos
        salida.wait(10)
        return reservar(sesion, aviso)

    monkeypatch.setattr(notificaciones, "_reservar", _reservar_a_la_vez)
    resultados = []
    hilos = [
        threading.Thread(target=lambda: resultados.append(notificaciones.enviar_avisos(motor, [n.id]))),
        threading.Thread(target=lambda: resultados.append(
            ciclo_reintentos(sessionmaker(bind=motor, expire_on_commit=False)))),
    ]
    for h in hilos:
        h.start()
    for h in hilos:
        h.join(30)

    assert sorted(resultados) == [0, 1]
    assert len(bot.recibidas) == 1
    db.expire_all()
    guardada = db.get(Notificacion, n.id)
    assert guardada.estado_envio == "enviada" and guardada.intentos == 1


def test_contrato_exige_telefono_o_contacto():
    """A9 (D1): basta con uno de los dos; sin ninguno, el contrato lo rechaza."""
    base = {"tipo": "anuncio", "texto": "Hola"}
    assert not list(VALIDADOR.iter_errors(base | {"telefono": "+34600000201"}))
    assert not list(VALIDADOR.iter_errors(base | {"contacto": "tg:99"}))
    assert list(VALIDADOR.iter_errors(base))
