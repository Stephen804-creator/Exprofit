"""Category budgets with explicit currency and inclusive period boundaries."""
from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    CheckConstraint,
    Date,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    Numeric,
    String,
    UniqueConstraint,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Budget(Base):
    """A spending target for one category, currency, and date range."""

    __tablename__ = "budgets"
    __table_args__ = (
        CheckConstraint("amount > 0", name="ck_budgets_amount_positive"),
        CheckConstraint("period_end >= period_start", name="ck_budgets_period_order"),
        CheckConstraint(
            "warning_threshold_percent >= 1 AND warning_threshold_percent <= 200",
            name="ck_budgets_threshold_range",
        ),
        UniqueConstraint(
            "business_id",
            "category",
            "currency_code",
            "period_start",
            "period_end",
            name="uq_budgets_period_category",
        ),
        Index("ix_budgets_business_period", "business_id", "period_start", "period_end"),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False
    )
    category: Mapped[str] = mapped_column(String(80), nullable=False)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False)
    period_start: Mapped[date] = mapped_column(Date, nullable=False)
    period_end: Mapped[date] = mapped_column(Date, nullable=False)
    amount: Mapped[Decimal] = mapped_column(Numeric(14, 2), nullable=False)
    warning_threshold_percent: Mapped[int] = mapped_column(
        Integer, nullable=False, default=80, server_default="80"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
