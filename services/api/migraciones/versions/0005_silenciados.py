"""Silenciados en el chat del evento (H3.4): tabla `silenciados` con PK (evento_id, usuario_id).

Revision ID: 0005
Revises: 0004
Create Date: 2026-11-21 18:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0005'
down_revision = '0004'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'silenciados',
        sa.Column('evento_id', sa.String(length=36), nullable=False),
        sa.Column('usuario_id', sa.String(length=36), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('por', sa.String(length=120), nullable=True),
        sa.ForeignKeyConstraint(['evento_id'], ['eventos.id'], name=op.f('fk_silenciados_evento_id_eventos'), ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_silenciados_usuario_id_usuarios'), ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('evento_id', 'usuario_id', name=op.f('pk_silenciados')),
    )


def downgrade() -> None:
    op.drop_table('silenciados')
