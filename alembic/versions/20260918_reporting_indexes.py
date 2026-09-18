"""Add indexes for CU16 and CU21-CU24 reporting queries."""
from alembic import op

revision = "20260918_reporting_indexes"
down_revision = "20260918_cu19_cu20"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_index("ix_venta_fecha_cliente", "venta", ["fecha", "id_cliente"])
    op.create_index("ix_movimiento_inventario_fecha", "movimiento_inventario", ["fecha"])
    op.create_index("ix_inventario_stock_minimo", "inventario", ["stock_actual", "stock_minimo"])


def downgrade() -> None:
    op.drop_index("ix_inventario_stock_minimo", table_name="inventario")
    op.drop_index("ix_movimiento_inventario_fecha", table_name="movimiento_inventario")
    op.drop_index("ix_venta_fecha_cliente", table_name="venta")
