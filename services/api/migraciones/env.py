from logging.config import fileConfig

from alembic import context

from app import modelos  # noqa: F401  (registra las tablas en Base.metadata)
from app.config import get_settings
from app.db import Base, crear_motor

config = context.config
if config.config_file_name is not None and config.attributes.get("configurar_logs", True):
    fileConfig(config.config_file_name)

objetivo = Base.metadata


def _url() -> str:
    # Los tests pasan su propia URL; si no, la de DATABASE_URL.
    return config.attributes.get("url") or get_settings().database_url


def offline() -> None:
    context.configure(url=_url(), target_metadata=objetivo, literal_binds=True, render_as_batch=True)
    with context.begin_transaction():
        context.run_migrations()


def online() -> None:
    motor = crear_motor(_url())
    with motor.connect() as conexion:
        # render_as_batch: SQLite no sabe hacer ALTER TABLE completos; así las migraciones valen para las dos bases.
        context.configure(connection=conexion, target_metadata=objetivo, render_as_batch=True, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()
    motor.dispose()


if context.is_offline_mode():
    offline()
else:
    online()
