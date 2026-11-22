"""Motor de base de datos, sesión por petición y clase base de los modelos.
Funciona con SQLite (local) y PostgreSQL (Docker)."""

from collections.abc import Iterator
from functools import lru_cache
from pathlib import Path

from sqlalchemy import MetaData, create_engine, event
from sqlalchemy.engine import Engine
from sqlalchemy.orm import DeclarativeBase, Session, sessionmaker

from app.config import get_settings

# Nombres de restricciones estables: Alembic los necesita para poder modificarlas en SQLite y PostgreSQL.
NOMBRES = {
    "ix": "ix_%(column_0_label)s",
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s",
}


class Base(DeclarativeBase):
    metadata = MetaData(naming_convention=NOMBRES)


API_DIR = Path(__file__).resolve().parents[1]  # services/api


def _sqlite_absoluta(url: str) -> str:
    """sqlite:///./hackemate.db → siempre services/api/hackemate.db, se lance desde donde se lance
    (uvicorn, alembic, scripts/seed.py o los tests usan así la misma base)."""
    prefijo = "sqlite:///"
    if not url.startswith(prefijo) or url == "sqlite://" or ":memory:" in url:
        return url
    ruta = Path(url[len(prefijo):])
    return url if ruta.is_absolute() else prefijo + (API_DIR / ruta).resolve().as_posix()


def crear_motor(url: str | None = None) -> Engine:
    url = _sqlite_absoluta(url or get_settings().database_url)
    opciones = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=opciones, pool_pre_ping=True)


@lru_cache
def _fabrica_sesiones() -> sessionmaker[Session]:
    # Se crea en la primera petición, no al importar: la API arranca aunque la base aún no responda.
    return sessionmaker(bind=crear_motor(), expire_on_commit=False)


def get_db() -> Iterator[Session]:
    """Dependencia de FastAPI: una sesión por petición. Las rutas que escriben hacen commit;
    si algo falla a medias, se deshace todo al cerrar."""
    sesion = _fabrica_sesiones()()
    try:
        yield sesion
    finally:
        sesion.close()


@event.listens_for(Engine, "connect")
def _sqlite_claves_foraneas(conexion, _):
    # SQLite no comprueba las claves foráneas si no se le pide en cada conexión.
    if conexion.__class__.__module__.startswith("sqlite3"):
        cursor = conexion.cursor()
        cursor.execute("PRAGMA foreign_keys=ON")
        cursor.close()
