"""align recommendation tables with the data dictionary (CU18)

Revision ID: 20260919_cu18_dictionary
Revises: 20260918_reporting_indexes
Create Date: 2026-09-19

El diccionario de datos del documento define:
- detalle_recomendacion.puntuacion numeric(5,2) y motivo varchar(255)
- recomendacion.estado -> Visto / Pendiente / Descartado (30 caracteres)

La implementación usaba numeric(6,2), text y el estado fijo "activa".
"""
from alembic import op
import sqlalchemy as sa

revision = "20260919_cu18_dictionary"
down_revision = "20260918_reporting_indexes"
branch_labels = None
depends_on = None


def upgrade() -> None:
    with op.batch_alter_table("recomendacion_detalle") as batch:
        batch.alter_column(
            "puntuacion",
            existing_type=sa.Numeric(6, 2),
            type_=sa.Numeric(5, 2),
            existing_nullable=False,
        )
        batch.alter_column(
            "motivo",
            existing_type=sa.Text(),
            type_=sa.String(255),
            existing_nullable=True,
        )
    with op.batch_alter_table("recomendacion") as batch:
        batch.alter_column(
            "estado",
            existing_type=sa.String(20),
            type_=sa.String(30),
            existing_nullable=False,
            server_default="pendiente",
        )
    op.execute("UPDATE recomendacion SET estado = 'pendiente' WHERE estado = 'activa'")


def downgrade() -> None:
    op.execute("UPDATE recomendacion SET estado = 'activa' WHERE estado = 'pendiente'")
    with op.batch_alter_table("recomendacion") as batch:
        batch.alter_column(
            "estado",
            existing_type=sa.String(30),
            type_=sa.String(20),
            existing_nullable=False,
            server_default="activa",
        )
    with op.batch_alter_table("recomendacion_detalle") as batch:
        batch.alter_column(
            "motivo",
            existing_type=sa.String(255),
            type_=sa.Text(),
            existing_nullable=True,
        )
        batch.alter_column(
            "puntuacion",
            existing_type=sa.Numeric(5, 2),
            type_=sa.Numeric(6, 2),
            existing_nullable=False,
        )
