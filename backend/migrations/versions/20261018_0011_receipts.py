"""Add private receipt storage and review state."""

from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261018_0011"
down_revision: str | None = "20261018_0010"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "receipts",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("uploaded_by_user_id", sa.Uuid(), nullable=False),
        sa.Column("original_filename", sa.String(length=255), nullable=False),
        sa.Column("content_type", sa.String(length=80), nullable=False),
        sa.Column("sha256_hex", sa.String(length=64), nullable=False),
        sa.Column("file_bytes", sa.LargeBinary(), nullable=False),
        sa.Column("extracted_text", sa.Text(), nullable=False),
        sa.Column("candidate_merchant", sa.String(length=160), nullable=True),
        sa.Column("candidate_date", sa.Date(), nullable=True),
        sa.Column("candidate_amount", sa.Numeric(precision=14, scale=2), nullable=True),
        sa.Column("candidate_currency", sa.String(length=3), nullable=True),
        sa.Column("review_status", sa.String(length=16), nullable=False),
        sa.Column("linked_transaction_id", sa.Uuid(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            server_default=sa.func.now(),
            nullable=False,
        ),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(["uploaded_by_user_id"], ["users.id"], ondelete="RESTRICT"),
        sa.ForeignKeyConstraint(
            ["linked_transaction_id"], ["transactions.id"], ondelete="RESTRICT"
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_receipts_business_id", "receipts", ["business_id"])
    op.create_index("ix_receipts_sha256_hex", "receipts", ["sha256_hex"])
    op.create_index(
        "uq_receipts_business_sha_active",
        "receipts",
        ["business_id", "sha256_hex"],
        unique=True,
        postgresql_where=sa.text("review_status != 'rejected'"),
        sqlite_where=sa.text("review_status != 'rejected'"),
    )


def downgrade() -> None:
    op.drop_index("uq_receipts_business_sha_active", table_name="receipts")
    op.drop_index("ix_receipts_sha256_hex", table_name="receipts")
    op.drop_index("ix_receipts_business_id", table_name="receipts")
    op.drop_table("receipts")
