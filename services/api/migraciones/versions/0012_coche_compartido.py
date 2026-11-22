"""Compartir coche (idea 6): tabla `coche_compartido` con la respuesta de cada vecino por plan.

Revision ID: 0012
Revises: 0011
Create Date: 2026-11-22 03:40:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0012'
down_revision = '0011'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'coche_compartido',
        sa.Column('evento_id', sa.String(length=36), nullable=False),
        sa.Column('usuario_id', sa.String(length=36), nullable=False),
        sa.Column('respuesta', sa.String(length=10), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('actualizado_en', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['evento_id'], ['eventos.id'], name=op.f('fk_coche_compartido_evento_id_eventos'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_coche_compartido_usuario_id_usuarios'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('evento_id', 'usuario_id', name=op.f('pk_coche_compartido')),
    )


def downgrade() -> None:
    op.drop_table('coche_compartido')
