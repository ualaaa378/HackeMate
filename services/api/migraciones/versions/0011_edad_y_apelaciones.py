"""P4a: `usuarios.edad` (14-120, opcional). P3a: `eventos.apelacion_motivo` y `eventos.apelacion_en` (una apelación
por plan rechazado). Todo opcional; lo que ya existe se queda en null. `recreate="never"`, como en 0007 y 0010.

Revision ID: 0011
Revises: 0010
Create Date: 2026-11-21 22:30:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0011'
down_revision = '0010'
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table('usuarios', schema=None, recreate='never') as batch_op:
        batch_op.add_column(sa.Column('edad', sa.Integer(), nullable=True))
    with op.batch_alter_table('eventos', schema=None, recreate='never') as batch_op:
        batch_op.add_column(sa.Column('apelacion_motivo', sa.Text(), nullable=True))
        batch_op.add_column(sa.Column('apelacion_en', sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    with op.batch_alter_table('eventos', schema=None, recreate='never') as batch_op:
        batch_op.drop_column('apelacion_en')
        batch_op.drop_column('apelacion_motivo')
    with op.batch_alter_table('usuarios', schema=None, recreate='never') as batch_op:
        batch_op.drop_column('edad')
