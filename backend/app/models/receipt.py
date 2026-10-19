"""Private receipt uploads and human-reviewed extraction candidates."""

from datetime import date, datetime
from decimal import Decimal
from uuid import UUID, uuid4

from sqlalchemy import (
    Date,
    DateTime,
    ForeignKey,
    Index,
    LargeBinary,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Receipt(Base):
    """Receipt bytes stay in the database and are never publicly addressable."""

    __tablename__ = "receipts"
    __table_args__ = (
        Index(
            "uq_receipts_business_sha_active",
            "business_id",
            "sha256_hex",
            unique=True,
            postgresql_where=text("review_status != 'rejected'"),
            sqlite_where=text("review_status != 'rejected'"),
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="RESTRICT"), nullable=False, index=True
    )
    uploaded_by_user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="RESTRICT"), nullable=False
    )
    original_filename: Mapped[str] = mapped_column(String(255), nullable=False)
    content_type: Mapped[str] = mapped_column(String(80), nullable=False)
    sha256_hex: Mapped[str] = mapped_column(String(64), nullable=False)
    file_bytes: Mapped[bytes] = mapped_column(LargeBinary, nullable=False, deferred=True)
    extracted_text: Mapped[str] = mapped_column(Text, nullable=False, default="")
    candidate_merchant: Mapped[str | None] = mapped_column(String(160), nullable=True)
    candidate_date: Mapped[date | None] = mapped_column(Date, nullable=True)
    candidate_amount: Mapped[Decimal | None] = mapped_column(Numeric(14, 2), nullable=True)
    candidate_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)
    review_status: Mapped[str] = mapped_column(String(16), nullable=False, default="pending")
    linked_transaction_id: Mapped[UUID | None] = mapped_column(
        ForeignKey("transactions.id", ondelete="RESTRICT"), nullable=True
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
