"""La migración crea todas las tablas en una base vacía, coincide con los modelos y se puede deshacer."""

from pathlib import Path

import pytest
from alembic import command
from alembic.autogenerate import compare_metadata
from alembic.config import Config
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlalchemy.exc import IntegrityError

from app import modelos  # noqa: F401
from app.db import Base, crear_motor

API = Path(__file__).resolve().parents[1]

TABLAS = {
    "municipios", "lugares", "usuarios", "publicadores", "fuentes", "eventos",
    "inscripciones", "mensajes_evento", "notificaciones", "metricas_tokens",
}


def _config(url: str) -> Config:
    cfg = Config(str(API / "alembic.ini"))
    cfg.attributes["url"] = url
    cfg.attributes["configurar_logs"] = False
    return cfg


@pytest.fixture
def url(tmp_path):
    return f"sqlite:///{(tmp_path / 'vacia.db').as_posix()}"


def test_upgrade_crea_todas_las_tablas(url):
    command.upgrade(_config(url), "head")
    motor = crear_motor(url)
    assert TABLAS <= set(inspect(motor).get_table_names())
    motor.dispose()


def test_migracion_coincide_con_los_modelos(url):
    command.upgrade(_config(url), "head")
    motor = crear_motor(url)
    with motor.connect() as conexion:
        diferencias = compare_metadata(MigrationContext.configure(conexion), Base.metadata)
    motor.dispose()
    assert not diferencias, f"Los modelos han cambiado sin migración: {diferencias}"


def test_downgrade_deja_la_base_vacia(url):
    cfg = _config(url)
    command.upgrade(cfg, "head")
    command.downgrade(cfg, "base")
    motor = crear_motor(url)
    assert not TABLAS & set(inspect(motor).get_table_names())
    motor.dispose()


def test_la_base_rechaza_datos_fuera_del_contrato(url):
    command.upgrade(_config(url), "head")
    motor = crear_motor(url)
    with motor.begin() as c:
        c.execute(text("INSERT INTO municipios (nombre, lat, lon) VALUES ('Senés', 37.1983, -2.3447)"))
    insertar = (
        "INSERT INTO publicadores (id, nombre, tipo, municipio, estado, nivel_confianza, aprobaciones, "
        "automatizaciones_pausadas, categorias_habituales, creado_en) "
        "VALUES (:id, 'Prueba', 'otro', :municipio, 'aprobado', :nivel, 0, 0, '[]', '2026-11-20 10:00:00')"
    )
    # Nivel de confianza fuera de 0/1/2
    with pytest.raises(IntegrityError), motor.begin() as c:
        c.execute(text(insertar), {"id": "a", "municipio": "Senés", "nivel": 3})
    # Pueblo que no existe (clave foránea)
    with pytest.raises(IntegrityError), motor.begin() as c:
        c.execute(text(insertar), {"id": "b", "municipio": "Almería", "nivel": 0})
    motor.dispose()
