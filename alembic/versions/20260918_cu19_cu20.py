"""add chatbot, collections and promotions (CU19-CU20)

Revision ID: 20260918_cu19_cu20
Revises: 20260917_missing_use_cases
"""
from alembic import op
import sqlalchemy as sa

revision = "20260918_cu19_cu20"
down_revision = "20260917_missing_use_cases"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "conversacion_chatbot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("id_usuario", sa.Integer(), sa.ForeignKey("usuario.id", ondelete="CASCADE"), nullable=False),
        sa.Column("titulo", sa.String(150)),
        sa.Column("contexto", sa.JSON()),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("fecha_actualizacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_conversacion_chatbot_id_usuario", "conversacion_chatbot", ["id_usuario"])
    op.create_table(
        "mensaje_chatbot",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("id_conversacion", sa.Integer(), sa.ForeignKey("conversacion_chatbot.id", ondelete="CASCADE"), nullable=False),
        sa.Column("rol", sa.String(20), nullable=False),
        sa.Column("contenido", sa.Text(), nullable=False),
        sa.Column("contexto", sa.JSON()),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_mensaje_chatbot_id_conversacion", "mensaje_chatbot", ["id_conversacion"])
    op.create_table(
        "coleccion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("descripcion", sa.Text()),
        sa.Column("estado", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column("fecha_creacion", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_index("ix_coleccion_nombre", "coleccion", ["nombre"])
    op.create_table(
        "promocion",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("nombre", sa.String(150), nullable=False),
        sa.Column("descripcion", sa.Text()),
        sa.Column("tipo_descuento", sa.String(20), nullable=False, server_default="percentage"),
        sa.Column("valor_descuento", sa.Numeric(12, 2), nullable=False),
        sa.Column("fecha_inicio", sa.Date()),
        sa.Column("fecha_fin", sa.Date()),
        sa.Column("estado", sa.Boolean(), nullable=False, server_default=sa.true()),
    )
    for table, col in (("promocion", "nombre"), ("promocion", "estado"), ("promocion", "fecha_inicio"), ("promocion", "fecha_fin")):
        op.create_index(f"ix_{table}_{col}", table, [col])
    op.create_table(
        "coleccion_producto",
        sa.Column("id_coleccion", sa.Integer(), sa.ForeignKey("coleccion.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("id_producto", sa.Integer(), sa.ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "promocion_producto",
        sa.Column("id_promocion", sa.Integer(), sa.ForeignKey("promocion.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("id_producto", sa.Integer(), sa.ForeignKey("producto.id", ondelete="CASCADE"), primary_key=True),
    )


def downgrade() -> None:
    op.drop_table("promocion_producto")
    op.drop_table("coleccion_producto")
    for table, col in (("promocion", "fecha_fin"), ("promocion", "fecha_inicio"), ("promocion", "estado"), ("promocion", "nombre")):
        op.drop_index(f"ix_{table}_{col}", table_name=table)
    op.drop_table("promocion")
    op.drop_index("ix_coleccion_nombre", table_name="coleccion")
    op.drop_table("coleccion")
    op.drop_index("ix_mensaje_chatbot_id_conversacion", table_name="mensaje_chatbot")
    op.drop_table("mensaje_chatbot")
    op.drop_index("ix_conversacion_chatbot_id_usuario", table_name="conversacion_chatbot")
    op.drop_table("conversacion_chatbot")
