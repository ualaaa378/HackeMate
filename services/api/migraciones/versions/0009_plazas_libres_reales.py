"""N6: plazas libres reales. `plazas_libres = plazas_totales - inscritos confirmados en la plataforma` (web y bot).

Los números de los fixtures (inscritos inventados) dejan de contar. Solo planes con aforo que no han terminado: los
`finalizado` guardan su ocupación histórica para las estadísticas. Solo datos; el seed hace lo mismo al cargar
(`app.inscripciones.recalcular_plazas`). No tiene vuelta atrás: el downgrade no sabe qué número había antes.

Revision ID: 0009
Revises: 0008
Create Date: 2026-11-21 18:00:00
"""

import sqlalchemy as sa
from alembic import op

revision = '0009'
down_revision = '0008'
branch_labels = None
depends_on = None

OCUPADAS = ("(SELECT COALESCE(SUM(i.plazas), 0) FROM inscripciones i "
            "WHERE i.evento_id = eventos.id AND i.estado = 'confirmada')")


def upgrade() -> None:
    op.execute(sa.text(
        f"UPDATE eventos SET plazas_libres = CASE WHEN plazas_totales - {OCUPADAS} < 0 THEN 0 "
        f"ELSE plazas_totales - {OCUPADAS} END "
        "WHERE plazas_totales IS NOT NULL AND estado <> 'finalizado'"
    ))


def downgrade() -> None:
    pass
