"""P5a: `eventos.propuesto_por_id` (usuario que propuso el plan), para «Mis planes propuestos» y para que un vecino
sin asociación sea dueño de lo que propone (verlo, modificarlo y apelarlo). Opcional; los planes que ya existen se
quedan en null. `recreate="never"`, como en 0007.

Revision ID: 0010
Revises: 0009
Create Date: 2026-11-21 22:10:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0010'
down_revision = '0009'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('eventos', schema=None, recreate='never') as batch_op:
        batch_op.add_column(sa.Column('propuesto_por_id', sa.String(length=36), nullable=True))
        batch_op.create_index('ix_eventos_propuesto_por_id', ['propuesto_por_id'])


def downgrade() -> None:
    with op.batch_alter_table('eventos', schema=None, recreate='never') as batch_op:
        batch_op.drop_index('ix_eventos_propuesto_por_id')
        batch_op.drop_column('propuesto_por_id')
