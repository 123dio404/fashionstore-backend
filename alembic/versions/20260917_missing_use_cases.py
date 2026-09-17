"""add catalog 3d metadata and missing business use-case tables

Revision ID: 20260917_missing_use_cases
Revises: c7d4e5f6a7b8
"""
from alembic import op
import sqlalchemy as sa

revision = "20260917_missing_use_cases"
down_revision = "c7d4e5f6a7b8"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("producto", sa.Column("id_temporada", sa.Integer(), nullable=True))
    op.create_foreign_key("fk_producto_temporada", "producto", "temporada", ["id_temporada"], ["id"], ondelete="SET NULL")
    op.add_column("producto", sa.Column("modelo_3d_url", sa.String(500), nullable=True))
    op.add_column("producto", sa.Column("modelo_3d_formato", sa.String(10), nullable=True))
    op.add_column("producto", sa.Column("metadatos_tecnicos", sa.Text(), nullable=True))
    op.add_column("temporada", sa.Column("fecha_inicio", sa.Date(), nullable=True))
    op.add_column("temporada", sa.Column("fecha_fin", sa.Date(), nullable=True))


def downgrade() -> None:
    op.drop_column("temporada", "fecha_fin")
    op.drop_column("temporada", "fecha_inicio")
    op.drop_column("producto", "metadatos_tecnicos")
    op.drop_column("producto", "modelo_3d_formato")
    op.drop_column("producto", "modelo_3d_url")
    op.drop_constraint("fk_producto_temporada", "producto", type_="foreignkey")
    op.drop_column("producto", "id_temporada")
