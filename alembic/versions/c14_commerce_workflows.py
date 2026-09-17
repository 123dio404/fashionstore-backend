"""CU11-CU14 commerce workflow fields and reservation lookup index."""
from alembic import op
import sqlalchemy as sa

revision = "c14_commerce_workflows"
down_revision = "b5615bb92135"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("reserva", sa.Column("probador", sa.Integer(), nullable=True))
    op.add_column("reserva", sa.Column("fecha_preparacion", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reserva", sa.Column("fecha_asignacion", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reserva", sa.Column("fecha_checkout", sa.DateTime(timezone=True), nullable=True))
    op.add_column("reserva", sa.Column("fecha_devolucion", sa.DateTime(timezone=True), nullable=True))
    op.create_index(
        "ix_reserva_overlap_lookup",
        "reserva",
        ["id_sucursal", "fecha_reserva", "hora_reserva", "estado"],
    )


def downgrade() -> None:
    op.drop_index("ix_reserva_overlap_lookup", table_name="reserva")
    for column in ("fecha_devolucion", "fecha_checkout", "fecha_asignacion", "fecha_preparacion", "probador"):
        op.drop_column("reserva", column)
