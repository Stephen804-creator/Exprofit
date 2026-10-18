"""Add Solo/business workspace identity and membership lifecycle fields."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0005"
down_revision: str | None = "20261018_0004"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        "businesses",
        sa.Column("display_name", sa.String(length=120), nullable=True),
    )
    op.add_column(
        "businesses",
        sa.Column(
            "workspace_type",
            sa.String(length=16),
            nullable=False,
            server_default="business",
        ),
    )
    op.add_column(
        "businesses",
        sa.Column(
            "organization_label",
            sa.String(length=32),
            nullable=False,
            server_default="Departments",
        ),
    )
    op.add_column("businesses", sa.Column("logo_url", sa.String(length=2048), nullable=True))
    op.create_check_constraint(
        "ck_businesses_workspace_type",
        "businesses",
        "workspace_type IN ('solo', 'business')",
    )

    op.add_column(
        "business_memberships",
        sa.Column("status", sa.String(length=16), nullable=False, server_default="active"),
    )
    op.add_column(
        "business_memberships",
        sa.Column(
            "permissions",
            sa.JSON(),
            nullable=False,
            server_default=sa.text("'{}'"),
        ),
    )
    op.add_column(
        "business_memberships",
        sa.Column("suspended_until", sa.DateTime(timezone=True), nullable=True),
    )
    op.add_column(
        "business_memberships",
        sa.Column("revoked_at", sa.DateTime(timezone=True), nullable=True),
    )
    op.create_check_constraint(
        "ck_memberships_role",
        "business_memberships",
        "role IN ('owner', 'admin', 'worker')",
    )
    op.create_check_constraint(
        "ck_memberships_status",
        "business_memberships",
        "status IN ('active', 'suspended', 'revoked')",
    )
    op.create_index(
        "ix_memberships_status_business",
        "business_memberships",
        ["business_id", "status"],
    )


def downgrade() -> None:
    op.drop_index("ix_memberships_status_business", table_name="business_memberships")
    op.drop_constraint("ck_memberships_status", "business_memberships", type_="check")
    op.drop_constraint("ck_memberships_role", "business_memberships", type_="check")
    op.drop_column("business_memberships", "revoked_at")
    op.drop_column("business_memberships", "suspended_until")
    op.drop_column("business_memberships", "permissions")
    op.drop_column("business_memberships", "status")
    op.drop_constraint("ck_businesses_workspace_type", "businesses", type_="check")
    op.drop_column("businesses", "logo_url")
    op.drop_column("businesses", "organization_label")
    op.drop_column("businesses", "workspace_type")
    op.drop_column("businesses", "display_name")
