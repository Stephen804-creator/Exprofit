"""Business and private Solo workspaces."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import CheckConstraint, DateTime, String, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class Business(Base):
    """A private Solo workspace or a shared business workspace."""

    __tablename__ = "businesses"
    __table_args__ = (
        CheckConstraint(
            "currency_code = upper(currency_code) AND length(currency_code) = 3",
            name="ck_businesses_currency_code_format",
        ),
        CheckConstraint(
            "workspace_type IN ('solo', 'business')",
            name="ck_businesses_workspace_type",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    # name is the original workspace identity; display_name is customizable.
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    workspace_type: Mapped[str] = mapped_column(
        String(16), nullable=False, default="business", server_default="business"
    )
    organization_label: Mapped[str] = mapped_column(
        String(32), nullable=False, default="Departments", server_default="Departments"
    )
    logo_url: Mapped[str | None] = mapped_column(String(2048), nullable=True)
    currency_code: Mapped[str] = mapped_column(String(3), nullable=False, default="NGN")
    timezone: Mapped[str] = mapped_column(String(64), nullable=False, default="Africa/Lagos")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )
