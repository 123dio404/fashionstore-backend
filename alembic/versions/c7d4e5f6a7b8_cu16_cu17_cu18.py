"""add virtual fitting, recommendations and analytics support

Revision ID: c7d4e5f6a7b8
Revises: c14_commerce_workflows
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "c7d4e5f6a7b8"
down_revision: Union[str, Sequence[str], None] = "c14_commerce_workflows"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "sesion_prueba_virtual",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("modelo_url", sa.String(500)),
        sa.Column("modelo_formato", sa.String(10)),
        sa.Column("metadatos_modelo", sa.JSON()),
        sa.Column("estado", sa.String(20), nullable=False, server_default="pendiente"),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_sesion_prueba_virtual_id_usuario", "sesion_prueba_virtual", ["id_usuario"])
    op.create_index("ix_sesion_prueba_virtual_estado", "sesion_prueba_virtual", ["estado"])
    op.create_table(
        "resultado_prueba_virtual",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_sesion", sa.Integer(), sa.ForeignKey("sesion_prueba_virtual.id", ondelete="CASCADE"), nullable=False),
        sa.Column("id_variante", sa.Integer(), sa.ForeignKey("producto_variante.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("id_talla", sa.Integer(), sa.ForeignKey("tallas.id", ondelete="RESTRICT")),
        sa.Column("resultado_url", sa.String(500)),
        sa.Column("confianza", sa.Numeric(5, 2), nullable=False),
        sa.Column("metadatos", sa.JSON()),
    )
    op.create_index("ix_resultado_prueba_virtual_id_sesion", "resultado_prueba_virtual", ["id_sesion"])
    op.create_index("ix_resultado_prueba_virtual_id_variante", "resultado_prueba_virtual", ["id_variante"])
    op.create_table(
        "preferencia_usuario",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("id_categoria", sa.Integer(), sa.ForeignKey("categoria.id", ondelete="SET NULL")),
        sa.Column("marca_preferida", sa.String(100)),
        sa.Column("colores_preferidos", sa.JSON()),
        sa.Column("tallas_preferidas", sa.JSON()),
        sa.Column("precio_minimo", sa.Numeric(12, 2)),
        sa.Column("precio_maximo", sa.Numeric(12, 2)),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
    )
    op.create_index("ix_preferencia_usuario_id_usuario", "preferencia_usuario", ["id_usuario"])
    op.create_table(
        "recomendacion",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("tipo", sa.String(50), nullable=False),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), nullable=False, server_default=sa.func.now()),
        sa.Column("estado", sa.String(20), nullable=False, server_default="activa"),
    )
    op.create_index("ix_recomendacion_id_usuario", "recomendacion", ["id_usuario"])
    op.create_table(
        "recomendacion_detalle",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("id_recomendacion", sa.Integer(), sa.ForeignKey("recomendacion.id", ondelete="CASCADE"), nullable=False),
        sa.Column("id_producto", sa.Integer(), sa.ForeignKey("producto.id", ondelete="CASCADE"), nullable=False),
        sa.Column("puntuacion", sa.Numeric(6, 2), nullable=False),
        sa.Column("motivo", sa.Text()),
        sa.UniqueConstraint("id_recomendacion", "id_producto", name="uq_recomendacion_producto"),
    )
    op.create_index("ix_recomendacion_detalle_id_producto", "recomendacion_detalle", ["id_producto"])


def downgrade() -> None:
    op.drop_table("recomendacion_detalle")
    op.drop_index("ix_recomendacion_id_usuario", table_name="recomendacion")
    op.drop_table("recomendacion")
    op.drop_index("ix_preferencia_usuario_id_usuario", table_name="preferencia_usuario")
    op.drop_table("preferencia_usuario")
    op.drop_index("ix_resultado_prueba_virtual_id_variante", table_name="resultado_prueba_virtual")
    op.drop_index("ix_resultado_prueba_virtual_id_sesion", table_name="resultado_prueba_virtual")
    op.drop_table("resultado_prueba_virtual")
    op.drop_index("ix_sesion_prueba_virtual_estado", table_name="sesion_prueba_virtual")
    op.drop_index("ix_sesion_prueba_virtual_id_usuario", table_name="sesion_prueba_virtual")
    op.drop_table("sesion_prueba_virtual")
