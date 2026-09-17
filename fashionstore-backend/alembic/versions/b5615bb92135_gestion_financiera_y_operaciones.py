"""gestión financiera y operaciones: cuotas/expensas, pagos, multas, instalaciones, reservas y mantenimiento

Revision ID: b5615bb92135
Revises: 8c2f4a1d9b7e
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b5615bb92135"
down_revision: Union[str, Sequence[str], None] = "8c2f4a1d9b7e"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id():
    return sa.Column("id", sa.Uuid(), primary_key=True)


def _timestamps(updated: bool = False) -> list[sa.Column]:
    cols = [sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False)]
    if updated:
        cols.append(sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False))
    return cols


def upgrade() -> None:
    op.create_table(
        "fees",
        _id(),
        sa.Column("fee_type", sa.Enum("cuota", "expensa", name="fee_type", native_enum=False), nullable=False),
        sa.Column("period", sa.String(7), nullable=False),
        sa.Column("concept", sa.String(200), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("due_date", sa.DateTime(timezone=True), nullable=True),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        *_timestamps(updated=True),
        sa.CheckConstraint("amount > 0", name="ck_fee_amount_positive"),
    )
    op.create_index("ix_fees_fee_type", "fees", ["fee_type"])
    op.create_index("ix_fees_period", "fees", ["period"])

    op.create_table(
        "fee_payments",
        _id(),
        sa.Column("fee_id", sa.Uuid(), sa.ForeignKey("fees.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("method", sa.Enum("tarjeta", "transferencia", "efectivo", name="payment_method", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("pendiente", "completado", "fallido", "reembolsado", name="payment_status", native_enum=False), nullable=False),
        sa.Column("reference", sa.String(100), nullable=True),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("reference", name="uq_fee_payments_reference"),
    )
    op.create_index("ix_fee_payments_fee_id", "fee_payments", ["fee_id"])
    op.create_index("ix_fee_payments_user_id", "fee_payments", ["user_id"])
    op.create_index("ix_fee_payments_status", "fee_payments", ["status"])

    op.create_table(
        "fines",
        _id(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("fee_id", sa.Uuid(), sa.ForeignKey("fees.id", ondelete="SET NULL"), nullable=True),
        sa.Column("reason", sa.String(255), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.Enum("pendiente", "pagada", "anulada", name="fine_status", native_enum=False), nullable=False),
        sa.Column("issued_at", sa.DateTime(timezone=True), server_default=sa.text("CURRENT_TIMESTAMP"), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("amount > 0", name="ck_fine_amount_positive"),
    )
    op.create_index("ix_fines_user_id", "fines", ["user_id"])
    op.create_index("ix_fines_fee_id", "fines", ["fee_id"])
    op.create_index("ix_fines_status", "fines", ["status"])

    op.create_table(
        "facilities",
        _id(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("location", sa.String(150), nullable=True),
        sa.Column("capacity", sa.Integer(), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False),
        sa.Column("open_time", sa.Time(), nullable=True),
        sa.Column("close_time", sa.Time(), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        *_timestamps(updated=True),
        sa.CheckConstraint("capacity > 0", name="ck_facility_capacity_positive"),
    )
    op.create_index("ix_facilities_name", "facilities", ["name"], unique=True)

    op.create_table(
        "facility_reservations",
        _id(),
        sa.Column("facility_id", sa.Uuid(), sa.ForeignKey("facilities.id", ondelete="CASCADE"), nullable=False),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.Column("status", sa.Enum("pendiente", "confirmada", "cancelada", "completada", name="reservation_status", native_enum=False), nullable=False),
        sa.Column("notes", sa.Text(), nullable=True),
        *_timestamps(),
        sa.CheckConstraint("end_time > start_time", name="ck_facility_reservation_time_range"),
    )
    op.create_index("ix_facility_reservations_facility_id", "facility_reservations", ["facility_id"])
    op.create_index("ix_facility_reservations_user_id", "facility_reservations", ["user_id"])
    op.create_index("ix_facility_reservations_date", "facility_reservations", ["date"])
    op.create_index("ix_facility_reservations_status", "facility_reservations", ["status"])

    op.create_table(
        "maintenance_tasks",
        _id(),
        sa.Column("title", sa.String(200), nullable=False),
        sa.Column("description", sa.Text(), nullable=True),
        sa.Column("facility_id", sa.Uuid(), sa.ForeignKey("facilities.id", ondelete="SET NULL"), nullable=True),
        sa.Column("assignee_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="SET NULL"), nullable=True),
        sa.Column("priority", sa.Enum("baja", "media", "alta", "critica", name="priority", native_enum=False), nullable=False),
        sa.Column("status", sa.Enum("pendiente", "en_progreso", "completada", "cancelada", name="task_status", native_enum=False), nullable=False),
        sa.Column("scheduled_date", sa.Date(), nullable=True),
        sa.Column("completed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("created_by_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        *_timestamps(updated=True),
    )
    op.create_index("ix_maintenance_tasks_facility_id", "maintenance_tasks", ["facility_id"])
    op.create_index("ix_maintenance_tasks_assignee_id", "maintenance_tasks", ["assignee_id"])
    op.create_index("ix_maintenance_tasks_priority", "maintenance_tasks", ["priority"])
    op.create_index("ix_maintenance_tasks_status", "maintenance_tasks", ["status"])


def downgrade() -> None:
    op.drop_table("maintenance_tasks")
    op.drop_table("facility_reservations")
    op.drop_table("facilities")
    op.drop_table("fines")
    op.drop_table("fee_payments")
    op.drop_table("fees")