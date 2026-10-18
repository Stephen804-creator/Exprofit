"""Request and response schemas for shareable workspace invitations."""

from datetime import datetime
from typing import Literal
from uuid import UUID

from pydantic import BaseModel, ConfigDict, Field, field_validator

ALLOWED_PERMISSION_KEYS = {
    f"{domain}:{action}"
    for domain in ("sales", "purchases", "expenses", "inventory", "staff_administration")
    for action in ("read", "write")
}


class InvitationCreate(BaseModel):
    role: Literal["admin", "worker"]
    permissions: dict[str, bool] = Field(default_factory=dict)
    # The workspace owner chooses the expiry; the API only enforces that deadline.
    expires_in_hours: int = Field(default=24, ge=1, le=720)

    @field_validator("permissions")
    @classmethod
    def validate_permissions(cls, value: dict[str, bool]) -> dict[str, bool]:
        unknown = set(value) - ALLOWED_PERMISSION_KEYS
        if unknown:
            raise ValueError(f"Unsupported permission keys: {', '.join(sorted(unknown))}")
        return value


class InvitationRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: UUID
    business_id: UUID
    recipient_email: str | None
    role: str
    permissions: dict[str, bool]
    expires_at: datetime
    invitation_url: str | None = None


class InvitationApplicationCreate(BaseModel):
    token: str = Field(min_length=32, max_length=256)
    full_name: str = Field(min_length=2, max_length=160)
    phone: str | None = Field(default=None, max_length=40)
    identifying_details: str = Field(min_length=5, max_length=1200)
    photo_data_url: str = Field(min_length=100, max_length=2_800_000)

    @field_validator("full_name", "identifying_details")
    @classmethod
    def strip_required_text(cls, value: str) -> str:
        cleaned = value.strip()
        if not cleaned:
            raise ValueError("This field cannot be blank")
        return cleaned

    @field_validator("phone")
    @classmethod
    def strip_phone(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None


class InvitationApplicationRead(BaseModel):
    id: UUID
    invitation_id: UUID
    full_name: str
    email: str
    phone: str | None
    identifying_details: str
    role: str
    status: str
    created_at: datetime


class InvitationApplicationDecision(BaseModel):
    reason: str | None = Field(default=None, max_length=500)


class InvitationApplicationDecisionRead(BaseModel):
    application_id: UUID
    status: Literal["approved", "rejected"]
    business_id: UUID | None = None
    role: str | None = None
    message: str
