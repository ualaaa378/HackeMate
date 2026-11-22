"""«Me gusta» en los planes: tabla `me_gusta` (uno por usuario y plan).

Revision ID: 0013
Revises: 0012
Create Date: 2026-11-22 10:05:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0013'
down_revision = '0012'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'me_gusta',
        sa.Column('evento_id', sa.String(length=36), nullable=False),
        sa.Column('usuario_id', sa.String(length=36), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.ForeignKeyConstraint(['evento_id'], ['eventos.id'], name=op.f('fk_me_gusta_evento_id_eventos'),
                                ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['usuario_id'], ['usuarios.id'], name=op.f('fk_me_gusta_usuario_id_usuarios'),
                                ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('evento_id', 'usuario_id', name=op.f('pk_me_gusta')),
    )


def downgrade() -> None:
    op.drop_table('me_gusta')
