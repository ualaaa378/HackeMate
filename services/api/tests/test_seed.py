"""El seed carga los datos de la demo, omite y borra los eventos ya terminados y no duplica al repetirse.
El histórico del panel (eventos_pasados.json, H4.3) se carga siempre: 8 actividades finalizadas, 17 inscripciones."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.modelos import Evento, Inscripcion, Lugar, MensajeEvento, Municipio, Publicador, Usuario
from app.seed import migrar, sembrar, vaciar

# Hora fija para que el test no dependa del día en que se ejecute: viernes del hackathon
VIERNES = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
RUTA_SOLIDARIA = "1e5d0000-0000-4000-8000-000000000001"
DIA_DE_LAS_FLORES = "d351aeee-3001-5b8a-b6c6-ce4c9348ec57"
HISTORICO = 8  # eventos_pasados.json
INSCRIPCIONES_HISTORICO = 17  # inscripciones_pasadas.json
CINE_DE_VERANO = "4a5a0000-0000-4000-8000-000000000001"
TALLER_GRAFITI = "1e5d0000-0000-4000-8000-000000000009"
APUESTAS_BAR = "1e5d0000-0000-4000-8000-000000000010"


def _contar(db, modelo) -> int:
    return db.scalar(select(func.count()).select_from(modelo))


def _sembrar(db, ahora=VIERNES) -> dict:
    resumen = sembrar(db, ahora=ahora)
    db.commit()
    return resumen


def test_carga_los_datos_de_la_demo(db):
    resumen = _sembrar(db)
    assert _contar(db, Municipio) == 5
    assert _contar(db, Lugar) == 35
    assert _contar(db, Publicador) == 10
    assert _contar(db, Usuario) == 5
    # 32 eventos en los fixtures: 12 reales ya terminados el viernes 20 → 18 publicados + 2 en revisión
    assert resumen["eventos"] == 20 and resumen["eventos_terminados_omitidos"] == 12
    assert resumen["eventos_historico"] == HISTORICO and resumen["inscripciones_historico"] == INSCRIPCIONES_HISTORICO
    assert _contar(db, Evento) == 20 + HISTORICO
    cine = db.get(Evento, CINE_DE_VERANO)
    assert cine.estado == "finalizado" and cine.municipio == "Uleila del Campo" and cine.plazas_totales == 120

    ruta = db.get(Evento, RUTA_SOLIDARIA)
    assert ruta.titulo.startswith("II Ruta Solidaria") and ruta.municipio == "Velefique"
    assert ruta.origen_canal == "facebook" and ruta.publicador.nombre == "Amigos de Velefique"
    assert ruta.fecha_inicio == datetime(2026, 11, 29, 8, 0, tzinfo=timezone.utc)  # 09:00 en Madrid
    assert db.get(Evento, DIA_DE_LAS_FLORES) is None

    carmen = db.scalar(select(Usuario).where(Usuario.nombre == "Carmen"))
    assert carmen.municipio == "Senés" and "senderismo" in carmen.etiquetas_interes
    bar = db.scalar(select(Publicador).where(Publicador.nombre == "Bar La Plaza"))
    assert bar.nivel_confianza == 2 and bar.fuentes[0].canal == "instagram"
    antonio = db.scalar(select(Usuario).where(Usuario.nombre.startswith("Antonio")))
    assert antonio.publicador_id is not None


def test_repetir_no_duplica(db):
    _sembrar(db)
    _sembrar(db)
    assert _contar(db, Evento) == 20 + HISTORICO
    assert _contar(db, Publicador) == 10
    assert _contar(db, Usuario) == 5
    assert _contar(db, Inscripcion) == 3 + INSCRIPCIONES_HISTORICO
    assert _contar(db, MensajeEvento) == 3


def test_al_pasar_el_dia_los_eventos_terminados_se_borran_con_lo_que_cuelga(db):
    _sembrar(db)
    assert _contar(db, Inscripcion) == 3 + INSCRIPCIONES_HISTORICO
    # Una semana después de la Ruta Solidaria (29 nov), vuelve a sembrarse
    resumen = _sembrar(db, ahora=datetime(2026, 12, 6, 12, 0, tzinfo=timezone.utc))
    assert db.get(Evento, RUTA_SOLIDARIA) is None
    assert resumen["eventos_terminados_borrados"] > 0
    assert all(e.fecha_fin is None or e.fecha_fin > datetime(2026, 12, 6, 12, 0, tzinfo=timezone.utc)
               for e in db.scalars(select(Evento).where(Evento.estado != "finalizado")))
    # El histórico del panel no se toca
    assert db.get(Evento, CINE_DE_VERANO) is not None
    # Sus inscripciones y mensajes desaparecen con él
    assert not db.scalars(select(Inscripcion).where(Inscripcion.evento_id == RUTA_SOLIDARIA)).all()
    assert not db.scalars(select(MensajeEvento).where(MensajeEvento.evento_id == RUTA_SOLIDARIA)).all()


def test_no_borra_lo_que_crean_los_usuarios(db):
    _sembrar(db)
    db.add(Evento(titulo="Evento creado en la app", categoria="ludica", municipio="Tahal", lat=37.2, lon=-2.28,
                  fecha_inicio=VIERNES - timedelta(days=30), estado="finalizado"))
    db.commit()
    _sembrar(db)
    assert _contar(db, Evento) == 21 + HISTORICO


def test_reset_y_migracion_desde_cero(tmp_path):
    from sqlalchemy.orm import Session

    from app.db import crear_motor

    url = f"sqlite:///{(tmp_path / 'demo.db').as_posix()}"
    migrar(url)
    motor = crear_motor(url)
    with Session(motor) as db:
        _sembrar(db)
        vaciar(db)
        db.commit()
        assert _contar(db, Evento) == 0 and _contar(db, Usuario) == 0
        _sembrar(db)
        assert _contar(db, Evento) == 20 + HISTORICO
    motor.dispose()


def test_demo_de_moderacion(db):
    """H2.7: un publicador de nivel 0, Bar La Plaza de nivel 2 y la bandeja del moderador con dos eventos."""
    _sembrar(db)
    juvenil = db.scalar(select(Publicador).where(Publicador.nombre == "Asociación Juvenil de Tahal"))
    assert juvenil.nivel_confianza == 0 and juvenil.aprobaciones == 0 and juvenil.estado == "aprobado"
    assert juvenil.municipio == "Tahal" and juvenil.telefono == "+34600000307"
    bar = db.scalar(select(Publicador).where(Publicador.nombre == "Bar La Plaza"))
    assert bar.nivel_confianza == 2 and "gastronomia" in bar.categorias_habituales
    assert db.scalar(select(Usuario).where(Usuario.rol == "moderador")) is not None

    en_revision = db.scalars(select(Evento).where(Evento.estado == "en_revision")).all()
    assert {e.id for e in en_revision} == {TALLER_GRAFITI, APUESTAS_BAR}
    taller, apuestas = db.get(Evento, TALLER_GRAFITI), db.get(Evento, APUESTAS_BAR)
    assert taller.publicador_id == juvenil.id and taller.score_spam < 0.2
    assert taller.motivo_moderacion == "Publicador nuevo (nivel 0)"
    assert apuestas.publicador_id == bar.id and apuestas.score_spam == 0.95
    assert apuestas.motivo_moderacion.startswith("Posible spam")


# --- arranque del contenedor: --solo-nuevos no deshace lo que hacen las personas ----------------------------------

CARMEN = "5a5e0000-0000-4000-8000-000000000001"


def _cambios_de_la_demo(db) -> dict:
    """Lo que haría la gente durante un ensayo sobre los datos de la demo."""
    ruta = db.get(Evento, RUTA_SOLIDARIA)
    nueva_hora = ruta.fecha_inicio + timedelta(hours=2)
    ruta.fecha_inicio, ruta.plazas_libres = nueva_hora, ruta.plazas_libres - 1  # cambio de hora y alguien se apunta
    otra = Usuario(nombre="Se apunta")
    db.add(otra)
    db.flush()
    db.add(Inscripcion(evento_id=ruta.id, usuario_id=otra.id, plazas=1, estado="confirmada", canal="web"))
    db.get(Evento, TALLER_GRAFITI).estado = "publicado"  # el moderador lo aprueba
    carmen = db.get(Usuario, CARMEN)
    carmen.nombre = "Carmen (editado)"
    db.commit()
    return {"hora": nueva_hora, "plazas": ruta.plazas_libres}


def test_solo_nuevos_no_sobrescribe_lo_que_ya_existe(db):
    _sembrar(db)
    antes = _cambios_de_la_demo(db)
    eventos = _contar(db, Evento)

    sembrar(db, ahora=VIERNES, sobrescribir=False)  # como al reiniciar el contenedor api
    db.commit()
    db.expire_all()
    ruta = db.get(Evento, RUTA_SOLIDARIA)
    assert ruta.fecha_inicio.replace(tzinfo=None) == antes["hora"].replace(tzinfo=None)
    assert ruta.plazas_libres == antes["plazas"]
    assert db.get(Evento, TALLER_GRAFITI).estado == "publicado"
    assert db.get(Usuario, CARMEN).nombre == "Carmen (editado)"
    assert _contar(db, Evento) == eventos  # no duplica


def test_solo_nuevos_anade_lo_que_falta(db):
    _sembrar(db)
    db.delete(db.get(Evento, APUESTAS_BAR))
    db.commit()
    resumen = sembrar(db, ahora=VIERNES, sobrescribir=False)
    db.commit()
    assert db.get(Evento, APUESTAS_BAR) is not None
    assert resumen["eventos"] > 0


def test_solo_nuevos_sigue_quitando_los_eventos_terminados(db):
    _sembrar(db)
    sembrar(db, ahora=datetime(2027, 6, 1, tzinfo=timezone.utc), sobrescribir=False)
    db.commit()
    assert db.get(Evento, RUTA_SOLIDARIA) is None


def test_sin_solo_nuevos_vuelve_a_los_fixtures(db):
    # El seed a mano (y demo_reset) sigue dejando los datos de la demo como en los fixtures.
    _sembrar(db)
    _cambios_de_la_demo(db)
    _sembrar(db)
    db.expire_all()
    assert db.get(Evento, TALLER_GRAFITI).estado == "en_revision"
    assert db.get(Usuario, CARMEN).nombre != "Carmen (editado)"


def test_n6_plazas_libres_salen_de_las_inscripciones(db):
    """N6: la Ruta Solidaria tiene 40 plazas y una inscripción confirmada en los fixtures → 39 libres, no las 8
    inventadas. Los finalizados guardan su ocupación (estadísticas)."""
    resumen = _sembrar(db)
    assert db.get(Evento, RUTA_SOLIDARIA).plazas_libres == 39
    assert resumen["plazas_recalculadas"] >= 1
    finalizados = db.scalars(select(Evento).where(Evento.estado == "finalizado", Evento.plazas_totales > 0)).all()
    assert finalizados and any(e.plazas_libres < e.plazas_totales for e in finalizados)
