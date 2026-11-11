"""add_audio_requirements_columns

Revision ID: 7c1e89f2a013
Revises: 4bcaa6a42279
Create Date: 2026-10-24 19:40:00.000000
"""
from typing import Sequence, Union
from alembic import op
import sqlalchemy as sa

revision: str = '7c1e89f2a013'
down_revision: Union[str, Sequence[str], None] = '4bcaa6a42279'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1. Producto: precio al por mayor, cantidad mínima, material, color secundario, liquidación
    op.add_column('producto', sa.Column('precio_mayor', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('producto', sa.Column('cantidad_min_mayor', sa.Integer(), nullable=True, server_default='3'))
    op.add_column('producto', sa.Column('material', sa.String(length=100), nullable=True))
    op.add_column('producto', sa.Column('color_secundario', sa.String(length=50), nullable=True))
    op.add_column('producto', sa.Column('es_liquidacion', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('producto', sa.Column('porcentaje_descuento', sa.Numeric(precision=5, scale=2), nullable=True, server_default='0.0'))

    # 2. Venta: tracking y confirmación de entrega
    op.add_column('venta', sa.Column('estado_entrega', sa.String(length=30), nullable=False, server_default='PAGADO'))
    op.add_column('venta', sa.Column('notas_cliente', sa.Text(), nullable=True))
    op.add_column('venta', sa.Column('fecha_entrega', sa.DateTime(timezone=True), nullable=True))

    # 3. Cambio de prenda: notificaciones push, saldos y retención administrativa
    op.add_column('cambio_prenda', sa.Column('estado_pago_diferencia', sa.String(length=30), nullable=False, server_default='PAGADO'))
    op.add_column('cambio_prenda', sa.Column('notificacion_push_enviada', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('cambio_prenda', sa.Column('texto_notificacion_push', sa.Text(), nullable=True))
    op.add_column('cambio_prenda', sa.Column('monto_reembolso', sa.Numeric(precision=12, scale=2), nullable=True))
    op.add_column('cambio_prenda', sa.Column('estado_reembolso', sa.String(length=30), nullable=True))


def downgrade() -> None:
    # Cambio prenda
    op.drop_column('cambio_prenda', 'estado_reembolso')
    op.drop_column('cambio_prenda', 'monto_reembolso')
    op.drop_column('cambio_prenda', 'texto_notificacion_push')
    op.drop_column('cambio_prenda', 'notificacion_push_enviada')
    op.drop_column('cambio_prenda', 'estado_pago_diferencia')

    # Venta
    op.drop_column('venta', 'fecha_entrega')
    op.drop_column('venta', 'notas_cliente')
    op.drop_column('venta', 'estado_entrega')

    # Producto
    op.drop_column('producto', 'porcentaje_descuento')
    op.drop_column('producto', 'es_liquidacion')
    op.drop_column('producto', 'color_secundario')
    op.drop_column('producto', 'material')
    op.drop_column('producto', 'cantidad_min_mayor')
    op.drop_column('producto', 'precio_mayor')
