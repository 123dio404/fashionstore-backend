"""extend schema with commerce, recommendation and chat entities

Revision ID: 8c2f4a1d9b7e
Revises: f79755b6e174
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "8c2f4a1d9b7e"
down_revision: Union[str, Sequence[str], None] = "f79755b6e174"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def _id():
    return sa.Column("id", sa.Uuid(), primary_key=True)


def upgrade() -> None:
    op.create_table(
        "roles",
        _id(),
        sa.Column("name", sa.String(80), nullable=False, unique=True),
    )
    op.create_table(
        "user_roles",
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("role_id", sa.Uuid(), sa.ForeignKey("roles.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "branch_hours",
        _id(),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id", ondelete="CASCADE"), nullable=False),
        sa.Column("weekday", sa.SmallInteger(), nullable=False),
        sa.Column("start_time", sa.Time(), nullable=False),
        sa.Column("end_time", sa.Time(), nullable=False),
        sa.CheckConstraint("weekday between 1 and 7", name="ck_branch_hours_weekday"),
        sa.CheckConstraint("end_time > start_time", name="ck_branch_hours_time_range"),
        sa.UniqueConstraint("branch_id", "weekday", name="uq_branch_hours_branch_weekday"),
    )
    op.create_table(
        "product_images",
        _id(),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("image_url", sa.String(500), nullable=False),
    )
    op.create_table(
        "garment_measurements",
        _id(),
        sa.Column("stock_id", sa.Uuid(), sa.ForeignKey("stocks.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("chest", sa.Numeric(8, 2)),
        sa.Column("waist", sa.Numeric(8, 2)),
        sa.Column("hip", sa.Numeric(8, 2)),
        sa.Column("length", sa.Numeric(8, 2)),
        sa.Column("shoulder_width", sa.Numeric(8, 2)),
        sa.Column("status", sa.String(30), nullable=False, server_default="activo"),
    )
    op.create_table(
        "product_suppliers",
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("supplier_id", sa.Uuid(), sa.ForeignKey("suppliers.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("purchase_price", sa.Numeric(12, 2), nullable=False),
    )
    op.create_table(
        "carts",
        _id(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="activo"),
    )
    op.create_table(
        "cart_items",
        _id(),
        sa.Column("cart_id", sa.Uuid(), sa.ForeignKey("carts.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", sa.Uuid(), sa.ForeignKey("stocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("price", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_cart_items_quantity"),
    )
    op.create_table(
        "sales",
        _id(),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("sale_date", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("total", sa.Numeric(12, 2), nullable=False),
        sa.Column("sale_type", sa.String(40), nullable=False),
    )
    op.create_table(
        "sale_items",
        _id(),
        sa.Column("sale_id", sa.Uuid(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", sa.Uuid(), sa.ForeignKey("stocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
        sa.Column("unit_price", sa.Numeric(12, 2), nullable=False),
        sa.CheckConstraint("quantity > 0", name="ck_sale_items_quantity"),
    )
    op.create_table(
        "payments",
        _id(),
        sa.Column("order_id", sa.Uuid(), sa.ForeignKey("sales.id", ondelete="CASCADE"), nullable=False),
        sa.Column("amount", sa.Numeric(12, 2), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
        sa.Column("paid_at", sa.DateTime(timezone=True)),
        sa.Column("reference", sa.String(150)),
    )
    op.create_table(
        "reservations",
        _id(),
        sa.Column("client_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("branch_id", sa.Uuid(), sa.ForeignKey("branches.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("reservation_date", sa.Date(), nullable=False),
        sa.Column("reservation_time", sa.Time(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False, server_default="pendiente"),
    )
    op.create_table(
        "reservation_items",
        _id(),
        sa.Column("reservation_id", sa.Uuid(), sa.ForeignKey("reservations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("stock_id", sa.Uuid(), sa.ForeignKey("stocks.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("quantity", sa.Integer(), nullable=False),
    )
    op.create_table(
        "body_profiles",
        _id(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False, unique=True),
        sa.Column("height", sa.Numeric(8, 2)),
        sa.Column("weight", sa.Numeric(8, 2)),
        sa.Column("chest", sa.Numeric(8, 2)),
        sa.Column("waist", sa.Numeric(8, 2)),
        sa.Column("hip", sa.Numeric(8, 2)),
        sa.Column("leg_length", sa.Numeric(8, 2)),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "size_recommendations",
        _id(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), nullable=False),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
        sa.Column("result", sa.String(80), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )
    op.create_table(
        "fitting_sessions",
        _id(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_table(
        "fitting_results",
        _id(),
        sa.Column("session_id", sa.Uuid(), sa.ForeignKey("fitting_sessions.id", ondelete="CASCADE"), nullable=False),
        sa.Column("variant_id", sa.Uuid(), sa.ForeignKey("product_variants.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("size_id", sa.Uuid(), sa.ForeignKey("sizes.id", ondelete="RESTRICT"), nullable=False),
        sa.Column("result_url", sa.String(500)),
        sa.Column("confidence", sa.Numeric(5, 2), nullable=False),
    )
    op.create_table(
        "recommendations",
        _id(),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("recommendation_type", sa.String(50), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_table(
        "recommendation_items",
        sa.Column("recommendation_id", sa.Uuid(), sa.ForeignKey("recommendations.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("score", sa.Numeric(5, 2), nullable=False),
        sa.Column("reason", sa.Text()),
    )
    op.create_table(
        "promotions",
        _id(),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("discount_type", sa.String(30), nullable=False),
        sa.Column("discount_value", sa.Numeric(12, 2), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=False),
        sa.Column("status", sa.String(30), nullable=False),
    )
    op.create_table(
        "product_promotions",
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("promotion_id", sa.Uuid(), sa.ForeignKey("promotions.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "collections",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("name", sa.String(150), nullable=False),
        sa.Column("description", sa.Text()),
        sa.Column("start_date", sa.Date()),
        sa.Column("end_date", sa.Date()),
    )
    op.create_table(
        "collection_products",
        sa.Column("collection_id", sa.Uuid(), sa.ForeignKey("collections.id", ondelete="CASCADE"), primary_key=True),
        sa.Column("product_id", sa.Uuid(), sa.ForeignKey("products.id", ondelete="CASCADE"), primary_key=True),
    )
    op.create_table(
        "chat_conversations",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("user_id", sa.Uuid(), sa.ForeignKey("users.id", ondelete="CASCADE"), nullable=False),
        sa.Column("started_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("ended_at", sa.DateTime(timezone=True)),
    )
    op.create_table(
        "chat_messages",
        sa.Column("id", sa.Uuid(), primary_key=True),
        sa.Column("conversation_id", sa.Uuid(), sa.ForeignKey("chat_conversations.id", ondelete="CASCADE"), nullable=False),
        sa.Column("sender", sa.String(30), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
    )


def downgrade() -> None:
    for table in (
        "chat_messages", "chat_conversations", "collection_products", "collections",
        "product_promotions", "promotions", "recommendation_items", "recommendations",
        "fitting_results", "fitting_sessions", "size_recommendations", "body_profiles",
        "reservation_items", "reservations", "payments", "sale_items", "sales",
        "cart_items", "carts", "product_suppliers", "garment_measurements",
        "product_images", "branch_hours", "user_roles", "roles",
    ):
        op.drop_table(table)