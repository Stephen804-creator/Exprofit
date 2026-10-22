"""Expected recurring income and expense schedules; never auto-post to the ledger."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, Date, DateTime, ForeignKey, Index, Numeric, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RecurringTransaction(Base):
    """A schedule for a future expected payment, separate from actual transactions."""

    __tablename__ = "recurring_transactions"
    __table_args__ = (
        CheckConstraint("direction IN ('income', 'expense')", name="ck_recurring_direction"),
        CheckConstraint("interval IN ('weekly', 'monthly', 'yearly')", name="ck_recurring_interval"),
        CheckConstraint("amount > 0", name="ck_recurring_amount_positive"),
        CheckConstraint("currency_code = upper(currency_code) AND length(currency_code) = 3", name="ck_recurring_currency"),
        CheckConstraint("end_date IS NULL OR end_date >= start_date", name="ck_recurring_date_order"),
        Index("ix_recurring_business_active_due", "business_id", "is_active", "next_due_date"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False)
    direction: Mapped[str] = mapped_column(String(8), nullable=False)
    description: Mapped[str] = mapped_column(String(160), nullable=False)
    category: Mapped[str | None] = mapped_column(String(80), nullable=True)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    interval: Mapped[str] = mapped_column(String(8), nullable=False)
    start_date: Mapped[date] = mapped_column(Date, nullable=False)
    next_due_date: Mapped[date] = mapped_column(Date, nullable=False)
    end_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    is_active: Mapped[bool] = mapped_column(nullable=False, default=True, server_default=func.true())
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, server_default=func.now(), onupdate=func.now())
