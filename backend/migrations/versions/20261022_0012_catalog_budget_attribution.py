"""Add product/customer attribution and category budgets."""
from collections.abc import Sequence

import sqlalchemy as sa
from alembic import op

revision: str = "20261022_0012"
down_revision: str | None = "20261018_0011"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        "products",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("sku", sa.String(80), nullable=True),
        sa.Column("description", sa.String(500), nullable=True),
        sa.Column("unit_price", sa.Numeric(14, 2), nullable=True),
        sa.Column("unit_cost", sa.Numeric(14, 2), nullable=True),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("unit_price IS NULL OR unit_price >= 0", name="ck_products_unit_price_nonnegative"),
        sa.CheckConstraint("unit_cost IS NULL OR unit_cost >= 0", name="ck_products_unit_cost_nonnegative"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "name", name="uq_products_business_name"),
        sa.UniqueConstraint("business_id", "sku", name="uq_products_business_sku"),
    )
    op.create_index("ix_products_business_active", "products", ["business_id", "is_active"])
    op.create_table(
        "customers",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("name", sa.String(160), nullable=False),
        sa.Column("email", sa.String(254), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("notes", sa.String(500), nullable=True),
        sa.Column("is_active", sa.Boolean(), server_default=sa.true(), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.Column("updated_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_customers_business_active", "customers", ["business_id", "is_active"])
    op.create_table(
        "budgets",
        sa.Column("id", sa.Uuid(), nullable=False),
        sa.Column("business_id", sa.Uuid(), nullable=False),
        sa.Column("category", sa.String(80), nullable=False),
        sa.Column("currency_code", sa.String(3), nullable=False),
        sa.Column("period_start", sa.Date(), nullable=False),
        sa.Column("period_end", sa.Date(), nullable=False),
        sa.Column("amount", sa.Numeric(14, 2), nullable=False),
        sa.Column("warning_threshold_percent", sa.Integer(), server_default="80", nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.func.now(), nullable=False),
        sa.CheckConstraint("amount > 0", name="ck_budgets_amount_positive"),
        sa.CheckConstraint("period_end >= period_start", name="ck_budgets_period_order"),
        sa.CheckConstraint("warning_threshold_percent >= 1 AND warning_threshold_percent <= 200", name="ck_budgets_threshold_range"),
        sa.ForeignKeyConstraint(["business_id"], ["businesses.id"], ondelete="RESTRICT"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("business_id", "category", "currency_code", "period_start", "period_end", name="uq_budgets_period_category"),
    )
    op.create_index("ix_budgets_business_period", "budgets", ["business_id", "period_start", "period_end"])
    op.add_column("transactions", sa.Column("product_id", sa.Uuid(), nullable=True))
    op.add_column("transactions", sa.Column("customer_id", sa.Uuid(), nullable=True))
    op.create_foreign_key("fk_transactions_product_id_products", "transactions", "products", ["product_id"], ["id"], ondelete="RESTRICT")
    op.create_foreign_key("fk_transactions_customer_id_customers", "transactions", "customers", ["customer_id"], ["id"], ondelete="RESTRICT")
    op.create_index("ix_transactions_business_product", "transactions", ["business_id", "product_id"])
    op.create_index("ix_transactions_business_customer", "transactions", ["business_id", "customer_id"])


def downgrade() -> None:
    op.drop_index("ix_transactions_business_customer", table_name="transactions")
    op.drop_index("ix_transactions_business_product", table_name="transactions")
    op.drop_constraint("fk_transactions_customer_id_customers", "transactions", type_="foreignkey")
    op.drop_constraint("fk_transactions_product_id_products", "transactions", type_="foreignkey")
    op.drop_column("transactions", "customer_id")
    op.drop_column("transactions", "product_id")
    op.drop_index("ix_budgets_business_period", table_name="budgets")
    op.drop_table("budgets")
    op.drop_index("ix_customers_business_active", table_name="customers")
    op.drop_table("customers")
    op.drop_index("ix_products_business_active", table_name="products")
    op.drop_table("products")
