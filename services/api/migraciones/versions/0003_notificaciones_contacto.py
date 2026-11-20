"""Cola de avisos por cualquier canal: columna `contacto` (`+34…` o `tg:<chat_id>`), `telefono` opcional
y `plantilla` + `parametros` (para reintentar avisos de WhatsApp fuera de la ventana de 24 h).

Un usuario que solo usa Telegram no tiene telefono; su aviso se guarda igualmente (ver app/notificaciones.py).
En SQLite, batch_alter_table recrea la tabla; en PostgreSQL hace ALTER TABLE directos.

Revision ID: 0003
Revises: 0002
Create Date: 2026-11-21 10:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0003'
down_revision = '0002'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.add_column(sa.Column('contacto', sa.String(length=32), nullable=True))
        batch_op.add_column(sa.Column('plantilla', sa.String(length=64), nullable=True))
        batch_op.add_column(sa.Column('parametros', sa.JSON(), nullable=True))
        batch_op.alter_column('telefono', existing_type=sa.String(length=16), nullable=True)


def downgrade() -> None:
    # Los avisos sin telefono no caben en la tabla antigua (telefono NOT NULL): se borran.
    t = sa.table('notificaciones', sa.column('telefono'))
    op.execute(t.delete().where(t.c.telefono.is_(None)))
    with op.batch_alter_table('notificaciones', schema=None) as batch_op:
        batch_op.alter_column('telefono', existing_type=sa.String(length=16), nullable=False)
        batch_op.drop_column('parametros')
        batch_op.drop_column('plantilla')
        batch_op.drop_column('contacto')
