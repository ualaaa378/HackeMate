"""El seed carga los datos de la demo, omite y borra los eventos ya terminados y no duplica al repetirse."""

from datetime import datetime, timedelta, timezone

from sqlalchemy import func, select

from app.modelos import Evento, Inscripcion, Lugar, MensajeEvento, Municipio, Publicador, Usuario
from app.seed import migrar, sembrar, vaciar

# Hora fija para que el test no dependa del día en que se ejecute: viernes del hackathon
VIERNES = datetime(2026, 11, 20, 18, 0, tzinfo=timezone.utc)
RUTA_SOLIDARIA = "1e5d0000-0000-4000-8000-000000000001"
DIA_DE_LAS_FLORES = "d351aeee-3001-5b8a-b6c6-ce4c9348ec57"
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
    assert _contar(db, Publicador) == 7
    assert _contar(db, Usuario) == 5
    # 32 eventos en los fixtures: 12 reales ya terminados el viernes 20 → 18 publicados + 2 en revisión
    assert resumen["eventos"] == 20 and resumen["eventos_terminados_omitidos"] == 12
    assert _contar(db, Evento) == 20

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
    assert _contar(db, Evento) == 20
    assert _contar(db, Publicador) == 7
    assert _contar(db, Usuario) == 5
    assert _contar(db, Inscripcion) == 3
    assert _contar(db, MensajeEvento) == 3


def test_al_pasar_el_dia_los_eventos_terminados_se_borran_con_lo_que_cuelga(db):
    _sembrar(db)
    assert _contar(db, Inscripcion) == 3
    # Una semana después de la Ruta Solidaria (29 nov), vuelve a sembrarse
    resumen = _sembrar(db, ahora=datetime(2026, 12, 6, 12, 0, tzinfo=timezone.utc))
    assert db.get(Evento, RUTA_SOLIDARIA) is None
    assert resumen["eventos_terminados_borrados"] > 0
    assert all(e.fecha_fin is None or e.fecha_fin > datetime(2026, 12, 6, 12, 0, tzinfo=timezone.utc)
               for e in db.scalars(select(Evento)))
    # Sus inscripciones y mensajes desaparecen con él
    assert not db.scalars(select(Inscripcion).where(Inscripcion.evento_id == RUTA_SOLIDARIA)).all()
    assert not db.scalars(select(MensajeEvento).where(MensajeEvento.evento_id == RUTA_SOLIDARIA)).all()


def test_no_borra_lo_que_crean_los_usuarios(db):
    _sembrar(db)
    db.add(Evento(titulo="Evento creado en la app", categoria="ludica", municipio="Tahal", lat=37.2, lon=-2.28,
                  fecha_inicio=VIERNES - timedelta(days=30), estado="finalizado"))
    db.commit()
    _sembrar(db)
    assert _contar(db, Evento) == 21


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
        assert _contar(db, Evento) == 20
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
