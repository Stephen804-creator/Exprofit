"""Schemas for workspace member administration and audit history."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from app.schemas.invitations import ALLOWED_PERMISSION_KEYS


class MembershipUpdate(BaseModel):
    role: Literal["admin", "worker"] | None = None
    permissions: dict[str, bool] | None = None
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("permissions")
    @classmethod
    def validate_permissions(
        cls, value: dict[str, bool] | None
    ) -> dict[str, bool] | None:
        if value is None:
            return None
        unknown = set(value) - ALLOWED_PERMISSION_KEYS
        if unknown:
            raise ValueError(f"Unsupported permission keys: {', '.join(sorted(unknown))}")
        return value

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason cannot be blank")
        return cleaned

    @model_validator(mode="after")
    def require_change(self) -> "MembershipUpdate":
        if self.role is None and self.permissions is None:
            raise ValueError("At least one of role or permissions must be supplied")
        return self


class MembershipReason(BaseModel):
    reason: str = Field(min_length=1, max_length=500)

    @field_validator("reason")
    @classmethod
    def normalize_reason(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("reason cannot be blank")
        return cleaned


class MembershipSuspendRequest(MembershipReason):
    duration_hours: int | None = Field(default=None, ge=1, le=720)


class MembershipRead(BaseModel):
    membership_id: UUID
    user_id: UUID
    email: str
    role: str
    status: str
    permissions: dict[str, bool]
    created_at: datetime
    suspended_until: datetime | None
    revoked_at: datetime | None


class AuditEventRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    actor_user_id: UUID | None
    event_type: str
    target_type: str
    target_id: str
    reason: str | None
    metadata: dict[str, object] = Field(validation_alias="metadata_json")
    created_at: datetime
