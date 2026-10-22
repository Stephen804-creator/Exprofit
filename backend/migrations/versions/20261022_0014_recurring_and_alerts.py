# ruff: noqa: E501
"""Add expected recurring payments and persistent financial alerts."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0014"
down_revision: str | None = "20261022_0013"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "recurring_transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(8), nullable=False),
        sa.Column("description", sa.String(160), nullable=False),
        sa.Column("category", sa.String(80), nullable=True),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("interval", sa.String(8), nullable=False),
        sa.Column("start_date", sa.Date(), nullable=False),
        sa.Column("next_due_date", sa.Date(), nullable=False),
        sa.Column("end_date", sa.Date(), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("direction IN ('income', 'expense')", name="ck_recurring_direction"),
        sa.CheckConstraint("interval IN ('weekly', 'monthly', 'yearly')", name="ck_recurring_interval"),
        sa.CheckConstraint("amount > 0", name="ck_recurring_amount_positive"),
        sa.CheckConstraint("currency_code = upper(currency_code) AND length(currency_code) = 3", name="ck_recurring_currency"),
        sa.CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_recurring_date_order"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_recurring_business_active_due", "recurring_transactions", ["business_id", "is_active", "next_due_date"])
    op.create_table(
        "financial_alerts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("alert_key", sa.String(180), nullable=False),
        sa.Column("kind", sa.String(40), nullable=False),
        sa.Column("severity", sa.String(12), nullable=False),
        sa.Column("title", sa.String(180), nullable=False),
        sa.Column("message", sa.Text(), nullable=False),
        sa.Column("status", sa.String(12), server_default="unread", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("acknowledged_at", sa.DateTime(timezone=True), nullable=True),
        sa.CheckConstraint("severity IN ('info', 'warning', 'critical')", name="ck_financial_alert_severity"),
        sa.CheckConstraint("status IN ('unread', 'read', 'dismissed')", name="ck_financial_alert_status"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "alert_key", name="uq_financial_alert_business_key"),
    )
    op.create_index("ix_financial_alert_business_status", "financial_alerts", ["business_id", "status", "created_at"])


def downgrade() -> None:
    op.drop_index("ix_financial_alert_business_status", table_name="financial_alerts")
    op.drop_table("financial_alerts")
    op.drop_index("ix_recurring_business_active_due", table_name="recurring_transactions")
    op.drop_table("recurring_transactions")
