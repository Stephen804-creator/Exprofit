"""Create the transactions table for business-scoped ledger entries."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0002"
down_revision: str | None = "20261018_0001"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "transactions",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("direction", sa.String(length=8), nullable=False),
        sa.Column("status", sa.String(length=8), server_default="draft", nullable=False),
        sa.Column("amount", sa.Numeric(precision=14, scale=2), nullable=False),
        sa.Column("currency_code", sa.String(length=3), server_default="NGN", nullable=False),
        sa.Column("transaction_date", sa.Date(), nullable=False),
        sa.Column("description", sa.String(length=500), nullable=False),
        sa.Column("category", sa.String(length=80), nullable=True),
        sa.Column("idempotency_key", sa.String(length=128), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        sa.CheckConstraint(
            "currency_code = upper(currency_code) AND length(currency_code) = 3",
            name="ck_transactions_currency_code_format",
        ),
        sa.CheckConstraint(
            "direction IN ('income', 'expense')",
            name="ck_transactions_direction",
        ),
        sa.CheckConstraint(
            "status IN ('draft', 'posted', 'void')",
            name="ck_transactions_status",
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "business_id",
            "idempotency_key",
            name="uq_transactions_business_idempotency_key",
        ),
    )
    op.create_index(
        "ix_transactions_business_date",
        "transactions",
        ["business_id", "transaction_date"],
    )
    op.create_index(
        "ix_transactions_business_status",
        "transactions",
        ["business_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_transactions_business_status", table_name="transactions")
    op.drop_index("ix_transactions_business_date", table_name="transactions")
    op.drop_table("transactions")
