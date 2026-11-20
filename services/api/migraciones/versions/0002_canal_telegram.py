"""Canal Telegram: valor `telegram` en el enum `canal` y columna `telegram_id` en usuarios y publicadores.

Los enums son texto con CHECK: hay que recrear las tres restricciones que usan el enum `canal`.
En SQLite, batch_alter_table recrea la tabla; en PostgreSQL hace ALTER TABLE directos.

Revision ID: 0002
Revises: 0001
Create Date: 2026-11-20 21:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0002'
down_revision = '0001'
branch_labels = None
depends_on = None

CANALES_ANTES = ("whatsapp", "web", "panel", "facebook", "instagram", "web_externa", "manual")
CANALES_AHORA = CANALES_ANTES + ("telegram",)

# (tabla, nombre del enum, columna): la restriccion se llama ck_<tabla>_<enum> (app/db.py NOMBRES)
CHECKS_CANAL = (
    ("eventos", "canal_origen", "origen_canal"),
    ("fuentes", "canal_fuente", "canal"),
    ("inscripciones", "canal_inscripcion", "canal"),
)


def _recrear_checks(valores: tuple[str, ...]) -> None:
    for tabla, enum, columna in CHECKS_CANAL:
        nombre = op.f(f"ck_{tabla}_{enum}")
        with op.batch_alter_table(tabla, schema=None) as batch_op:
            batch_op.drop_constraint(nombre, type_="check")
            batch_op.create_check_constraint(nombre, sa.column(columna).in_(valores))


def upgrade() -> None:
    _recrear_checks(CANALES_AHORA)
    for tabla in ("usuarios", "publicadores"):
        with op.batch_alter_table(tabla, schema=None) as batch_op:
            batch_op.add_column(sa.Column('telegram_id', sa.String(length=32), nullable=True))
            batch_op.create_index(batch_op.f(f'ix_{tabla}_telegram_id'), ['telegram_id'], unique=True)


def downgrade() -> None:
    for tabla in ("usuarios", "publicadores"):
        with op.batch_alter_table(tabla, schema=None) as batch_op:
            batch_op.drop_index(batch_op.f(f'ix_{tabla}_telegram_id'))
            batch_op.drop_column('telegram_id')
    # Lo que entro por Telegram pasa a `manual` para que cumpla la restriccion antigua.
    for tabla, _, columna in CHECKS_CANAL:
        t = sa.table(tabla, sa.column(columna))
        op.execute(t.update().where(t.c[columna] == "telegram").values({columna: "manual"}))
    _recrear_checks(CANALES_ANTES)
