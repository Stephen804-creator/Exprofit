"""Allow shareable invitations and add owner-reviewed application records."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0010"
down_revision: str | None = "20261018_0009"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.alter_column(
        "workspace_invitations",
        "recipient_email",
        existing_type=sa.String(length=254),
        nullable=True,
    )
    op.create_table(
        "invitation_applications",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("invitation_id", sa.Uuid(), nullable=False),
        sa.Column("user_id", sa.Uuid(), nullable=False),
        sa.Column("full_name", sa.String(length=160), nullable=False),
        sa.Column("phone", sa.String(length=40), nullable=True),
        sa.Column("identifying_details", sa.Text(), nullable=False),
        sa.Column("photo_bytes", sa.LargeBinary(), nullable=True),
        sa.Column("status", sa.String(length=16), server_default="pending", nullable=False),
        sa.Column("reviewed_by_user_id", sa.Uuid(), nullable=True),
        sa.Column("reviewed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.CheckConstraint(
            "status IN ('pending', 'approved', 'rejected')",
            name="ck_invitation_applications_status",
        ),
        sa.ForeignKeyConstraint(["invitation_id"], ["workspace_invitations.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["reviewed_by_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("invitation_id", name="uq_invitation_applications_invitation_id"),
    )
    op.create_index(
        "ix_invitation_applications_invitation_id", "invitation_applications", ["invitation_id"]
    )
    op.create_index("ix_invitation_applications_user_id", "invitation_applications", ["user_id"])


def downgrade() -> None:
    op.drop_index("ix_invitation_applications_user_id", table_name="invitation_applications")
    op.drop_index("ix_invitation_applications_invitation_id", table_name="invitation_applications")
    op.drop_table("invitation_applications")
    op.alter_column(
        "workspace_invitations",
        "recipient_email",
        existing_type=sa.String(length=254),
        nullable=False,
    )
