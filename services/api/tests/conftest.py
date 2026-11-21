import os
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
# Sin tarea de fondo de reintentos: tocaría la base real (DATABASE_URL), no la temporal de cada test.
os.environ["NOTIFICACIONES_REINTENTO_S"] = "0"

from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy.orm import Session, sessionmaker  # noqa: E402

from app import modelos  # noqa: E402,F401
from app.db import Base, crear_motor, get_db  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture
def motor(tmp_path):
    """Base SQLite vacía (con todas las tablas) solo para este test."""
    m = crear_motor(f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    Base.metadata.create_all(m)
    yield m
    m.dispose()


@pytest.fixture
def db(motor) -> Session:
    sesion = sessionmaker(bind=motor, expire_on_commit=False)()
    yield sesion
    sesion.close()


@pytest.fixture
def cliente(motor):
    """Cliente de la API que usa la base temporal en vez de DATABASE_URL."""
    fabrica = sessionmaker(bind=motor, expire_on_commit=False)

    def _db():
        sesion = fabrica()
        try:
            yield sesion
        finally:
            sesion.close()

    app.dependency_overrides[get_db] = _db
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture(autouse=True)
def _limites_a_cero():
    """Los límites en memoria (intentos de /auth/admin, mensajes por minuto) empiezan vacíos en cada test."""
    from app.rutas import auth, mensajes

    auth._fallos_admin.clear()
    mensajes._enviados.clear()
    yield
    auth._fallos_admin.clear()
    mensajes._enviados.clear()
