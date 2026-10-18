"""Join table defining access and permissions for each workspace member."""

from datetime import datetime
from uuid import UUID, uuid4

from sqlalchemy import JSON, CheckConstraint, DateTime, ForeignKey, String, UniqueConstraint, func
from sqlalchemy.orm import Mapped, mapped_column

from app.db.base import Base


class BusinessMembership(Base):
    """A user's role, lifecycle state, and explicit permissions in a workspace."""

    __tablename__ = "business_memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "business_id", name="uq_membership_user_business"),
        CheckConstraint(
            "role IN ('owner', 'admin', 'worker')",
            name="ck_memberships_role",
        ),
        CheckConstraint(
            "status IN ('active', 'suspended', 'revoked')",
            name="ck_memberships_status",
        ),
    )

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    business_id: Mapped[UUID] = mapped_column(
        ForeignKey("businesses.id", ondelete="CASCADE"), nullable=False, index=True
    )
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="owner")
    status: Mapped[str] = mapped_column(
        String(16), nullable=False, default="active", server_default="active"
    )
    # Domain permissions are separate from department/team assignment.
    permissions: Mapped[dict[str, bool]] = mapped_column(
        JSON, nullable=False, default=dict, server_default="{}"
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    suspended_until: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    revoked_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leave_effective_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    leave_reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
