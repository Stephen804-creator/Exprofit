"""Financial ledger entries with explicit direction and lifecycle status."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Transaction(Base):
    """One income or expense entry for a business; amounts are always positive."""

    __tablename__ = "transactions"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_transactions_amount_positive"),
        CheckConstraint(
            "currency_code = upper(currency_code) AND length(currency_code) = 3",
            name="ck_transactions_currency_code_format",
        ),
        CheckConstraint(
            "direction IN ('income', 'expense')",
            name="ck_transactions_direction",
        ),
        CheckConstraint(
            "status IN ('draft', 'posted', 'void')",
            name="ck_transactions_status",
        ),
        UniqueConstraint(
            "business_id",
            "idempotency_key",
            name="uq_transactions_business_idempotency_key",
        ),
        Index("ix_transactions_business_date", "business_id", "transaction_date"),
        Index("ix_transactions_business_status", "business_id", "status"),
        Index("ix_transactions_business_product", "business_id", "product_id"),
        Index("ix_transactions_business_customer", "business_id", "customer_id"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    status: Mapped[str] = mapped_column(String(8), nullable=False, default="draft")
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    transaction_date: Mapped[date] = mapped_column(Date, nullable=False)
    description: Mapped[str] = mapped_column(String(500), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    product_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("products.id", ondelete="RESTRICT"), nullable=True
    )
    customer_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("customers.id", ondelete="RESTRICT"), nullable=True
    )
    idempotency_key: Mapped[str | None] = mapped_column(String(128), nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
