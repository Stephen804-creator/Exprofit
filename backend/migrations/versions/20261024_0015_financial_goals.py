"""Add financial revenue and gross-profit goals."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261024_0015"
down_revision: str | None = "20261022_0014"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "financial_goals",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(length=120), nullable=False),
        sa.Column("goal_kind", sa.String(length=20), nullable=False),
        sa.Column("currency_code", sa.String(length=3), nullable=False),
        sa.Column("target_amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "goal_kind IN ('revenue', 'gross_profit')", name="ck_financial_goals_kind"
        ),
        sa.CheckConstraint(
            "target_amount > 0", name="ck_financial_goals_target_positive"
        ),
        sa.CheckConstraint(
            "period_end >= period_start", name="ck_financial_goals_period_order"
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "ix_financial_goals_business_period",
        "financial_goals",
        ["business_id", "period_start", "period_end"],
    )


def downgrade() -> None:
    op.drop_index("ix_financial_goals_business_period", table_name="financial_goals")
    op.drop_table("financial_goals")
