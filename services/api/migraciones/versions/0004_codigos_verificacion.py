"""Códigos de verificación del teléfono (login por WhatsApp/Telegram, alta de publicadores): tabla
`codigos_verificacion` con el HMAC del código, caducidad, intentos fallidos y si ya se ha usado.

Revision ID: 0004
Revises: 0003
Create Date: 2026-11-21 12:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0004'
down_revision = '0003'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        'codigos_verificacion',
        sa.Column('id', sa.String(length=36), nullable=False),
        sa.Column('telefono', sa.String(length=16), nullable=False),
        sa.Column('codigo_hash', sa.String(length=64), nullable=False),
        sa.Column('expira_en', sa.DateTime(timezone=True), nullable=False),
        sa.Column('intentos', sa.Integer(), nullable=False),
        sa.Column('usado', sa.Boolean(), nullable=False),
        sa.Column('creado_en', sa.DateTime(timezone=True), nullable=False),
        sa.PrimaryKeyConstraint('id', name=op.f('pk_codigos_verificacion')),
    )
    with op.batch_alter_table('codigos_verificacion', schema=None) as batch_op:
        batch_op.create_index(batch_op.f('ix_codigos_verificacion_telefono'), ['telefono'], unique=False)


def downgrade() -> None:
    with op.batch_alter_table('codigos_verificacion', schema=None) as batch_op:
        batch_op.drop_index(batch_op.f('ix_codigos_verificacion_telefono'))
    op.drop_table('codigos_verificacion')
