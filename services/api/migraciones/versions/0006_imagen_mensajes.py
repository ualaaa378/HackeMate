"""Foto en los comentarios de planes pasados: columna `imagen_url` (Text, opcional) en `mensajes_evento`.

En SQLite, batch_alter_table recrea la tabla; en PostgreSQL hace ALTER TABLE directos.

Revision ID: 0006
Revises: 0005
Create Date: 2026-11-21 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0006'
down_revision = '0005'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('mensajes_evento', schema=None) as batch_op:
        batch_op.add_column(sa.Column('imagen_url', sa.Text(), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('mensajes_evento', schema=None) as batch_op:
        batch_op.drop_column('imagen_url')
