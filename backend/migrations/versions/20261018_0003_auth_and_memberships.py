"""Add users and explicit business memberships."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0003"
down_revision: str | None = "20261018_0002"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "users",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("email", sa.String(length=254), nullable=False),
        sa.Column("password_hash", sa.String(length=255), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.true()),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("email"),
    )
    op.create_table(
        "business_memberships",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("role", sa.String(length=16), nullable=False, server_default="owner"),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("user_id", "business_id", name="uq_membership_user_business"),
    )
    op.create_index("ix_business_memberships_user_id", "business_memberships", ["user_id"])
    op.create_index(
        "ix_business_memberships_business_id", "business_memberships", ["business_id"]
    )


def downgrade() -> None:
    op.drop_index("ix_business_memberships_business_id", table_name="business_memberships")
    op.drop_index("ix_business_memberships_user_id", table_name="business_memberships")
    op.drop_table("business_memberships")
    op.drop_table("users")
