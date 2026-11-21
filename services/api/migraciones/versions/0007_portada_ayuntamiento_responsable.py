"""Frase de portada y datos para el ayuntamiento en `eventos`; responsable e identidad verificada en `publicadores`.

- `eventos.frase_portada` (String 90) y `eventos.datos_ayuntamiento` (JSON, privado), opcionales.
- `eventos.imagen_url` pasa de VARCHAR(500) a Text (admite data URL de imagen de ~1,5 MB). Solo en PostgreSQL:
  SQLite no limita la longitud de VARCHAR, y cambiar el tipo obligaría a recrear `eventos`, lo que falla con
  claves foráneas activas en una base con datos (ver el modelo, que usa la variante VARCHAR(500) en SQLite).
- `publicadores.responsable` (JSON, privado) y `publicadores.identidad_verificada` (bool, false por defecto).

`recreate="never"`: en SQLite se usan ALTER TABLE ADD/DROP COLUMN directos y nunca se recrean tablas
(`publicadores` y `eventos` tienen tablas hijas; DROP TABLE fallaría con PRAGMA foreign_keys=ON).

Revision ID: 0007
Revises: 0006
Create Date: 2026-11-21 14:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0007'
down_revision = '0006'
branch_labels = None
depends_on = None


def _es_sqlite() -> bool:
    return op.get_bind().dialect.name == 'sqlite'


def upgrade() -> None:
    with op.batch_alter_table('eventos', schema=None, recreate='never') as batch_op:
        batch_op.add_column(sa.Column('frase_portada', sa.String(length=90), nullable=True))
        batch_op.add_column(sa.Column('datos_ayuntamiento', sa.JSON(), nullable=True))
    if not _es_sqlite():
        op.alter_column('eventos', 'imagen_url', existing_type=sa.String(length=500), type_=sa.Text(),
                        existing_nullable=True)
    with op.batch_alter_table('publicadores', schema=None, recreate='never') as batch_op:
        batch_op.add_column(sa.Column('responsable', sa.JSON(), nullable=True))
        # Texto constante ('0'): vale como false en SQLite y en PostgreSQL y no obliga a recrear la tabla.
        batch_op.add_column(sa.Column('identidad_verificada', sa.Boolean(), server_default='0', nullable=False))


def downgrade() -> None:
    with op.batch_alter_table('publicadores', schema=None, recreate='never') as batch_op:
        batch_op.drop_column('identidad_verificada')
        batch_op.drop_column('responsable')
    if not _es_sqlite():
        # Las imágenes que no caben en VARCHAR(500) (data URL) se pierden al deshacer.
        op.execute(sa.text("UPDATE eventos SET imagen_url = NULL WHERE length(imagen_url) > 500"))
        op.alter_column('eventos', 'imagen_url', existing_type=sa.Text(), type_=sa.String(length=500),
                        existing_nullable=True)
    with op.batch_alter_table('eventos', schema=None, recreate='never') as batch_op:
        batch_op.drop_column('datos_ayuntamiento')
        batch_op.drop_column('frase_portada')
