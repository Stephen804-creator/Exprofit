"""Add voluntary-leave scheduling fields to workspace memberships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0009"
down_revision: str | None = "20261018_0008"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "business_memberships",
        sa.Column("leave_effective_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "business_memberships",
        sa.Column("leave_reason", sa.String(length=500), nullable=True),
    )
    op.create_index(
        "ix_business_memberships_leave_effective_at",
        "business_memberships",
        ["leave_effective_at"],
    )


def downgrade() -> None:
    op.drop_index(
        "ix_business_memberships_leave_effective_at",
        table_name="business_memberships",
    )
    op.drop_column("business_memberships", "leave_reason")
    op.drop_column("business_memberships", "leave_effective_at")
