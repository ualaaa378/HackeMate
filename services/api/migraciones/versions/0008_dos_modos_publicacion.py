"""Solo dos modos de publicación: los publicadores con el nivel 1 obsoleto (semiautomático) pasan a 0 (a mano).

Solo datos: el CHECK `nivel_confianza IN (0, 1, 2)` se queda igual (el enum del contrato no se borra después de CP0).
No tiene vuelta atrás exacta: el downgrade no sabe qué publicadores eran nivel 1 y no cambia nada.

Revision ID: 0008
Revises: 0007
Create Date: 2026-11-21 11:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0008'
down_revision = '0007'
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.execute(sa.text("UPDATE publicadores SET nivel_confianza = 0 WHERE nivel_confianza = 1"))


def downgrade() -> None:
    pass
