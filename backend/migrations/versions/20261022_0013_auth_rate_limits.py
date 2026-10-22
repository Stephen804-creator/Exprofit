"""Add shared authentication rate-limit buckets."""
from collections.abc import Sequence
import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0013"
down_revision: str | None = "20261022_0012"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "rate_limit_buckets",
        sa.Column("key_hash", sa.String(64), nullable=False),
        sa.Column("window_start", sa.DateTime(timezone=True), nullable=False),
        sa.Column("hits", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("key_hash", "window_start"),
    )
    op.create_index("ix_rate_limit_buckets_window", "rate_limit_buckets", ["window_start"])


def downgrade() -> None:
    op.drop_index("ix_rate_limit_buckets_window", table_name="rate_limit_buckets")
    op.drop_table("rate_limit_buckets")
