"""Database-backed request counters shared by application instances."""
from datetime import datetime

from sqlalchemy import DateTime, Index, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class RateLimitBucket(Base):
    """Hashed identity and fixed window; raw IPs/emails are never persisted."""

    __tablename__ = "rate_limit_buckets"
    __table_args__ = (Index("ix_rate_limit_buckets_window", "window_start"),)

    key_hash: Mapped[str] = mapped_column(String(64), primary_key=True)
    window_start: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), primary_key=True
    )
    hits: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
